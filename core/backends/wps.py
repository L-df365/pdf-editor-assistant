import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import time

from .base import ConversionBackend

WPS_LIB_DIRS = (
    os.environ.get('WPS_OFFICE_DIR', ''),
    '/opt/kingsoft/wps-office/office6',
    '/usr/lib/office6',
    '/opt/apps/cn.wps.wps-office/files/kingsoft/wps-office/office6',
)

CONVERT_TIMEOUT = 180


def find_wps_lib_dir():
    for path in WPS_LIB_DIRS:
        if not path:
            continue
        if os.path.exists(os.path.join(path, 'librpcwpsapi_sysqt5.so')):
            return path
    return None


def _kill_wps_process(pidfile):
    """结束 worker 记录的 WPS 自动化进程（可能已被 init 收养）。"""
    try:
        with open(pidfile) as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return

    try:
        with open('/proc/{}/cmdline'.format(pid), 'rb') as f:
            cmdline = f.read().decode('utf-8', 'replace')
    except OSError:
        return
    if '-rpcserverport' not in cmdline:
        return

    try:
        pgid = os.getpgid(pid)
    except OSError:
        return

    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pgid, sig)
        except OSError:
            return
        for _ in range(20):
            if not os.path.exists('/proc/{}'.format(pid)):
                return
            time.sleep(0.1)


class PyWpsRpcBackend(ConversionBackend):
    """调用本机 WPS Office（pywpsrpc）静默转换为 PDF。

    转换在独立进程中完成，WPS 窗口始终隐藏（Visible = False），
    不会阻塞 Tk 主线程，也不会把窗口弹到用户面前。
    """

    name = 'wps'
    label = 'WPS 静默转换 (pywpsrpc)'

    SUPPORTED = {
        '.docx', '.doc', '.odt', '.rtf', '.txt',
        '.xlsx', '.xls', '.ods',
        '.pptx', '.ppt', '.odp',
    }

    def is_available(self):
        return (importlib.util.find_spec('pywpsrpc') is not None
                and find_wps_lib_dir() is not None)

    def unavailable_reason(self):
        if importlib.util.find_spec('pywpsrpc') is None:
            return '未安装 pywpsrpc（pip install pywpsrpc，aarch64 需源码编译）'
        if find_wps_lib_dir() is None:
            return '未找到 WPS Office 的 RPC 库（librpcwpsapi_sysqt5.so）'
        return '未知原因'

    def convert_to_pdf(self, input_path, output_dir=None):
        ext = os.path.splitext(input_path)[1].lower()
        if ext == '.pdf':
            return input_path

        if not self.is_available():
            raise RuntimeError(self.unavailable_reason())

        output_path = self.build_output_path(input_path, output_dir)
        worker = os.path.join(os.path.dirname(__file__), 'wps_worker.py')
        pidfile = output_path + '.wps.pid'
        try:
            os.remove(pidfile)
        except OSError:
            pass

        env = os.environ.copy()
        wps_dir = find_wps_lib_dir()
        if wps_dir:
            old_ld = env.get('LD_LIBRARY_PATH', '')
            env['LD_LIBRARY_PATH'] = (
                wps_dir + (os.pathsep + old_ld if old_ld else ''))

        cmd = [sys.executable, worker,
               os.path.abspath(input_path), output_path, pidfile]

        # WPS 是 GUI 程序。始终放进独立的 Xvfb 虚拟屏幕，
        # 这样启动动画/窗口只画在虚拟屏幕上，用户桌面不会闪现。
        xvfb_run = shutil.which('xvfb-run')
        if xvfb_run:
            cmd = [xvfb_run, '-a',
                   '-s', '-screen 0 1280x1024x24',
                   '--'] + cmd
        elif not (env.get('DISPLAY') or env.get('WAYLAND_DISPLAY')):
            raise RuntimeError(
                'WPS 静默转换需要 xvfb-run 或图形会话，'
                '请安装 xvfb（apt install xvfb）')

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            start_new_session=True,
        )

        try:
            try:
                stdout, stderr = proc.communicate(timeout=CONVERT_TIMEOUT)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:
                    pass
                try:
                    proc.communicate(timeout=5)
                except Exception:
                    pass
                raise RuntimeError(
                    'WPS 转换超时（{} 秒）: {}'.format(
                        CONVERT_TIMEOUT, os.path.basename(input_path)))
        finally:
            _kill_wps_process(pidfile)
            try:
                os.remove(pidfile)
            except OSError:
                pass

        if proc.returncode != 0 or not os.path.exists(output_path):
            detail = (stderr or stdout or '').strip()
            if len(detail) > 2000:
                detail = '...' + detail[-2000:]
            raise RuntimeError(
                'WPS 转换失败: {}\n{}'.format(
                    os.path.basename(input_path), detail))

        return output_path
