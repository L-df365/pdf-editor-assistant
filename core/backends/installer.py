"""按需准备转换后端。

应用不打包 WPS/LibreOffice；用户装好后，这里负责把**转换支持**准备好：
系统里的 PyQt5 运行时、Xvfb、以及随应用一起发布的 pywpsrpc 预编译包。

原则：**用户只需要决定装 WPS 还是装 LibreOffice**，
"工具"是应用自己的事 —— 能用预编译包就绝不让人编译。
"""

import glob
import importlib.util
import os
import platform
import shutil
import subprocess
import sys

WPS_DOWNLOAD_URL = 'https://linux.wps.cn/'
PYWPSRPC_URL = 'https://github.com/timxx/pywpsrpc'
LIBREOFFICE_URL = 'https://www.libreoffice.org/download/'

#: 随应用发布的预编译包目录（wheels/）
WHEELS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), 'wheels')

#: PyQt5 运行时（pywpsrpc 的绑定需要 libQt5Core）
PYQT_PACKAGES = {
    'apt-get': ['python3-pyqt5'],
    'dnf': ['python3-qt5'],
    'pacman': ['python-pyqt5'],
}

#: Xvfb（让 WPS 完全静默，不在桌面上弹窗）
XVFB_PACKAGES = {
    'apt-get': ['xvfb', 'xauth'],
    'dnf': ['xorg-x11-server-Xvfb', 'xauth'],
    'pacman': ['xorg-server-xvfb', 'xorg-xauth'],
}


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


#: WPS 的可执行文件可能装在这些地方（应用商店的沙箱路径也要认）
WPS_EXECUTABLE_PATHS = (
    '/opt/kingsoft/wps-office/office6/wps',
    '/usr/lib/office6/wps',
    '/opt/apps/cn.wps.wps-office/files/kingsoft/wps-office/office6/wps',
)


def is_wps_installed():
    """本机有没有 WPS Office。

    判据要宽：软件商店装的 WPS 装在沙箱路径下，只认 /opt/kingsoft 会漏判，
    漏判了就会去让用户重装一套已有的 WPS。
    """
    from .wps import find_wps_lib_dir
    if find_wps_lib_dir() is not None:
        return True
    if shutil.which('wps'):
        return True
    return any(os.path.exists(path) for path in WPS_EXECUTABLE_PATHS)


def is_libreoffice_installed():
    """本机有没有 LibreOffice（含随应用附带的便携版）。"""
    if shutil.which('soffice'):
        return True
    from .libreoffice import LibreOfficeBackend
    return bool(LibreOfficeBackend().soffice)


def is_pywpsrpc_installed():
    return importlib.util.find_spec('pywpsrpc') is not None


def bundled_wheels():
    """随应用发布的预编译包（wheels/ 下的 .whl）。"""
    if not os.path.isdir(WHEELS_DIR):
        return []
    return sorted(glob.glob(os.path.join(WHEELS_DIR, '*.whl')))


def _wheel_matches_platform(path):
    """这个 wheel 能不能装到当前机器上（看文件名里的平台标签）。"""
    name = os.path.basename(path)
    machine = platform.machine()
    if machine in ('aarch64', 'arm64'):
        arch = 'aarch64'
    elif machine in ('x86_64', 'amd64'):
        arch = 'x86_64'
    else:
        arch = machine
    python_tag = 'cp{}{}'.format(*sys.version_info[:2])
    return arch in name and (python_tag in name or 'abi3' in name)


APP_STORE_QUERIES = {
    'wps': 'WPS Office',
    'libreoffice': 'LibreOffice',
}

APP_STORE_FALLBACKS = {
    'wps': WPS_DOWNLOAD_URL,
    'libreoffice': LIBREOFFICE_URL,
}


def _spawn_detached(args):
    subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def open_app_store(name):
    """打开系统软件商店搜索指定后端，返回给用户看的提示。"""
    keyword = APP_STORE_QUERIES.get(name, name)
    stores = (
        ('kylin-software-center', ()),
        ('gnome-software', ('--search',)),
        ('plasma-discover', ('--search',)),
    )
    for command, extra in stores:
        path = shutil.which(command)
        if not path:
            continue
        args = [path]
        if command == 'kylin-software-center':
            args.append(keyword)
        else:
            args.extend(extra)
            args.append(keyword)
        try:
            _spawn_detached(args)
            return '已打开软件商店，请搜索并安装 {}。'.format(keyword)
        except OSError:
            continue
    try:
        import webbrowser
        webbrowser.open(APP_STORE_FALLBACKS.get(name, LIBREOFFICE_URL))
    except Exception:
        return '请手动安装 {} 后重启应用。'.format(keyword)
    return '已打开下载页面，请安装 {} 后重启应用。'.format(keyword)


# --------------------------------------------------------------------------
# 办公套件 → 桥接工具
#
# 用户只需要决定"装 WPS 还是装 LibreOffice"。
# 桥接工具（PyQt5 运行时、Xvfb、pywpsrpc 预编译包）由应用自己准备，
# **绝不让用户去编译**。
# --------------------------------------------------------------------------

