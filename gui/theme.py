"""设计系统：令牌与 ttk 主题。

方向「样张台」：冷中性台面 + 墨青交互色 + 琥珀标记色。
所有界面颜色、字体、间距从本模块取，禁止在组件里再写死色值。

用法::

    root = tk.Tk()
    init_theme(root)          # 必须在创建任何控件之前调用
"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

# --------------------------------------------------------------------------
# 颜色
# --------------------------------------------------------------------------

BG = '#EDF0EF'          # 应用底色（冷中性台面）
SURFACE = '#F7F9F8'     # 面板 / 标题条 / 工具条
PAPER = '#FFFFFF'       # 纸张：页面卡、输入框、弹层
STAGE = '#D8DEDD'       # 预览台面（比 surface 深一档，让白纸浮起来）
LINE = '#D3D9D7'        # 1px 分隔线、卡片描边
LINE_SOFT = '#E3E8E6'   # 更弱的分隔、滚动条轨道
SCROLL_THUMB = '#C2CAC8'  # 滚动条滑块：比 LINE 深一档，浅色底上也要看得见
#: 页面在台面上的投影（由深到浅三层）
SHADOW_TONES = ('#C3CBC9', '#CCD3D1', '#D3D9D7')
INK = '#1B2321'         # 主文字
INK_2 = '#586460'       # 次要文字
INK_3 = '#8B9693'       # 三级 / 禁用（不用于正文）
ACCENT = '#0F7368'      # 墨青：主操作、焦点、链接
ACCENT_DEEP = '#0A544C'  # hover / press
ACCENT_TINT = '#E2EFEC'  # 选中底、标签底
MARKER = '#E9A62A'      # 荧光琥珀：仅「当前页 / 进行中」标记
MARKER_INK = '#8A5A00'  # 琥珀底上的文字
DANGER = '#B4462F'      # 删除、破坏性动作
DANGER_DEEP = '#8F3524'  # 危险按钮按下
DANGER_TINT = '#F8E7E3'  # 危险项悬停底
OK = '#2F7D5B'         # 已保存、状态点「可用」


# --------------------------------------------------------------------------
# 字体
# --------------------------------------------------------------------------

UI_FAMILIES = (
    'Noto Sans CJK SC', 'Source Han Sans SC', 'Microsoft YaHei',
    'WenQuanYi Micro Hei', 'DejaVu Sans',
)
DISPLAY_FAMILIES = (
    'Noto Serif CJK SC', 'Source Han Serif SC', 'STSong', 'SimSun',
    'DejaVu Serif',
)
MONO_FAMILIES = (
    'Noto Sans Mono CJK SC', 'Noto Sans Mono', 'DejaVu Sans Mono',
    'Liberation Mono',
)

UI_FONT = 'TkDefaultFont'
DISPLAY_FONT = 'TkDefaultFont'
NUM_FONT = 'TkFixedFont'

SIZE = {
    'display': 18,   # 空状态主标题（全应用仅此一处）
    'h1': 13,        # 面板 / 弹层标题、文档名
    'h2': 11,        # 区块标题、按钮
    'body': 10,      # 正文、菜单项、输入
    'meta': 9,       # 说明文字、次要标签
    'num': 9,        # 页码、页数、比例、尺寸
}


def _first_available(families, candidates):
    for name in candidates:
        if name in families:
            return name
    return None


def font(kind='body', weight=''):
    """返回 tk 字体元组。kind: display/h1/h2/body/meta/num。"""
    if kind == 'display':
        family, size = DISPLAY_FONT, SIZE['display']
    elif kind == 'num':
        family, size = NUM_FONT, SIZE['num']
    else:
        family, size = UI_FONT, SIZE.get(kind, SIZE['body'])
    if weight:
        return (family, size, weight)
    return (family, size)


# --------------------------------------------------------------------------
# 间距 / 圆角 / 光标
# --------------------------------------------------------------------------

SPACE = {'xs': 4, 'sm': 8, 'md': 12, 'lg': 16, 'xl': 24, 'xxl': 32}
# --------------------------------------------------------------------------
# 主题
# --------------------------------------------------------------------------

def _set(style, name, **options):
    """逐项设置样式选项，忽略当前主题不支持的项。"""
    for key, value in options.items():
        try:
            style.configure(name, **{key: value})
        except tk.TclError:
            pass


def _map(style, name, **options):
    for key, value in options.items():
        try:
            style.map(name, **{key: value})
        except tk.TclError:
            pass


def _apply_named_fonts(root):
    pairs = (
        ('TkDefaultFont', UI_FONT, SIZE['body'], 'normal'),
        ('TkTextFont', UI_FONT, SIZE['body'], 'normal'),
        ('TkMenuFont', UI_FONT, SIZE['body'], 'normal'),
        ('TkHeadingFont', UI_FONT, SIZE['h2'], 'bold'),
        ('TkCaptionFont', UI_FONT, SIZE['meta'], 'normal'),
        ('TkSmallCaptionFont', UI_FONT, SIZE['meta'], 'normal'),
        ('TkIconFont', UI_FONT, SIZE['body'], 'normal'),
        ('TkTooltipFont', UI_FONT, SIZE['meta'], 'normal'),
        ('TkFixedFont', NUM_FONT, SIZE['num'], 'normal'),
    )
    for name, family, size, weight in pairs:
        try:
            tkfont.nametofont(name).configure(family=family, size=size,
                                              weight=weight)
        except tk.TclError:
            pass


def _configure_menus(root):
    """所有 tk.Menu 继承同一套外观（标题栏菜单、右键菜单、弹出菜单）。"""
    root.option_add('*tearOff', False)
    root.option_add('*Menu.tearOff', False)
    root.option_add('*Menu.font', (UI_FONT, SIZE['body']))
    root.option_add('*Menu.background', PAPER)
    root.option_add('*Menu.foreground', INK)
    root.option_add('*Menu.activeBackground', ACCENT_TINT)
    root.option_add('*Menu.activeForeground', INK)
    root.option_add('*Menu.activeBorderWidth', 0)
    root.option_add('*Menu.disabledForeground', INK_3)
    root.option_add('*Menu.borderWidth', 1)
    root.option_add('*Menu.relief', 'solid')
    root.option_add('*Menu.background', SURFACE)
    root.option_add('*Menu.accelerator', INK_3)


def _configure_lists(root):
    """下拉列表（Combobox 的候选列表）也用同一套配色。"""
    root.option_add('*Listbox.background', PAPER)
    root.option_add('*Listbox.foreground', INK)
    root.option_add('*Listbox.selectBackground', ACCENT_TINT)
    root.option_add('*Listbox.selectForeground', INK)
    root.option_add('*Listbox.borderWidth', 1)
    root.option_add('*Listbox.font', (UI_FONT, SIZE['body']))


def _configure_styles(style):
    # 底板
    _set(style, 'TFrame', background=BG)
    _set(style, 'Surface.TFrame', background=SURFACE)
    _set(style, 'Paper.TFrame', background=PAPER)
    _set(style, 'Stage.TFrame', background=STAGE)
    _set(style, 'TPanedwindow', background=BG)
    _set(style, 'TNotebook', background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))

    # 文字
    _set(style, 'TLabel', background=BG, foreground=INK,
         font=font('body'))
    _set(style, 'Surface.TLabel', background=SURFACE, foreground=INK,
         font=font('body'))
    _set(style, 'Paper.TLabel', background=PAPER, foreground=INK,
         font=font('body'))
    _set(style, 'Stage.TLabel', background=STAGE, foreground=INK,
         font=font('body'))
    _set(style, 'Title.TLabel', background=SURFACE, foreground=INK,
         font=font('h1', 'bold'))
    _set(style, 'Muted.TLabel', background=BG, foreground=INK_2,
         font=font('meta'))
    _set(style, 'Num.TLabel', background=BG, foreground=INK_2,
         font=font('num'))
    _set(style, 'Danger.TLabel', background=BG, foreground=DANGER,
         font=font('body'))

    # 按钮：三档
    _set(style, 'TButton', background=SURFACE, foreground=INK,
         bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
         relief='flat', focuscolor=ACCENT, borderwidth=1,
         padding=(SPACE['md'], SPACE['xs']), anchor='center',
         font=font('body'))
    _map(style, 'TButton',
         background=[('disabled', BG), ('pressed', LINE_SOFT),
                     ('active', LINE_SOFT)],
         foreground=[('disabled', INK_3)],
         bordercolor=[('focus', ACCENT)])

    _set(style, 'Primary.TButton', background=ACCENT, foreground=PAPER,
         bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
         relief='flat', focuscolor=ACCENT, borderwidth=1,
         padding=(SPACE['lg'], SPACE['xs']), anchor='center',
         font=font('body', 'bold'))
    _map(style, 'Primary.TButton',
         background=[('disabled', LINE), ('pressed', ACCENT_DEEP),
                     ('active', ACCENT_DEEP)],
         foreground=[('disabled', INK_3), ('active', PAPER)],
         bordercolor=[('focus', ACCENT)])

    _set(style, 'Ghost.TButton', background=BG, foreground=INK_2,
         borderwidth=0, relief='flat', focuscolor=ACCENT,
         padding=(SPACE['sm'], SPACE['xs']), anchor='center',
         font=font('body'))
    _map(style, 'Ghost.TButton',
         background=[('disabled', BG), ('pressed', LINE_SOFT),
                     ('active', ACCENT_TINT)],
         foreground=[('disabled', INK_3), ('active', INK)])

    _set(style, 'Danger.TButton', background=BG, foreground=DANGER,
         borderwidth=0, relief='flat', focuscolor=ACCENT,
         padding=(SPACE['sm'], SPACE['xs']), anchor='center',
         font=font('body'))
    _map(style, 'Danger.TButton',
         background=[('disabled', BG), ('pressed', LINE_SOFT),
                     ('active', ACCENT_TINT)],
         foreground=[('disabled', INK_3), ('active', DANGER)])

    # 顶栏次级按钮：带 1px 描边，一眼看出可点
    _set(style, 'Surface.Secondary.TButton', background=PAPER,
         foreground=INK, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
         relief='flat', focuscolor=ACCENT, borderwidth=1,
         padding=(SPACE['md'], 4), anchor='center', font=font('body'))
    _map(style, 'Surface.Secondary.TButton',
         background=[('disabled', SURFACE), ('pressed', LINE_SOFT),
                     ('active', ACCENT_TINT)],
         foreground=[('disabled', INK_3), ('active', INK)],
         bordercolor=[('disabled', LINE_SOFT), ('focus', ACCENT)])

    # 表面变体：与所在面板同色，避免出现灰色方块
    _set(style, 'Surface.Ghost.TButton', background=SURFACE,
         foreground=INK_2, borderwidth=0, relief='flat', focuscolor=ACCENT,
         padding=(SPACE['sm'], SPACE['xs']), anchor='center',
         font=font('body'))
    _map(style, 'Surface.Ghost.TButton',
         background=[('disabled', SURFACE), ('pressed', LINE_SOFT),
                     ('active', ACCENT_TINT)],
         foreground=[('disabled', INK_3), ('active', INK)])

    _set(style, 'Surface.Danger.TButton', background=SURFACE,
         foreground=DANGER, borderwidth=0, relief='flat', focuscolor=ACCENT,
         padding=(SPACE['sm'], SPACE['xs']), anchor='center',
         font=font('body'))
    _map(style, 'Surface.Danger.TButton',
         background=[('disabled', SURFACE), ('pressed', LINE_SOFT),
                     ('active', ACCENT_TINT)],
         foreground=[('disabled', INK_3), ('active', DANGER)])

    _set(style, 'Paper.Ghost.TButton', background=PAPER, foreground=INK_2,
         borderwidth=0, relief='flat', focuscolor=ACCENT,
         padding=(SPACE['sm'], SPACE['xs']), anchor='center',
         font=font('body'))
    _map(style, 'Paper.Ghost.TButton',
         background=[('disabled', PAPER), ('pressed', LINE_SOFT),
                     ('active', ACCENT_TINT)],
         foreground=[('disabled', INK_3), ('active', INK)])

    _set(style, 'Paper.Danger.TButton', background=PAPER, foreground=DANGER,
         borderwidth=0, relief='flat', focuscolor=ACCENT,
         padding=(SPACE['sm'], SPACE['xs']), anchor='center',
         font=font('body'))
    _map(style, 'Paper.Danger.TButton',
         background=[('disabled', PAPER), ('pressed', LINE_SOFT),
                     ('active', ACCENT_TINT)],
         foreground=[('disabled', INK_3), ('active', DANGER)])

    # 分段控件（缩放档位）
    _set(style, 'Segment.TButton', background=SURFACE, foreground=INK_2,
         borderwidth=0, relief='flat', focuscolor=ACCENT,
         padding=(SPACE['sm'], 2), anchor='center', font=font('meta'))
    _map(style, 'Segment.TButton',
         background=[('pressed', LINE_SOFT), ('active', ACCENT_TINT)],
         foreground=[('active', INK)])
    _set(style, 'SegmentOn.TButton', background=ACCENT_TINT,
         foreground=ACCENT, borderwidth=0, relief='flat', focuscolor=ACCENT,
         padding=(SPACE['sm'], 2), anchor='center',
         font=font('meta', 'bold'))
    _map(style, 'SegmentOn.TButton',
         background=[('pressed', LINE_SOFT), ('active', ACCENT_TINT)])

    _set(style, 'Paper.Primary.TButton', background=ACCENT, foreground=PAPER,
         bordercolor=ACCENT, lightcolor=ACCENT, darkcolor=ACCENT,
         relief='flat', focuscolor=ACCENT, borderwidth=1,
         padding=(SPACE['lg'], 7), anchor='center', font=font('body', 'bold'))
    _map(style, 'Paper.Primary.TButton',
         background=[('disabled', LINE), ('pressed', ACCENT_DEEP),
                     ('active', ACCENT_DEEP)],
         foreground=[('disabled', INK_3), ('active', PAPER)])

    _set(style, 'Paper.Secondary.TButton', background=PAPER, foreground=INK,
         bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, relief='flat',
         focuscolor=ACCENT, borderwidth=1, padding=(SPACE['md'], 5),
         anchor='center', font=font('body'))
    _map(style, 'Paper.Secondary.TButton',
         background=[('disabled', PAPER), ('pressed', LINE_SOFT),
                     ('active', ACCENT_TINT)],
         foreground=[('disabled', INK_3), ('active', INK)])

    _set(style, 'Paper.Segment.TButton', background=PAPER, foreground=INK_2,
         borderwidth=0, relief='flat', focuscolor=ACCENT,
         padding=(SPACE['sm'], 3), anchor='center', font=font('meta'))
    _map(style, 'Paper.Segment.TButton',
         background=[('pressed', LINE_SOFT), ('active', ACCENT_TINT)],
         foreground=[('active', INK)])
    _set(style, 'Paper.SegmentOn.TButton', background=ACCENT_TINT,
         foreground=ACCENT, borderwidth=0, relief='flat', focuscolor=ACCENT,
         padding=(SPACE['sm'], 3), anchor='center',
         font=font('meta', 'bold'))
    _map(style, 'Paper.SegmentOn.TButton',
         background=[('pressed', LINE_SOFT), ('active', ACCENT_TINT)])

    # 输入
    _set(style, 'TEntry', fieldbackground=PAPER, background=PAPER,
         foreground=INK, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
         insertcolor=INK, relief='flat', padding=SPACE['sm'])
    _map(style, 'TEntry', bordercolor=[('focus', ACCENT)])
    _set(style, 'TCombobox', fieldbackground=PAPER, background=SURFACE,
         foreground=INK, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
         arrowcolor=INK_2, relief='flat', padding=(SPACE['sm'], 3))
    _map(style, 'TCombobox',
         fieldbackground=[('readonly', PAPER)],
         bordercolor=[('focus', ACCENT)],
         arrowcolor=[('active', ACCENT)])

    # 选择
    _set(style, 'TCheckbutton', background=BG, foreground=INK,
         focuscolor=ACCENT, font=font('body'))
    _set(style, 'TRadiobutton', background=BG, foreground=INK,
         focuscolor=ACCENT, font=font('body'))
    _set(style, 'Surface.TCheckbutton', background=SURFACE, foreground=INK,
         focuscolor=ACCENT, font=font('body'))
    _set(style, 'Surface.TRadiobutton', background=SURFACE, foreground=INK,
         focuscolor=ACCENT, font=font('body'))
    _set(style, 'Paper.TCheckbutton', background=PAPER, foreground=INK,
         focuscolor=ACCENT, font=font('body'))
    _set(style, 'Paper.TRadiobutton', background=PAPER, foreground=INK,
         focuscolor=ACCENT, font=font('body'))
    # 指示器：纸白底 + 墨青勾
    for name in ('TCheckbutton', 'TRadiobutton', 'Paper.TRadiobutton'):
        _set(style, name, indicatorbackground=PAPER,
             indicatorforeground=ACCENT, upperbordercolor=LINE,
             lowerbordercolor=LINE, indicatorsize=11, indicatormargin=1)

    # 分隔线
    _set(style, 'TSeparator', background=LINE)
    _set(style, 'Horizontal.TSeparator', background=LINE)
    _set(style, 'Vertical.TSeparator', background=LINE)

    # 滚动条：无箭头细条
    # 滚动条：不要设 arrowsize=0 —— clam 主题的宽度是由箭头决定的，
    # 去掉箭头会把滚动条压成 1px（看上去就是"滚动条没了"）。
    _set(style, 'Vertical.TScrollbar', background=SCROLL_THUMB, troughcolor=BG,
         bordercolor=BG, lightcolor=SCROLL_THUMB, darkcolor=SCROLL_THUMB,
         arrowcolor=INK_3, borderwidth=0, relief='flat')
    _map(style, 'Vertical.TScrollbar',
         background=[('pressed', INK_2), ('active', INK_3)])
    _set(style, 'Horizontal.TScrollbar', background=SCROLL_THUMB,
         troughcolor=BG, bordercolor=BG, lightcolor=SCROLL_THUMB,
         darkcolor=SCROLL_THUMB, arrowcolor=INK_3, borderwidth=0, relief='flat')
    _map(style, 'Horizontal.TScrollbar',
         background=[('pressed', INK_2), ('active', INK_3)])

    # 进度
    _set(style, 'Horizontal.TProgressbar', background=ACCENT,
         troughcolor=LINE_SOFT, bordercolor=LINE_SOFT, lightcolor=ACCENT,
         darkcolor=ACCENT, borderwidth=0, thickness=4, relief='flat')

    # 列表 / 树
    _set(style, 'Treeview', background=PAPER, fieldbackground=PAPER,
         foreground=INK, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
         rowheight=26, font=font('body'))
    _set(style, 'Paper.Treeview', background=PAPER, fieldbackground=PAPER,
         foreground=INK, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
         rowheight=26, font=font('body'))
    _set(style, 'Paper.Treeview.Heading', background=SURFACE,
         foreground=INK, bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
         relief='flat', font=font('meta', 'bold'), borderwidth=1)
    _set(style, 'Treeview.Heading', background=SURFACE, foreground=INK_2,
         bordercolor=LINE, lightcolor=LINE, darkcolor=LINE,
         relief='flat', font=font('meta', 'bold'))


def init_theme(root):
    """初始化设计系统。必须在创建任何控件之前调用。"""
    global UI_FONT, DISPLAY_FONT, NUM_FONT

    families = set(tkfont.families(root))
    UI_FONT = _first_available(families, UI_FAMILIES) or 'TkDefaultFont'
    DISPLAY_FONT = (_first_available(families, DISPLAY_FAMILIES)
                    or UI_FONT)
    NUM_FONT = _first_available(families, MONO_FAMILIES) or 'TkFixedFont'

    _apply_named_fonts(root)
    _configure_menus(root)
    _configure_lists(root)

    style = ttk.Style(root)
    if 'clam' in style.theme_names():
        style.theme_use('clam')
    _configure_styles(style)
    style_scrollbars(style)

    try:
        root.configure(background=BG)
    except tk.TclError:
        pass
    return style


def style_scrollbars(style):
    """把系统滚动条换成我们的配色。

    注意：不要自建带 layout 的样式 —— 那样 ttk 会把它算成 1px 宽
    （等于看不见）。直接改内置样式，宽度保持系统的 14px。
    """
    for orient in ('Vertical', 'Horizontal'):
        name = '{}.TScrollbar'.format(orient)
        try:
            style.configure(
                name,
                troughcolor=BG,
                bordercolor=BG,
                lightcolor=BG,
                darkcolor=BG,
                background=SCROLL_THUMB,
                borderwidth=0,
                relief='flat',
                arrowcolor=INK_3,
            )
            style.map(
                name,
                background=[('active', INK_3), ('pressed', INK_2)],
                bordercolor=[('active', BG)],
                lightcolor=[('active', BG)],
                darkcolor=[('active', BG)],
            )
        except tk.TclError:
            continue
    return style
