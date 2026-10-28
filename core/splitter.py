"""把一份 PDF 拆成多个文件。

拆分方式和命名是两件事：

- 拆分方式：每页一份 / 每 N 页一份 / 按页码范围
- 命名规则：见 :mod:`core.naming`

界面先用 :func:`plan_split` 做出「拆成什么、叫什么」的预览，
确认后再用 :func:`split_pdf` 真正写文件 —— 预览和结果走同一份计划，
不会出现「预览一个样、拆出来另一个样」。
"""

import os

import pymupdf

from .naming import Namer
from .print_core import ranges

#: 拆分方式
MODE_PAGE = 'page'        # 每页一份
MODE_CHUNK = 'chunk'      # 每 N 页一份
MODE_RANGES = 'ranges'    # 按页码范围，一段一份

MODE_LABELS = (
    (MODE_PAGE, '每页一份'),
    (MODE_CHUNK, '每 N 页'),
    (MODE_RANGES, '按范围'),
)


class SplitError(ValueError):
    """拆分参数有问题（或者文件打不开）。"""


def count_pages(path):
    """快速数一份 PDF 有几页（不渲染，只读文件结构）。"""
    try:
        document = pymupdf.open(path)
    except Exception as exc:
        raise SplitError('这个文件打不开：{}'.format(exc))
    try:
        return document.page_count
    finally:
        document.close()


class SplitPart:
    """一份输出：页码从 0 起，闭区间。"""

    __slots__ = ('first', 'last')

    def __init__(self, first, last):
        self.first = int(first)
        self.last = int(last)

    @property
    def page(self):
        """第一页（1 起，给人看的）。"""
        return self.first + 1

    @property
    def end(self):
        """最后一页（1 起，含）。"""
        return self.last + 1

    @property
    def count(self):
        return self.last - self.first + 1

    @property
    def label(self):
        if self.page == self.end:
            return '第 {} 页'.format(self.page)
        return '第 {}-{} 页'.format(self.page, self.end)

    def __repr__(self):
        return 'SplitPart({}-{})'.format(self.page, self.end)


def plan_parts(page_count, mode=MODE_PAGE, chunk=1, ranges_text=''):
    """按拆分方式算出每一份的页码范围。

    page_count  总页数
    mode        MODE_PAGE / MODE_CHUNK / MODE_RANGES
    chunk       「每 N 页」的 N
    ranges_text 页码范围（写法同打印：1-3, 4-8, 9-）
    """
    if page_count <= 0:
        raise SplitError('文档里没有页面，没法拆分')

    if mode == MODE_PAGE:
        return [SplitPart(i, i) for i in range(page_count)]

    if mode == MODE_CHUNK:
        try:
            size = int(chunk)
        except (TypeError, ValueError):
            raise SplitError('「每 N 页」的 N 得是数字')
        if size < 1:
            raise SplitError('「每 N 页」的 N 至少是 1')
        parts = []
        first = 0
        while first < page_count:
            parts.append(SplitPart(first, min(first + size - 1,
                                              page_count - 1)))
            first += size
        return parts

    if mode == MODE_RANGES:
        text = (ranges_text or '').strip()
        if not text:
            raise SplitError('按范围拆分要填页码范围，例如 1-3, 4-8')
        try:
            segments = ranges.parse(text, page_count)
        except ranges.RangeError as exc:
            raise SplitError(str(exc))
        if not segments:
            raise SplitError('页码范围内没有有效的页')
        if any(mode_tag is not None for _, _, mode_tag in segments):
            raise SplitError('拆分不用写单双面后缀（s / d）')
        return [SplitPart(start - 1, end - 1) for start, end, _ in segments]

    raise SplitError('不认识的拆分方式：{}'.format(mode))


class SplitPlan:
    """拆分的完整计划：拆成几份、每份哪几页、每份叫什么。"""

    def __init__(self, source_name, page_count, out_dir, parts, names,
                 overwrite=False):
        self.source_name = source_name
        self.page_count = page_count
        self.out_dir = out_dir
        self.parts = list(parts)
        self.names = list(names)
        self.overwrite = bool(overwrite)

    @property
    def total(self):
        return len(self.parts)

    def entries(self):
        """[(序号, 页码范围, 文件名), …]，预览表格直接用。"""
        return [(i + 1, part.label, name)
                for i, (part, name) in enumerate(zip(self.parts, self.names))]

    def path_for(self, name):
        return os.path.join(self.out_dir, name)


def _existing_names(out_dir):
    try:
        return [name for name in os.listdir(out_dir)
                if os.path.isfile(os.path.join(out_dir, name))]
    except OSError:
        return []


def plan_split(page_count, source_name, out_dir, mode=MODE_PAGE, chunk=1,
               ranges_text='', namer=None, overwrite=False):
    """生成拆分计划（不写任何文件）。

    overwrite=False 时会把输出目录里已有的同名文件让开 —— 加 (2)，
    不会默默覆盖用户已有的文件。
    """
    if not out_dir:
        raise SplitError('还没有选输出位置')
    parts = plan_parts(page_count, mode, chunk, ranges_text)
    namer = namer or Namer()
    reserved = () if overwrite else _existing_names(out_dir)
    pages = [(part.page, part.end) for part in parts]
    try:
        names = namer.build_names(source_name, pages, reserved=reserved)
    except Exception as exc:
        raise SplitError(str(exc))
    return SplitPlan(source_name, page_count, out_dir, parts, names,
                     overwrite=overwrite)


class SplitReport:
    """拆分结果：成功的文件、失败的条目。"""

    def __init__(self, plan, paths, failures):
        self.plan = plan
        self.paths = list(paths)
        self.failures = list(failures)   # [(文件名, 错误说明), …]

    @property
    def ok(self):
        return not self.failures

    @property
    def count(self):
        return len(self.paths)

    @property
    def out_dir(self):
        return self.plan.out_dir


def split_pdf(source_path, plan, progress=None):
    """按计划写文件。

    progress(done, total, name) 每写完一份回调一次（在调用线程里）。
    单份失败不会中断其余文件，失败条目收集在 report.failures 里。
    """
    try:
        source = pymupdf.open(source_path)
    except Exception as exc:
        raise SplitError('这个文件打不开：{}'.format(exc))
    try:
        if source.page_count != plan.page_count:
            raise SplitError(
                '页数和预览时不一样了（现在 {} 页，预览时 {} 页），请重新打开'
                .format(source.page_count, plan.page_count))
        try:
            os.makedirs(plan.out_dir, exist_ok=True)
        except OSError as exc:
            raise SplitError('建不了输出目录：{}'.format(exc))

        paths = []
        failures = []
        total = plan.total
        for index, (part, name) in enumerate(zip(plan.parts, plan.names)):
            dest = plan.path_for(name)
            out = pymupdf.open()
            try:
                out.insert_pdf(source, from_page=part.first, to_page=part.last)
                out.save(dest, garbage=3, deflate=True)
                paths.append(dest)
            except Exception as exc:
                failures.append((name, str(exc)))
            finally:
                out.close()
            if progress:
                progress(index + 1, total, name)
        return SplitReport(plan, paths, failures)
    finally:
        source.close()
