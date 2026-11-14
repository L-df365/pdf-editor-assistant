"""把作业源变成可打印的 PDF。

三种源：
- 内存里打开的文档（PDFDocument）：按**当前状态**导出成临时 PDF
  —— 用户改了顺序、删了页、插了文件，打印出来的必须是改后的版本
- PDF 路径：直接用
- Word/Excel/PPT/图片/文本：走已有的转换后端（WPS 静默 / LibreOffice）
"""

import os
import shutil
import subprocess
import tempfile

from .errors import PrintError

#: 转换后端是按需装的，import 放在函数里，缺了不影响别的路径
_converter = None


def _get_converter():
    global _converter
    if _converter is None:
        from core.converter import DocumentConverter
        _converter = DocumentConverter()
    return _converter


def is_pdf(path):
    return os.path.splitext(path)[1].lower() == '.pdf'


def to_pdf(job, workdir=None):
    """返回可打印的 PDF 路径。

    返回的路径可能是临时文件，用完要 cleanup()；磁盘上的 PDF 会原样
    返回 —— 那份是用户的文件，调用方不能删。
    """
    source = job.source
    if isinstance(source, str):
        path = source
        if not os.path.isfile(path):
            raise PrintError('文件不存在：{}'.format(path))
        if is_pdf(path):
            return path
        return convert_file(path, workdir=workdir)

    # 内存里的文档：按当前状态另存一份
    if not hasattr(source, 'snapshot'):
        raise PrintError('不支持的打印源：{}'.format(type(source).__name__))
    path = temp_path(workdir)
    try:
        source.snapshot(path)
    except Exception as exc:
        cleanup(path)
        raise PrintError('导出当前文档失败：{}'.format(exc))
    return path


def convert_file(path, workdir=None):
    """非 PDF 文件转成 PDF（用已有的转换后端）。"""
    directory = workdir or tempfile.mkdtemp(prefix='pdf_conv_')
    try:
        return _get_converter().convert_to_pdf(path, output_dir=directory)
    except Exception as exc:
        raise PrintError('转换成 PDF 失败：{}'.format(exc))


def grayscale_pdf(path, workdir=None):
    """把 PDF 转成灰度 PDF；工具不全或转换失败时返回 None。

    为什么不交给 CUPS 的「gs 渲染器」：这份车票的中文字体没有内嵌，
    Ghostscript 会拿 DroidSansFallback 顶替，而 GBK 编码里数字 / 字母的
    CID 在替代字体里对不上字形 —— 号码会整段消失（中文却还在）。
    先用 pdftocairo 重新导出：它走 fontconfig 找到系统里的宋体并内嵌，
    再让 gs 只做颜色转换（pdfwrite 不重排文字），数字就不会丢。
    """
    if not (shutil.which('pdftocairo') and shutil.which('gs')):
        return None
    embedded = temp_path(workdir)
    gray = temp_path(workdir)
    try:
        subprocess.run(
            ['pdftocairo', '-pdf', path, embedded],
            check=True, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=300)
        subprocess.run(
            ['gs', '-q', '-dNOPAUSE', '-dBATCH', '-dSAFER',
             '-sDEVICE=pdfwrite',
             '-sColorConversionStrategy=Gray',
             '-dProcessColorModel=/DeviceGray',
             '-o', gray, embedded],
            check=True, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=300)
    except (OSError, subprocess.SubprocessError):
        cleanup(embedded)
        cleanup(gray)
        return None
    cleanup(embedded)
    return gray


def page_count(job):
    """作业源有多少页（转换之前只能给出内存文档的页数）。"""
    source = job.source
    if isinstance(source, str):
        return 0        # 磁盘上的文件：页数要等转完才知道
    return getattr(source, 'page_count', 0)


def temp_path(workdir=None):
    directory = workdir or tempfile.gettempdir()
    handle, path = tempfile.mkstemp(prefix='pdf-print-', suffix='.pdf',
                                     dir=directory)
    os.close(handle)
    return path


def cleanup(path):
    """删掉临时文件（CUPS 提交时已经把内容收走了，提交完就能删）。"""
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        pass


def submit_segments(path, segments, printer, options, page_ranges, job,
                     on_event=None, workdir=None, gray_prepared=False):
    """页码范围里混了单双面模式时：切成多段，每段一个作业。

    CUPS 的单双面是作业级选项，同一份文件里"1-12 双面、13 单面"
    只能拆成两个作业。切出来的 PDF 用 PyMuPDF 做（内存文档本来就带着）。
    """
    from . import backend
    from . import ranges

    ids = []
    # 按模式分组：模式相同、连续的一段合成一个作业
    groups = []
    for start, end, mode in segments:
        if groups and groups[-1][0] == mode:
            groups[-1][1].append((start, end))
        else:
            groups.append((mode, [(start, end)]))

    for mode, parts in groups:
        sub_options = options.copy()
        if mode == ranges.SIMPLEX:
            sub_options.duplex = 'one'
        elif mode == ranges.DUPLEX:
            sub_options.duplex = 'long'
        sub_ranges = ranges.to_cups_value(parts)
        if on_event:
            on_event(job, 'submitting', '提交分段 {}'.format(sub_ranges))
        job_id = backend.submit(printer.name, path, job.title(),
                                sub_options.to_cups(sub_ranges),
                                printer=printer,
                                gray_prepared=gray_prepared)
        ids.append(job_id)
    return ids
