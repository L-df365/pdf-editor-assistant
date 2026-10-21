import os
import tempfile


class ConversionBackend:
    """文件转 PDF 后端接口。

    所有后端都实现统一入口::

        output_path = backend.convert_to_pdf(input_path)

    需要把临时文件放到指定目录时，可传入 ``output_dir``。
    """

    name = ''
    label = ''
    SUPPORTED = frozenset()

    def can_convert(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        return ext == '.pdf' or ext in self.SUPPORTED

    def is_available(self):
        """桥接工具是否就绪（能不能真的转换）。"""
        return False

    def suite_installed(self):
        """对应的办公套件装了没有（和桥接工具是两回事）。"""
        return False

    def unavailable_reason(self):
        return '后端不可用'

    def convert_to_pdf(self, input_path, output_dir=None):
        raise NotImplementedError

    @staticmethod
    def build_output_path(input_path, output_dir=None):
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix='pdf_edit_')
        os.makedirs(output_dir, exist_ok=True)

        base = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(output_dir, base + '.pdf')
        index = 1
        while os.path.exists(output_path):
            output_path = os.path.join(
                output_dir, '{}_{}.pdf'.format(base, index))
            index += 1
        return output_path
