import os
import shutil
import subprocess
import tempfile

from .base import ConversionBackend


class LibreOfficeBackend(ConversionBackend):
    """使用 LibreOffice headless 将 Office 文档转换为 PDF。"""

    name = 'libreoffice'
    label = 'LibreOffice 无头转换'

    SUPPORTED = {
        '.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt',
        '.odt', '.ods', '.odp', '.rtf', '.txt',
    }

    def __init__(self, soffice_path=None):
        self.soffice = self._find_soffice(soffice_path)

    def _find_soffice(self, custom_path=None):
        if custom_path and os.path.exists(custom_path):
            return custom_path

        system_path = shutil.which('soffice')
        if system_path:
            return system_path

        system_paths = [
            '/usr/bin/soffice',
            '/usr/lib/libreoffice/program/soffice',
            '/opt/libreoffice/program/soffice',
        ]
        for path in system_paths:
            if os.path.exists(path):
                return path

        app_dir = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        portable_paths = [
            os.path.join(app_dir, 'libreoffice_portable', 'program', 'soffice'),
            os.path.join(app_dir, 'libreoffice_portable', 'soffice'),
        ]
        for path in portable_paths:
            if os.path.exists(path):
                return path

        return None

    def suite_installed(self):
        return bool(self.soffice)

    def is_available(self):
        return bool(self.soffice)

    def unavailable_reason(self):
        return '未找到 soffice 可执行文件（请安装 LibreOffice）'

    def convert_to_pdf(self, input_path, output_dir=None):
        ext = os.path.splitext(input_path)[1].lower()
        if ext == '.pdf':
            return input_path

        if not self.soffice:
            raise RuntimeError(self.unavailable_reason())

        output_path = self.build_output_path(input_path, output_dir)
        basename = os.path.splitext(os.path.basename(input_path))[0]

        with tempfile.TemporaryDirectory(prefix='lo_out_') as work_dir, \
                tempfile.TemporaryDirectory(prefix='lo_profile_') as profile_dir:
            result = subprocess.run(
                [
                    self.soffice,
                    '-env:UserInstallation=file://{}'.format(profile_dir),
                    '--headless',
                    '--norestore',
                    '--convert-to', 'pdf',
                    '--outdir', work_dir,
                    os.path.abspath(input_path),
                ],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                raise RuntimeError(
                    'LibreOffice 转换失败:\n{}'.format(
                        result.stderr or result.stdout))

            produced = os.path.join(work_dir, basename + '.pdf')
            if not os.path.exists(produced):
                raise RuntimeError('转换后未找到 PDF: {}'.format(produced))

            shutil.move(produced, output_path)

        return output_path
