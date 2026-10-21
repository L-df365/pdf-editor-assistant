"""页码范围解析。

支持几种常见写法：

    5        第 5 页
    1-5      1 到 5
    10-      10 到末页
    -5       首页到 5
    *        全部
    1-5,8    组合
    1-12d    1-12 页，双面（Firefox 语法，批量打印时用来分段）
    13s      13 页，单面
    14-*d    14 到末页，双面

解析结果统一成 [(起, 止, 模式)]，页码从 1 开始（和 CUPS 一致），
模式 ∈ {None（继承）, 's' 单面, 'd' 双面}。
"""

SEQUENCE = None      # 不指定模式
SIMPLEX = 's'
DUPLEX = 'd'

#: 模式后缀 → 人类可读的说明
MODE_LABELS = {
    None: '默认',
    SIMPLEX: '单面',
    DUPLEX: '双面',
}


class RangeError(ValueError):
    """页码范围写错了。"""


def _parse_one(text, total):
    """解析一段，返回 (起, 止, 模式)。页码从 1 起。"""
    text = text.strip()
    if not text:
        raise RangeError('有一段是空的')

    mode = None
    if text[-1] in (SIMPLEX, DUPLEX):
        mode = text[-1]
        text = text[:-1].strip()
    if not text:
        raise RangeError('只有模式后缀，没有页码')

    if text == '*':
        start, end = 1, total
    elif '-' in text:
        left, _, right = text.partition('-')
        left = left.strip()
        right = right.strip()
        if left:
            start = _to_int(left)
        else:
            start = 1
        if right:
            end = _to_int(right)
        else:
            end = total
        if start > end:
            start, end = end, start
    else:
        start = end = _to_int(text)

    if start < 1:
        raise RangeError('页码从 1 开始')
    return start, end, mode


def _to_int(text):
    try:
        return int(text)
    except ValueError:
        raise RangeError('「{}」不是页码'.format(text))


def parse(text, total=None):
    """解析页码范围。

    text    范围字符串，空或 None 表示全部
    total   文档总页数；给了才会把 "10-" 这样的开区间补齐
    返回 [(起, 止, 模式), ...]；范围为空时返回 []
    """
    if not text:
        return []
    if not isinstance(text, str):
        raise RangeError('页码范围必须是文本')

    segments = []
    for part in text.split(','):
        part = part.strip()
        if not part:
            continue
        start, end, mode = _parse_one(part, total)
        if total:
            start = min(start, total)
            end = min(end, total)
            if start > end:
                continue
        segments.append((start, end, mode))
    return segments


def count_pages(segments):
    """数一共有多少页（重复的页按出现的次数算）。"""
    return sum(end - start + 1 for start, end, _ in segments)


def to_cups_value(segments):
    """转成 CUPS 的 page-ranges 写法：1-3,7,9-。"""
    parts = []
    for start, end, _ in segments:
        if start == end:
            parts.append(str(start))
        else:
            parts.append('{}-{}'.format(start, end))
    return ','.join(parts)


def has_mixed_modes(segments):
    """页码范围里混了不同的单双面模式（要拆成多个作业）。"""
    modes = {mode for _, _, mode in segments}
    return len(modes) > 1


def describe(segments):
    """人话描述：1-12（双面）、13（单面）。"""
    parts = []
    for start, end, mode in segments:
        label = '{}-{}'.format(start, end) if start != end else str(start)
        if mode:
            label += '（{}）'.format(MODE_LABELS.get(mode, mode))
        parts.append(label)
    return '、'.join(parts)
