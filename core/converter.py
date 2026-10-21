import os

from .backends import (
    BACKEND_ENV,
    BACKEND_CLASSES as _BACKEND_CLASSES,
    DEFAULT_BACKEND,
    backend_choices as _backend_choices,
    backend_status as _backend_status,
    get_backend,
)


class DocumentConverter:
    """文件转 PDF 门面，可在运行时切换底层后端。

    统一接口::

        output_path = converter.convert_to_pdf(input_path)

    后端选择优先级：
    1. 构造函数参数 ``backend``
    2. 环境变量 ``PDF_EDIT_BACKEND``（auto/wps/libreoffice）
    3. ``auto``：优先 WPS(pywpsrpc)，其次 LibreOffice
    """

    SUPPORTED = set().union(
        *(cls.SUPPORTED for cls in _BACKEND_CLASSES))

    def __init__(self, backend=None):
        self._requested = (backend or os.environ.get(BACKEND_ENV)
                           or DEFAULT_BACKEND).strip().lower()
        self._backend = None

    @property
    def requested_name(self):
        return self._requested

    @property
    def backend(self):
        if self._backend is None:
            self._backend = get_backend(self._requested)
        return self._backend

    @property
    def name(self):
        return self.backend.name

    @property
    def label(self):
        return self.backend.label

    def set_backend(self, name):
        """切换后端（auto/wps/libreoffice），下次转换时生效。"""
        self._requested = (name or DEFAULT_BACKEND).strip().lower()
        self._backend = None

    def backend_choices(self):
        return _backend_choices()

    def backend_status(self):
        return _backend_status()

    def can_convert(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.pdf':
            return True
        if ext not in self.SUPPORTED:
            return False
        try:
            return self.backend.can_convert(filepath)
        except RuntimeError:
            # 还没选定后端：只要有后端支持这种格式就算能转
            return True

    def convert_to_pdf(self, input_path, output_dir=None):
        """转换文件为 PDF。

        首选当前后端；它失败而另一个套件可用时自动改用另一个
        （总比直接失败强 —— 用户只关心文件被转出来了）。
        """
        backend = self.backend
        try:
            return backend.convert_to_pdf(input_path, output_dir=output_dir)
        except Exception as exc:
            fallback = self._fallback_backend(backend)
            if fallback is None:
                raise
            try:
                return fallback.convert_to_pdf(input_path,
                                               output_dir=output_dir)
            except Exception:
                raise exc

    def _fallback_backend(self, current):
        """另一个可用的后端（没有就返回 None）。"""
        for cls in _BACKEND_CLASSES:
            if cls.name == current.name:
                continue
            other = cls()
            if other.is_available():
                return other
        return None
