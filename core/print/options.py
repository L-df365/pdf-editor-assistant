"""打印参数。

界面上的每一项都对应一个 IPP 作业属性，CUPS 那边原生支持：
颜色、单双面、份数、纸张、缩放、N-up、页码范围。

字段用空值表示"不指定"，提交时不下发该属性（用打印机的默认值）。
批量打印里的"公共默认 + 单文件覆盖"也基于这个语义：
未覆盖的字段留空，覆盖的字段填值。
"""

#: 缩放方式 → CUPS print-scaling
SCALING_LABELS = (
    ('', '打印机默认'),
    ('auto-fit', '适合页面'),
    ('fit', '缩小到可打印区域'),
    ('fill', '填满页面'),
    ('none', '实际大小'),
)

#: 颜色 → CUPS print-color-mode
COLOR_LABELS = (
    ('', '按打印机默认'),
    ('color', '彩色'),
    ('mono', '黑白'),
)

#: 单双面 → CUPS sides
DUPLEX_LABELS = (
    ('', '按打印机默认'),
    ('one', '单面'),
    ('long', '双面（长边翻页）'),
    ('short', '双面（短边翻页）'),
)

#: N-up 版式 → CUPS number-up-layout
NUP_LAYOUTS = (
    ('btlr', '从左到右、从上到下'),
    ('btrl', '从左到右、从下到上'),
    ('lrbt', '从左到右、先竖后横'),
    ('lrtb', '从左到右、先横后竖'),
    ('rlbt', '从右到左、先竖后横'),
    ('rltb', '从右到左、先横后竖'),
    ('tblr', '从上到下、从左到右'),
    ('tbrl', '从上到下、从右到左'),
)


class PrintOptions:
    """一组打印参数。空字符串/None = 不指定。"""

    __slots__ = ('pages', 'copies', 'media', 'scaling', 'color', 'duplex',
                 'nup', 'nup_layout')

    def __init__(self, pages='', copies=1, media='', scaling='', color='',
                 duplex='', nup=1, nup_layout=''):
        self.pages = pages or ''
        self.copies = int(copies or 1)
        self.media = media or ''
        self.scaling = scaling or ''
        self.color = color or ''
        self.duplex = duplex or ''
        self.nup = int(nup or 1)
        self.nup_layout = nup_layout or ''

    def copy(self):
        return PrintOptions(self.pages, self.copies, self.media, self.scaling,
                            self.color, self.duplex, self.nup, self.nup_layout)

    def is_default(self):
        """除了份数之外都没设置 = 没改过。"""
        return not any((self.pages, self.media, self.scaling, self.color,
                        self.duplex)) and self.nup <= 1

    # -- 与打印机的能力对照 ------------------------------------------

    def sides(self):
        """把单双面翻成 CUPS 的 sides 值。"""
        return {
            'one': 'one-sided',
            'long': 'two-sided-long-edge',
            'short': 'two-sided-short-edge',
        }.get(self.duplex, '')

    def color_mode(self):
        return {'color': 'color', 'mono': 'monochrome'}.get(self.color, '')

    # -- 提交 --------------------------------------------------------

    def to_cups(self, page_ranges=''):
        """转成 CUPS 作业属性。

        page_ranges 是已经算好的页码范围（CUPS 的 page-ranges），
        没指定页范围时传空串 = 全部页。
        """
        options = {}
        if page_ranges:
            options['page-ranges'] = page_ranges
        if self.copies > 1:
            options['copies'] = str(self.copies)
        if self.media:
            options['media'] = self.media
        if self.scaling:
            options['print-scaling'] = self.scaling
        color = self.color_mode()
        if color:
            options['print-color-mode'] = color
        sides = self.sides()
        if sides:
            options['sides'] = sides
        if self.nup and self.nup > 1:
            options['number-up'] = str(self.nup)
            if self.nup_layout:
                options['number-up-layout'] = self.nup_layout
        return options

    def summary(self):
        """一句话说明这组参数（界面上给用户看）。"""
        parts = []
        if self.color:
            parts.append('彩色' if self.color == 'color' else '黑白')
        if self.duplex:
            parts.append({'one': '单面', 'long': '双面长边',
                          'short': '双面短边'}[self.duplex])
        if self.media:
            parts.append(self.media)
        if self.nup > 1:
            parts.append('{} 页/张'.format(self.nup))
        if self.copies > 1:
            parts.append('{} 份'.format(self.copies))
        if self.scaling:
            parts.append(dict(SCALING_LABELS).get(self.scaling, ''))
        return ' · '.join(p for p in parts if p)
