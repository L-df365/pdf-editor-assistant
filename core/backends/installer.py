"""按需安装转换后端。

应用不打包 WPS/LibreOffice；用户选择未安装的后端时，由这里调用
系统包管理器安装，或打开官方下载页面。
"""

import importlib.util
import os
import shutil
import subprocess
import sys

WPS_DOWNLOAD_URL = 'https://linux.wps.cn/'
PYWPSRPC_URL = 'https://github.com/timxx/pywpsrpc'
LIBREOFFICE_URL = 'https://www.libreoffice.org/download/'


class ManualInstallRequired(RuntimeError):
    def __init__(self, message, url=''):
        super().__init__(message)
        self.url = url


def _noop_log(text):
    pass


def package_manager():
    for name in ('apt-get', 'dnf', 'pacman'):
        if shutil.which(name):
            return name
    return None


def _command(name):
    return shutil.which(name) or name


def _run(args, log=None, timeout=None):
    log = log or _noop_log
    log('$ ' + ' '.join(args))
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    try:
        for line in proc.stdout:
            log(line.rstrip())
        return proc.wait(timeout=timeout)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def _root_prefix():
    if os.geteuid() == 0:
        return []
    for name in ('pkexec', 'sudo'):
        path = shutil.which(name)
        if path:
            return [path]
    raise RuntimeError('需要管理员权限，但未找到 pkexec 或 sudo')


def _run_root(args, log=None):
    return _run(_root_prefix() + args, log=log)


def _apt_install(packages, log):
    prefix = [_command('env'), 'DEBIAN_FRONTEND=noninteractive']
    rc = _run_root(prefix + [_command('apt-get'), 'update'], log=log)
    if rc != 0:
        raise RuntimeError('apt-get update 失败（退出码 {}）'.format(rc))
    rc = _run_root(
        prefix + [_command('apt-get'), 'install', '-y',
                  '--no-install-recommends'] + packages,
        log=log,
    )
    if rc != 0:
        raise RuntimeError('apt-get install 失败（退出码 {}）'.format(rc))


def _dnf_install(packages, log):
    rc = _run_root([_command('dnf'), 'install', '-y'] + packages, log=log)
    if rc != 0:
        raise RuntimeError('dnf install 失败（退出码 {}）'.format(rc))


def _pacman_install(packages, log):
    rc = _run_root(
        [_command('pacman'), '-S', '--noconfirm'] + packages, log=log)
    if rc != 0:
        raise RuntimeError('pacman 安装失败（退出码 {}）'.format(rc))


def _apt_has_package(name):
    try:
        result = subprocess.run(
            [_command('apt-cache'), 'show', name],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=20,
        )
        return result.returncode == 0
    except Exception:
        return False


def is_wps_installed():
    return bool(shutil.which('wps')) or os.path.exists(
        '/opt/kingsoft/wps-office/office6/wps')


def is_pywpsrpc_installed():
    return importlib.util.find_spec('pywpsrpc') is not None


def install_libreoffice(log=None):
    log = log or _noop_log
    packages = ['libreoffice-core', 'libreoffice-writer', 'libreoffice-calc']
    manager = package_manager()
    if manager == 'apt-get':
        _apt_install(packages, log)
    elif manager == 'dnf':
        _dnf_install(packages, log)
    elif manager == 'pacman':
        _pacman_install(['libreoffice-fresh'], log)
    else:
        raise ManualInstallRequired(
            '未找到系统包管理器，请手动安装 LibreOffice。',
            LIBREOFFICE_URL,
        )
    if not shutil.which('soffice'):
        raise RuntimeError(
            'LibreOffice 安装后仍未找到 soffice 可执行文件')
    return 'LibreOffice 安装完成'


def install_wps(log=None):
    log = log or _noop_log

    if not is_wps_installed():
        manager = package_manager()
        if manager == 'apt-get':
            if not _apt_has_package('wps-office'):
                raise ManualInstallRequired(
                    'WPS Office 不在系统软件源中。已打开官方下载页面，'
                    '请安装 WPS 后重启应用。',
                    WPS_DOWNLOAD_URL,
                )
            _apt_install(['wps-office'], log)
        elif manager == 'dnf':
            try:
                _dnf_install(['wps-office'], log)
            except RuntimeError:
                raise ManualInstallRequired(
                    'WPS Office 无法从系统软件源安装。已打开官方下载页面，'
                    '请安装 WPS 后重启应用。',
                    WPS_DOWNLOAD_URL,
                )
        elif manager == 'pacman':
            try:
                _pacman_install(['wps-office'], log)
            except RuntimeError:
                raise ManualInstallRequired(
                    'WPS Office 无法从系统软件源安装。已打开官方下载页面，'
                    '请安装 WPS 后重启应用。',
                    WPS_DOWNLOAD_URL,
                )
        else:
            raise ManualInstallRequired(
                '未找到系统包管理器。已打开官方下载页面，'
                '请安装 WPS 后重启应用。',
                WPS_DOWNLOAD_URL,
            )

    if not is_wps_installed():
        raise ManualInstallRequired(
            'WPS 安装后仍未找到可执行文件。已打开官方下载页面，'
            '请检查安装后重启应用。',
            WPS_DOWNLOAD_URL,
        )

    if not shutil.which('xvfb-run'):
        manager = package_manager()
        if manager == 'apt-get':
            _apt_install(['xvfb', 'xauth'], log)
        elif manager == 'dnf':
            _dnf_install(['xorg-x11-server-Xvfb', 'xauth'], log)
        elif manager == 'pacman':
            _pacman_install(['xorg-server-xvfb', 'xorg-xauth'], log)
        else:
            raise ManualInstallRequired(
                '未找到系统包管理器，无法安装 xvfb。'
                '请手动安装 xvfb-run 后重启应用。',
                WPS_DOWNLOAD_URL,
            )
        if not shutil.which('xvfb-run'):
            raise RuntimeError('xvfb 安装后仍未找到 xvfb-run')

    if not is_pywpsrpc_installed():
        rc = _run(
            [sys.executable, '-m', 'pip', 'install', '--user',
             'pywpsrpc', '-i',
             'https://pypi.tuna.tsinghua.edu.cn/simple'],
            log=log,
        )
        if rc != 0:
            raise ManualInstallRequired(
                'pywpsrpc 安装失败。aarch64/麒麟需要源码编译，'
                '请参考 requirements-wps.txt 或项目文档。',
                PYWPSRPC_URL,
            )
        if not is_pywpsrpc_installed():
            raise ManualInstallRequired(
                'pywpsrpc 已安装但当前进程未找到。请重启应用；'
                '若仍不可用，请参考 requirements-wps.txt 源码编译。',
                PYWPSRPC_URL,
            )

    return 'WPS 后端安装完成'


INSTALLERS = {
    'wps': install_wps,
    'libreoffice': install_libreoffice,
}


def install_backend(name, log=None):
    installer = INSTALLERS.get(name)
    if installer is None:
        raise ValueError('未知后端: {}'.format(name))
    return installer(log=log)
