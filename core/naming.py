"""文件命名规则（拆分 / 批量改名的唯一实现）。

界面只负责收参数，真正的命名都在这里：

- 模板：``{name}_{n}`` 这样的占位符
- 表格名单：CSV / TSV / TXT / XLSX 里取一列
- 查找替换（可正则）
- 前缀 / 后缀
- 清理非法字符、限长、同批次与磁盘上的重名去重

不依赖 tkinter，也不依赖 PyMuPDF，方便单独测。
"""

import csv
import datetime
import io
import os
import re

#: 默认命名：原文件名 + 序号
DEFAULT_TEMPLATE = '{name}_{n}'

#: 文件名里不允许的字符（按 Windows 最严的标准来，拷到别的系统也不会坏）
_ILLEGAL = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

#: Windows 的保留设备名，不能当文件名（大小写不敏感）
RESERVED_NAMES = frozenset((
    'con', 'prn', 'aux', 'nul',
    'com1', 'com2', 'com3', 'com4', 'com5', 'com6', 'com7', 'com8', 'com9',
    'lpt1', 'lpt2', 'lpt3', 'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9',
))

#: 模板里允许的占位符（界面上的说明也从这里取）
TOKENS = (
    ('{name}', '原文件名（不含扩展名）'),
    ('{n}', '序号（按「位数」补零）'),
    ('{N}', '序号（不补零）'),
    ('{total}', '文件总数'),
    ('{page}', '这一份的第一页'),
    ('{end}', '这一份的最后一页'),
    ('{range}', '页码范围，如 3-5'),
    ('{date}', '今天，2026-10-27'),
    ('{time}', '现在，143005'),
    ('{ext}', '扩展名（不含点）'),
)

_TOKEN_NAMES = {name.strip('{}') for name, _ in TOKENS}

#: 表格文件支持的类型
TABLE_EXTS = ('.csv', '.tsv', '.txt', '.xlsx', '.xlsm')

#: 列表头名字的默认值（表格里第一行不是表头时，界面上用「第 1 列」）
MAX_STEM = 100

#: 名字（UTF-8）的字节上限：中文一个字 3 字节，光按字数限会超过文件系统的 255
MAX_STEM_BYTES = 200


class NamingError(ValueError):
    """命名规则有问题（模板写错、表格读不出来…）。"""


# --------------------------------------------------------------------------
# 表格名单
# --------------------------------------------------------------------------

class TableData:
    """读出来的表格：全部是字符串，空行已经去掉。"""

    def __init__(self, path, rows, sheet='', sheets=()):
        self.path = path
        self.rows = rows
        self.sheet = sheet
        self.sheets = list(sheets)

    @property
    def headers(self):
        return self.rows[0] if self.rows else []

    @property
    def column_count(self):
        return max((len(row) for row in self.rows), default=0)

    def column_label(self, index):
        return '第 {} 列'.format(index + 1)

    def column_values(self, index=0, has_header=False):
        """取第 index 列的非空值（0 起）。"""
        rows = self.rows[1:] if has_header else self.rows
        values = []
        for row in rows:
            cell = row[index].strip() if index < len(row) else ''
            if cell:
                values.append(cell)
        return values


def _decode(raw):
    """按 utf-8 → GB18030 的顺序解码（政务/工资表常见 GBK）。"""
    for encoding in ('utf-8-sig', 'gb18030'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def _rows_from_text(text, delimiter=None):
    """把文本表格拆成行；没有分隔符时按「一行一个名字」处理。"""
    if delimiter is None:
        sample = text[:4096]
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=',\t;|').delimiter
        except csv.Error:
            delimiter = None
    if delimiter is None:
        lines = [line.strip() for line in text.splitlines()]
        return [[line] for line in lines if line]
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = []
    for row in reader:
        cells = [cell.strip() for cell in row]
        if any(cells):
            rows.append(cells)
    return rows


def _read_text_table(path):
    with open(path, 'rb') as handle:
        raw = handle.read()
    text = _decode(raw)
    ext = os.path.splitext(path)[1].lower()
    delimiter = '\t' if ext == '.tsv' else None
    return _rows_from_text(text, delimiter)


