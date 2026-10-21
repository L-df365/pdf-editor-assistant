import os

from .libreoffice import LibreOfficeBackend
from .wps import PyWpsRpcBackend

BACKEND_CLASSES = (PyWpsRpcBackend, LibreOfficeBackend)

DEFAULT_BACKEND = 'auto'
BACKEND_ENV = 'PDF_EDIT_BACKEND'


def backend_choices():
    """返回 GUI/CLI 可选的 (name, label) 列表。"""
    return [('auto', '自动选择')] + [
        (cls.name, cls.label) for cls in BACKEND_CLASSES]


def backend_status():
    """返回每个后端的可用状态，便于界面展示或排查。"""
    result = []
    for cls in BACKEND_CLASSES:
        backend = cls()
        available = backend.is_available()
        result.append({
            'name': cls.name,
            'label': cls.label,
            'available': available,
            # 办公套件装了没有：套件在、只是桥接工具没就绪时，
            # 不该显示成"未安装"
            'installed': backend.suite_installed(),
            'reason': '' if available else backend.unavailable_reason(),
        })
    return result


def detect_office_suite():
    """探测本机装了哪个办公套件：'wps' / 'libreoffice' / None。

    策略是"有什么用什么"：装了 WPS 就用 WPS，装了 LibreOffice 就用
    LibreOffice。桥接工具（pywpsrpc 等）由应用自己准备，不该让用户编译。
    """
    from .installer import is_libreoffice_installed, is_wps_installed
    if is_wps_installed():
        return 'wps'
    if is_libreoffice_installed():
        return 'libreoffice'
    return None


def get_backend(name=None):
    """按名称创建后端；``auto`` 按"本机有什么用什么"来选。

    注意：这里看的是**办公套件**装没装（WPS / LibreOffice），
    不是桥接工具 —— 桥接工具缺了应用会自己补上，
    不该因为 pywpsrpc 没装就把用户降级到另一个套件。
    """
    name = (name or os.environ.get(BACKEND_ENV) or DEFAULT_BACKEND)
    name = name.strip().lower()

    if name in ('', 'auto'):
        suite = detect_office_suite()
        if suite:
            backend = _create(suite)
            if backend.is_available():
                return backend
            # 套件在、桥接工具还没准备好：仍然用这个套件，
            # 由应用去把桥接工具准备好（启动时会自动做）。
            return backend
        reasons = []
        for cls in BACKEND_CLASSES:
            backend = cls()
            reasons.append('  - {}: {}'.format(
                backend.label, backend.unavailable_reason()))
        raise RuntimeError(
            '本机没有安装办公套件，无法转换 Word/Excel 等文件。\n{}\n'
            '请安装 WPS Office 或 LibreOffice 后重启应用。'.format(
                '\n'.join(reasons)))

    backend = _create(name)
    if backend is None:
        raise RuntimeError('未知的转换后端: {}'.format(name))
    if not backend.is_available():
        raise RuntimeError(
            '后端 {} 不可用: {}'.format(name, backend.unavailable_reason()))
    return backend


def _create(name):
    for cls in BACKEND_CLASSES:
        if cls.name == name:
            return cls()
    return None
