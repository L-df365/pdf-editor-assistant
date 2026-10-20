"""文件类型定义：全应用唯一来源。

界面过滤、插入校验、转换判断都从这里取，避免三处各写一份后互相漂移。
"""

import os

PDF_EXTS = ('.pdf',)
WORD_EXTS = ('.doc', '.docx', '.odt', '.rtf')
EXCEL_EXTS = ('.xls', '.xlsx', '.ods')
PPT_EXTS = ('.ppt', '.pptx', '.odp')
IMAGE_EXTS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tif', '.tiff',
              '.webp')
TEXT_EXTS = ('.txt',)

#: 界面上的分组（顺序即菜单里显示的顺序）
FILE_GROUPS = (
    ('PDF 文档', PDF_EXTS),
    ('Word 文档', WORD_EXTS),
    ('Excel 表格', EXCEL_EXTS),
    ('演示文稿', PPT_EXTS),
    ('图片', IMAGE_EXTS),
    ('文本', TEXT_EXTS),
)

#: 可以作为页面插入的文件
INSERTABLE_EXTS = (PDF_EXTS + WORD_EXTS + EXCEL_EXTS + PPT_EXTS
                   + IMAGE_EXTS + TEXT_EXTS)

#: 需要经过转换引擎（而不是直接插入）的文件
CONVERTIBLE_EXTS = (WORD_EXTS + EXCEL_EXTS + PPT_EXTS + TEXT_EXTS)

#: 类型徽标（文件列表右侧的小标签）
BADGES = {
    'pdf': 'PDF',
    'word': 'Word',
    'excel': 'Excel',
    'slides': '演示',
    'image': '图片',
    'text': '文本',
    'file': '文件',
}


def ext_of(path):
    return os.path.splitext(path)[1].lower()


def kind_of(path):
    """返回文件类别标识：pdf/word/excel/slides/image/text/file。"""
    ext = ext_of(path)
    if ext in PDF_EXTS:
        return 'pdf'
    if ext in WORD_EXTS:
        return 'word'
    if ext in EXCEL_EXTS:
        return 'excel'
    if ext in PPT_EXTS:
        return 'slides'
    if ext in IMAGE_EXTS:
        return 'image'
    if ext in TEXT_EXTS:
        return 'text'
    return 'file'


def badge_of(path):
    return BADGES.get(kind_of(path), BADGES['file'])


def is_insertable(path):
    return ext_of(path) in INSERTABLE_EXTS


def needs_conversion(path):
    return ext_of(path) in CONVERTIBLE_EXTS


def patterns(exts):
    return ' '.join('*' + ext for ext in exts)


def filetypes():
    """tkinter filedialog 用的过滤器列表（最后一项是「所有文件」）。"""
    result = [(name, patterns(exts)) for name, exts in FILE_GROUPS]
    result.append(('所有文件', '*.*'))
    return result


def human_size(size):
    """把字节数写成「1.2 MB」这样。"""
    if not size:
        return '0 B'
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            if unit == 'B':
                return '{:.0f} B'.format(value)
            return '{:.1f} {}'.format(value, unit)
        value /= 1024.0
    return '{:.1f} GB'.format(value)