def _read_xlsx(path, sheet=None):
    try:
        import openpyxl
    except ImportError:
        raise NamingError(
            '读取 Excel 表格需要 openpyxl。可以先另存为 CSV 再导入，'
            '或者装上：sudo apt install python3-openpyxl')
    try:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception as exc:
        raise NamingError('这个 Excel 打不开：{}'.format(exc))

    try:
        sheets = list(workbook.sheetnames)
        if sheet and sheet in sheets:
            worksheet = workbook[sheet]
        else:
            worksheet = workbook[sheets[0]]
            sheet = sheets[0]
        rows = []
        for row in worksheet.iter_rows(values_only=True):
            cells = ['' if value is None else str(value).strip()
                     for value in row]
            if any(cells):
                rows.append(cells)
        return rows, sheet, sheets
    finally:
        workbook.close()


def read_table(path, sheet=None):
    """读表格文件，返回 :class:`TableData`。

    支持 CSV / TSV / TXT / XLSX。CSV 里哪一列是名单由调用方决定。
    读不出来抛 :class:`NamingError`。
    """
    ext = os.path.splitext(path)[1].lower()
    if ext not in TABLE_EXTS:
        raise NamingError('表格只支持 {} 这些格式'.format(
            '、'.join(e.lstrip('.').upper() for e in TABLE_EXTS)))
    if not os.path.isfile(path):
        raise NamingError('找不到表格文件：{}'.format(path))

    try:
        if ext in ('.xlsx', '.xlsm'):
            rows, used_sheet, sheets = _read_xlsx(path, sheet)
            return TableData(path, rows, used_sheet, sheets)
        rows = _read_text_table(path)
    except OSError as exc:
        raise NamingError('表格读不出来：{}'.format(exc))
    if not rows:
        raise NamingError('表格是空的')
    return TableData(path, rows)


# --------------------------------------------------------------------------
# 名字清理
# --------------------------------------------------------------------------

def clean_stem(text, max_length=MAX_STEM):
    """清成一个能用的文件名（不含扩展名）。"""
    text = _ILLEGAL.sub('_', str(text))
    text = text.replace('\r', ' ').replace('\n', ' ').strip()
    # 结尾的点和空格在 Windows 上会被系统悄悄吃掉
    text = text.rstrip(' .')
    if not text:
        return 'file'
    if text.split('.')[0].lower() in RESERVED_NAMES:
        text = '_' + text
    if len(text) > max_length:
        text = text[:max_length]
    while len(text.encode('utf-8')) > MAX_STEM_BYTES:
        text = text[:-1]
    text = text.rstrip(' .')
    return text or 'file'


# --------------------------------------------------------------------------
# 命名器
# --------------------------------------------------------------------------