#: 桥接工具 = 系统包（包管理器，二进制）+ 随应用发布的预编译 wheel
BRIDGES = {
    'wps': {
        'label': 'WPS Office',
        'packages': {
            'apt-get': ['python3-pyqt5', 'xvfb', 'xauth'],
            'dnf': ['python3-qt5', 'xorg-x11-server-Xvfb', 'xauth'],
            'pacman': ['python-pyqt5', 'xorg-server-xvfb', 'xorg-xauth'],
        },
        'wheels': ['pywpsrpc'],
    },
    'libreoffice': {
        'label': 'LibreOffice',
        'packages': {
            'apt-get': ['libreoffice-core', 'libreoffice-writer',
                        'libreoffice-calc'],
            'dnf': ['libreoffice-core', 'libreoffice-writer',
                    'libreoffice-calc'],
            'pacman': ['libreoffice-fresh'],
        },
        'wheels': [],
    },
}


def _install_packages(packages, log):
    """用系统包管理器装二进制包（不编译）。"""
    manager = package_manager()
    if manager == 'apt-get':
        _apt_install(packages, log)
    elif manager == 'dnf':
        _dnf_install(packages, log)
    elif manager == 'pacman':
        _pacman_install(packages, log)
    else:
        raise ManualInstallRequired(
            '未找到系统包管理器，无法自动安装依赖。',
            APP_STORE_FALLBACKS.get('libreoffice', LIBREOFFICE_URL),
        )


def _install_bundled_wheel(log):
    """装随应用发布的预编译包（arm64 上 pywpsrpc 上游没有 wheel，
    有了它就不需要用户自己编译）。"""
    for wheel in bundled_wheels():
        if not _wheel_matches_platform(wheel):
            continue
        if 'pywpsrpc' not in os.path.basename(wheel):
            continue
        log('安装随应用发布的预编译包：{}'.format(
            os.path.basename(wheel)))
        rc = _run(
            [sys.executable, '-m', 'pip', 'install', '--user',
             '--force-reinstall', wheel],
            log=log,
        )
        if rc == 0:
            return True
        log('预编译包安装失败，尝试其它方式')
        return False
    return False


def _install_pywpsrpc(log):
    """装 pywpsrpc：优先用随应用发布的预编译包，其次才从源码装。

    源码安装由**应用**来做（用户不用动手），失败也不让用户去编译。
    """
    if is_pywpsrpc_installed():
        return True
    if _install_bundled_wheel(log):
        return is_pywpsrpc_installed()
    log('没有匹配的预编译包，改为从源码安装（由应用完成，无需你操作）')
    rc = _run(
        [sys.executable, '-m', 'pip', 'install', '--user',
         'pywpsrpc', '-i',
         'https://pypi.tuna.tsinghua.edu.cn/simple'],
        log=log,
    )
    return rc == 0 and is_pywpsrpc_installed()


def prepare_bridge(name, log=None):
    """给已装好的办公套件装上桥接工具。"""
    log = log or _noop_log
    bridge = BRIDGES.get(name)
    if not bridge:
        raise ValueError('未知后端: {}'.format(name))

    manager = package_manager()
    packages = bridge['packages'].get(manager)
    if packages:
        missing = [p for p in packages
                   if not _package_installed(p, manager)]
        if missing:
            log('安装系统依赖：{}'.format('、'.join(missing)))
            _install_packages(missing, log)

    if name == 'wps':
        if not _install_pywpsrpc(log):
            raise RuntimeError(
                'WPS 转换支持准备失败（pywpsrpc 装不上）。'
                '可改用 LibreOffice 转换，或重新安装 WPS Office 后重试。')
    return '{} 转换支持已就绪'.format(bridge['label'])


def _package_installed(name, manager):
    """这个系统包装了没有（尽量用本地信息判断，不去刷软件源）。"""
    if manager == 'apt-get':
        try:
            result = subprocess.run(
                [_command('dpkg-query'), '-W', '-f=${Status}', name],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=15)
            return 'installed' in result.stdout
        except Exception:
            return False
    if manager == 'dnf':
        try:
            result = subprocess.run(
                [_command('rpm'), '-q', name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=15)
            return result.returncode == 0
        except Exception:
            return False
    if manager == 'pacman':
        try:
            result = subprocess.run(
                [_command('pacman'), '-Q', name],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=15)
            return result.returncode == 0
        except Exception:
            return False
    return False


def install_libreoffice(log=None):
    """装 LibreOffice（办公套件本身）+ 桥接工具。"""
    log = log or _noop_log
    if not is_libreoffice_installed():
        _install_packages(BRIDGES['libreoffice']['packages']
                          .get(package_manager(), []), log)
    if not shutil.which('soffice'):
        raise RuntimeError(
            'LibreOffice 安装后仍未找到 soffice 可执行文件')
    return prepare_bridge('libreoffice', log)


def install_wps(log=None):
    """装 WPS（办公套件本身）+ 桥接工具（PyQt5/Xvfb/pywpsrpc 预编译包）。"""
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
        elif manager in ('dnf', 'pacman'):
            try:
                _install_packages(['wps-office'], log)
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

    from .wps import find_wps_lib_dir
    if find_wps_lib_dir() is None:
        raise ManualInstallRequired(
            '未找到 WPS Office 的 RPC 库（librpcwpsapi_sysqt5.so）。'
            '请重新安装 WPS Office 后重启应用。',
            WPS_DOWNLOAD_URL,
        )

    return prepare_bridge('wps', log)


INSTALLERS = {
    'wps': install_wps,
    'libreoffice': install_libreoffice,
}


def install_backend(name, log=None):
    installer = INSTALLERS.get(name)
    if installer is None:
        raise ValueError('未知后端: {}'.format(name))
    return installer(log=log)
