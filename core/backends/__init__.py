import os

from .base import ConversionBackend
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
        result.append({
            'name': cls.name,
            'label': cls.label,
            'available': backend.is_available(),
            'reason': '' if backend.is_available()
            else backend.unavailable_reason(),
        })
    return result


def get_backend(name=None):
    """按名称创建后端；``auto`` 按优先级选择第一个可用的后端。"""
    name = (name or os.environ.get(BACKEND_ENV) or DEFAULT_BACKEND)
    name = name.strip().lower()

    if name in ('', 'auto'):
        reasons = []
        for cls in BACKEND_CLASSES:
            backend = cls()
            if backend.is_available():
                return backend
            reasons.append('  - {}: {}'.format(
                backend.label, backend.unavailable_reason()))
        raise RuntimeError(
            '没有可用的文件转换后端。\n{}\n'
            '请安装 WPS Office + pywpsrpc，或 LibreOffice；'
            '也可用 {} 指定后端。'.format('\n'.join(reasons), BACKEND_ENV))

    for cls in BACKEND_CLASSES:
        if cls.name == name:
            backend = cls()
            if not backend.is_available():
                raise RuntimeError(
                    '后端 {} 不可用: {}'.format(
                        name, backend.unavailable_reason()))
            return backend

    raise RuntimeError('未知的转换后端: {}'.format(name))
