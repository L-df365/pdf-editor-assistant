"""打印底座（print_core）。

这一层是「打印」这件事的唯一实现：
主程序打印当前文档、批量打印工具提交队列，走的都是这里的同一套
参数映射、转换、能力校验和错误处理 —— 两边行为不会不一致。

分层：
- jobs.py     PrintJob / PrintOptions（参数与 IPP 属性的映射）
- ranges.py   页码范围解析（1-5,8,10-，以及 1-12d 这种分段模式）
- convert.py  把作业源变成可打印的 PDF（内存文档 / PDF / Word…）
- backend.py  CUPS：能力探测、作业提交、状态查询、取消
- queue.py    批量队列：顺序执行、暂停/继续/取消、状态回调

不依赖 tkinter，也不依赖 PyMuPDF：
只有"打印内存中打开的文档"这条路径才需要 PyMuPDF（由调用方提供文档对象），
独立批量打印工具可以不装 PyMuPDF。
"""

from .errors import PrintError
from .jobs import (PrintJob, PrintOptions, PrintState, SCALING_LABELS,
                   COLOR_LABELS, DUPLEX_LABELS, NUP_LAYOUTS)
from . import backend
from . import convert
from . import ranges
from .queue import PrintQueue

__all__ = [
    'PrintError', 'PrintJob', 'PrintOptions', 'PrintState', 'PrintQueue',
    'print_single', 'print_batch', 'backend', 'convert', 'ranges',
    'SCALING_LABELS', 'COLOR_LABELS', 'DUPLEX_LABELS', 'NUP_LAYOUTS',
]


def _resolve_printer(name=None):
    """确定目标打印机。"""
    if name:
        printer = backend.get_printer(name)
        if printer is None:
            raise PrintError('找不到打印机：{}'.format(name))
        return printer
    printer = backend.default_printer()
    if printer is None:
        raise PrintError('系统里没有可用的打印机')
    return printer


def check_capabilities(printer, options, page_count=0):
    """检查这台打印机能不能按这组参数打。

    不支持就抛 PrintError 并说明原因——**不静默降级**
    （彩色打成黑白、双面打成单面这种"悄悄办了"最招人烦）。
    """
    if printer is None:
        raise PrintError('没有可用的打印机')
    if not printer.online:
        raise PrintError('打印机当前不接收任务（{}）'.format(printer.state_text))
    if not printer.supports_duplex(options.duplex):
        raise PrintError('该打印机不支持{}，可选：{}'.format(
            _duplex_label(options.duplex),
            '、'.join(backend.sides_text(s) for s in printer.sides) or '无'))
    if not printer.supports_color(options.color):
        raise PrintError('该打印机不支持{}'.format(_color_label(options.color)))
    if not printer.supports_media(options.media):
        raise PrintError('该打印机不支持所选纸张')
    if not printer.supports_nup(options.nup):
        raise PrintError('该打印机不支持每张 {} 页'.format(options.nup))


def _duplex_label(mode):
    return {'one': '单面', 'long': '双面长边', 'short': '双面短边'}.get(
        mode, '单双面')


def _color_label(mode):
    return {'color': '彩色', 'mono': '黑白'}.get(mode, '颜色')


def submit_job(job, printer=None, on_event=None, workdir=None):
    """提交一个作业，返回 CUPS 作业号。

    job.source 可以是：
    - PDFDocument 实例：打印的是内存里的当前状态（改了没保存也算数）
    - 路径：PDF 直接用，其它格式先转
    """
    printer = _resolve_printer(printer or getattr(job, 'printer', ''))
    options = job.options
    check_capabilities(printer, options)

    path = None
    try:
        if on_event:
            on_event(job, PrintState.PREPARING, '准备文件')
        path = convert.to_pdf(job, workdir=workdir)

        segments = ranges.parse(options.pages, convert.page_count(job))
        if options.pages and not segments:
            raise PrintError('页码范围超出文档范围（共 {} 页）'.format(
                convert.page_count(job)))
        page_ranges = ranges.to_cups_value(segments)
        if ranges.has_mixed_modes(segments):
            # 同一份文件里混了单双面 → 拆成多个作业（选项是作业级的）
            ids = convert.submit_segments(
                path, segments, printer, options, page_ranges, job, on_event,
                workdir)
            job.job_ids = ids
            return ids[0] if ids else None

        if on_event:
            on_event(job, PrintState.SUBMITTING, '提交中')
        job_id = backend.submit(printer.name, path, job.title(),
                                options.to_cups(page_ranges))
        job.job_ids = [job_id]
        if on_event:
            on_event(job, PrintState.PRINTING, '作业 #{}'.format(job_id))
        return job_id
    finally:
        # CUPS 提交时已经把内容收走了，临时文件可以马上删
        convert.cleanup(path)


def print_single(doc, options=None, printer=None, on_event=None):
    """打印一个（已打开的）文档。

    主程序用这个：打印的是当前编辑状态，不是磁盘上的旧文件。
    """
    job = PrintJob(doc, options=options, printer=printer or '')
    return submit_job(job, printer=printer, on_event=on_event)


def print_batch(jobs, printer=None, on_event=None):
    """按顺序提交一批作业，返回结果列表。

    单个作业失败不影响后面的（失败隔离）。
    """
    results = []
    for job in jobs:
        try:
            job_id = submit_job(job, printer=printer, on_event=on_event)
            results.append({'job': job, 'ok': True, 'job_id': job_id,
                            'error': ''})
        except PrintError as exc:
            job.state = PrintState.FAILED
            job.error = str(exc)
            if on_event:
                on_event(job, PrintState.FAILED, job.error)
            results.append({'job': job, 'ok': False, 'job_id': None,
                            'error': job.error})
        except Exception as exc:
            job.state = PrintState.FAILED
            job.error = str(exc)
            if on_event:
                on_event(job, PrintState.FAILED, job.error)
            results.append({'job': job, 'ok': False, 'job_id': None,
                            'error': job.error})
    return results