class Namer:
    """把「序号 + 页码 + 名单」变成一组文件名。

    参数都是界面上的那些控件，名字生成是纯函数式的，方便预览。
    """

    def __init__(self, template=DEFAULT_TEMPLATE, start=1, step=1, digits=0,
                 prefix='', suffix='', find='', replace='', regex=False,
                 case='keep', names=(), max_length=MAX_STEM, now=None):
        self.template = template or DEFAULT_TEMPLATE
        self.start = int(start)
        self.step = int(step) or 1
        self.digits = max(int(digits), 0)
        self.prefix = prefix or ''
        self.suffix = suffix or ''
        self.find = find or ''
        self.replace = replace or ''
        self.regex = bool(regex)
        self.case = case or 'keep'
        self.names = list(names or ())
        self.max_length = max_length
        self._now = now

    # -- 模板 ------------------------------------------------------------

    def tokens(self, index, total, first_page, last_page, ext='pdf'):
        """这一份文件可用的占位符取值（页码都是 1 起）。"""
        number = self.start + index * self.step
        now = self._now or datetime.datetime.now()
        rng = str(first_page) if first_page == last_page \
            else '{}-{}'.format(first_page, last_page)
        return {
            'n': str(number).zfill(self.digits),
            'N': str(number),
            'total': str(total),
            'page': str(first_page),
            'end': str(last_page),
            'range': rng,
            'date': now.strftime('%Y-%m-%d'),
            'time': now.strftime('%H%M%S'),
            'ext': ext,
        }

    def _expand(self, template, values, name, ext):
        values = dict(values)
        values['name'] = name
        values['ext'] = ext

        def replace(match):
            key = match.group(1)
            if key not in _TOKEN_NAMES:
                raise NamingError('模板里不认识的占位符：{{{}}}'.format(key))
            return values[key]

        return re.sub(r'\{(\w+)\}', replace, template)

    def _apply_case(self, text):
        if self.case == 'upper':
            return text.upper()
        if self.case == 'lower':
            return text.lower()
        if self.case == 'title':
            return text.title()
        return text

    def _apply_replace(self, text):
        if not self.find:
            return text
        if self.regex:
            try:
                return re.sub(self.find, self.replace, text)
            except re.error as exc:
                raise NamingError('查找规则不是合法的正则：{}'.format(exc))
        return text.replace(self.find, self.replace)

    # -- 生成 ------------------------------------------------------------

    def stem_for(self, source_name, index, total, first_page, last_page,
                 ext='pdf'):
        """生成第 index 份的文件名（不含扩展名）。"""
        source_stem = os.path.splitext(os.path.basename(source_name))[0]
        if index < len(self.names) and str(self.names[index]).strip():
            stem = str(self.names[index]).strip()
            # 名单里常写成「张三.pdf」，扩展名当名字的一部分没意义
            if stem.lower().endswith('.pdf'):
                stem = stem[:-4]
        else:
            values = self.tokens(index, total, first_page, last_page, ext)
            stem = self._expand(self.template, values, source_stem, ext)

        stem = self._apply_replace(stem)
        stem = self._apply_case(stem)
        stem = '{}{}{}'.format(self.prefix, stem, self.suffix)
        return clean_stem(stem, self.max_length)

    def build_names(self, source_name, pages, ext='pdf', reserved=()):
        """按页码范围生成一组不重名的文件名。

        pages     [(第一页, 最后一页), …]，页码 1 起
        reserved  已经占用的文件名（磁盘上已有的），避免直接覆盖
        """
        total = len(pages)
        taken = {os.path.normcase(name) for name in reserved}
        names = []
        for index, (first_page, last_page) in enumerate(pages):
            stem = self.stem_for(source_name, index, total,
                                 first_page, last_page, ext)
            candidate = '{}.{}'.format(stem, ext)
            serial = 1
            while os.path.normcase(candidate) in taken:
                serial += 1
                candidate = '{} ({}).{}'.format(stem, serial, ext)
            taken.add(os.path.normcase(candidate))
            names.append(candidate)
        return names


# --------------------------------------------------------------------------
# 表格名单的快捷用法
# --------------------------------------------------------------------------

def names_from_table(path, column=0, has_header=False, sheet=None):
    """直接读出名单（去掉扩展名、去空行）。"""
    data = read_table(path, sheet=sheet)
    values = data.column_values(int(column), has_header=has_header)
    if not values:
        raise NamingError('这一列没有内容，换个列试试')
    cleaned = []
    for value in values:
        stem = value[:-4] if value.lower().endswith('.pdf') else value
        cleaned.append(clean_stem(stem))
    return cleaned


# --------------------------------------------------------------------------
# 页号：界面上的说法和文件名里的说法要一致
# --------------------------------------------------------------------------

def compact_pages(pages):
    """把页号压成 '3-5, 8'（页码 1 起，连续的合并成区间）。

    拆分的「页码范围」输入框、提取页面的默认文件名共用它，
    预览里写的和写进文件名的才是同一个说法。
    """
    numbers = []
    for page in pages:
        try:
            page = int(page)
        except (TypeError, ValueError):
            raise NamingError('页码要是整数：{!r}'.format(page))
        if page < 1:
            raise NamingError('页码从 1 开始')
        if page not in numbers:
            numbers.append(page)
    numbers.sort()
    parts = []
    start = previous = None
    for page in numbers:
        if start is None:
            start = previous = page
        elif page == previous + 1:
            previous = page
        else:
            parts.append((start, previous))
            start = previous = page
    if start is not None:
        parts.append((start, previous))
    return ', '.join('{}-{}'.format(a, b) if a != b else str(a)
                     for a, b in parts)


def extract_name(source_path, pages, ext='pdf'):
    """提取页面的默认文件名：「报告 第3-5页.pdf」。

    选的页很多（页号写出来太长）时改成「报告 提取12页.pdf」，
    文件名不会被截成一串没意义的数字。
    """
    stem = os.path.basename(source_path or '')
    if stem.lower().endswith('.' + ext):
        stem = stem[:-len(ext) - 1]
    stem = clean_stem(stem or '提取的页面')
    pages = list(pages)
    label = compact_pages(pages)
    if len(label) <= 18:
        return clean_stem('{} 第{}页'.format(stem, label)) + '.' + ext
    return clean_stem('{} 提取{}页'.format(stem, len(pages))) + '.' + ext
