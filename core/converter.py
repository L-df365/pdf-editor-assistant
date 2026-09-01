import os
import subprocess
import tempfile
import shutil


class DocumentConverter:
    """使用 LibreOffice headless 将 Office 文档转换为 PDF。"""

    SUPPORTED = {
        '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt',
        '.odt', '.ods', '.odp', '.rtf', '.txt',
    }

    def __init__(self, soffice_path=None):
        if soffice_path and os.path.exists(soffice_path):
            self.soffice = soffice_path
        else:
            self.soffice = shutil.which('soffice') or '/usr/bin/soffice'

    def can_convert(self, filepath):
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.pdf':
            return True
        return ext in self.SUPPORTED

    def convert_to_pdf(self, input_path, output_dir=None):
        ext = os.path.splitext(input_path)[1].lower()
        if ext == '.pdf':
            return input_path

        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix='pdf_edit_')
        os.makedirs(output_dir, exist_ok=True)

        with tempfile.TemporaryDirectory() as profile_dir:
            result = subprocess.run(
                [
                    self.soffice,
                    f'-env:UserInstallation=file://{profile_dir}',
                    '--headless',
                    '--norestore',
                    '--convert-to', 'pdf',
                    '--outdir', output_dir,
                    os.path.abspath(input_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

        if result.returncode != 0:
            raise RuntimeError(
                f'LibreOffice 转换失败:\n{result.stderr or result.stdout}'
            )

        basename = os.path.splitext(os.path.basename(input_path))[0]
        pdf_path = os.path.join(output_dir, basename + '.pdf')
        if not os.path.exists(pdf_path):
            raise RuntimeError(f'转换后未找到 PDF: {pdf_path}')
        return pdf_path
