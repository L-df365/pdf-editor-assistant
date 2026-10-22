"""自绘圆角按钮。

ttk 画不出圆角（clam 主题只有方角），所以可见的操作按钮统一用这个：
纸面填充 / 1px 细线 / 墨青主色 / 悬停与按下反馈 / 焦点环。
"""

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from gui.draw import rounded_photo
from gui.theme import (ACCENT, ACCENT_DEEP, ACCENT_TINT, DANGER, DANGER_DEEP,
                        DANGER_TINT, INK, INK_2, INK_3, LINE, PAPER, font)

RADIUS = 6
PAD_X = 12
PAD_Y = 4

# 变体: (填充, 描边, 文字, 悬停填充, 悬停文字)
VARIANTS = {
    'primary': (ACCENT, ACCENT, PAPER, ACCENT_DEEP, PAPER),
    'secondary': (PAPER, LINE, INK, ACCENT_TINT, INK),
    'ghost': ('', '', INK_2, ACCENT_TINT, INK),
    'danger': ('', '', DANGER, DANGER_TINT, DANGER),
    'danger-solid': (DANGER, DANGER, PAPER, DANGER_DEEP, PAPER),
    'menu': ('', '', INK, ACCENT_TINT, INK),
    'segment': ('', '', INK_2, ACCENT_TINT, INK),
    'segment-on': (ACCENT_TINT, '', ACCENT, ACCENT_TINT, ACCENT),
}


def bg_of(parent, fallback=PAPER):
    """取父容器的背景色（ttk 控件没有 -bg 选项）。

    ttk 容器取不到 -bg，就退回 fallback（调用方一般会显式给 bg）。
    """
    try:
        return parent.cget('bg')
    except tk.TclError:
        return fallback


# --------------------------------------------------------------------------
# 字体度量缓存
#
# font.metrics() / font.measure() 每调一次都要问一遍字体服务，单次 3~4ms。
# 一个按钮要量三四次，二十几个按钮就是几百毫秒 —— 启动明显发顿。
# 字体规格和文字都是有限的，缓存住即可。
# --------------------------------------------------------------------------

_FONT_CACHE = {}
_METRIC_CACHE = {}
_WIDTH_CACHE = {}


def _font_object(spec):
    obj = _FONT_CACHE.get(spec)
    if obj is None:
        obj = tkfont.Font(font=spec)
        _FONT_CACHE[spec] = obj
    return obj


def font_metric(spec, kind):
    key = (spec, kind)
    value = _METRIC_CACHE.get(key)
    if value is None:
        value = _font_object(spec).metrics(kind)
        _METRIC_CACHE[key] = value
    return value


def text_width(spec, text):
    key = (spec, text)
    value = _WIDTH_CACHE.get(key)
    if value is None:
        value = _font_object(spec).measure(text)
        _WIDTH_CACHE[key] = value
    return value


class FlatButton(tk.Canvas):
    """圆角按钮。"""

    def __init__(self, parent, text, command=None, variant='secondary',
                 icon='', bg=None, width=None, state='normal'):
        super().__init__(parent, highlightthickness=0, bd=0,
                         bg=bg or bg_of(parent))
        self._text = text
        self._icon = icon
        self._command = command
        self._variant = variant
        self._state = state
        self._hover = False
        self._pressed = False
        self._focus = False
        self._width = width
        self._font_spec = font('body')
        self._icon_font_spec = font('body', 'bold')
        self._font = tkfont.Font(font=self._font_spec)
        self._icon_font = tkfont.Font(font=self._icon_font_spec)
        self.bind('<Configure>', lambda e: self._redraw())
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)
        self.bind('<FocusIn>', self._on_focus_in)
        self.bind('<FocusOut>', self._on_focus_out)
        self.bind('<Return>', self._on_key)
        self.bind('<space>', self._on_key)
        self._redraw()

    # -- 状态 ----------------------------------------------------------

    def configure_state(self, enabled=True):
        self._state = 'normal' if enabled else 'disabled'
        self.configure(cursor='hand2' if enabled else 'arrow')
        self._redraw()
        return self

    def configure(self, **kwargs):
        """Canvas 没有"禁用"这个状态，得自己接住。

        不接的话 configure(state='disabled') 只会去改 Canvas 的 state，
        按钮既不变灰、也照样能点（撤销/重做就是这样失效的）。
        """
        if 'state' in kwargs:
            state = kwargs.pop('state')
            enabled = state not in ('disabled', 'active')
            self.configure_state(enabled)
        if kwargs:
            return super().configure(**kwargs)
        return self

    def set_text(self, text):
        self._text = text
        self._redraw()
        return self

    def set_command(self, command):
        self._command = command
        return self

    def set_variant(self, variant):
        self._variant = variant
        self._redraw()
        return self

    def _on_enter(self, event=None):
        self._hover = True
        self._redraw()

    def _on_leave(self, event=None):
        self._hover = False
        self._pressed = False
        self._redraw()

    def _on_press(self, event=None):
        if self._state != 'normal':
            return
        self._pressed = True
        self.focus_set()
        self._redraw()

    def _on_release(self, event=None):
        if self._state != 'normal':
            return
        was = self._pressed
        self._pressed = False
        self._redraw()
        if was and self._command:
            self._command()

    def _on_focus_in(self, event=None):
        self._focus = True
        self._redraw()

    def _on_focus_out(self, event=None):
        self._focus = False
        self._redraw()

    def _on_key(self, event=None):
        if self._state == 'normal' and self._command:
            self._command()

    # -- 绘制 ----------------------------------------------------------

    def _measure(self):
        text_w = (text_width(self._font_spec, self._text)
                  if self._text else 0)
        icon_w = (text_width(self._icon_font_spec, self._icon)
                  if self._icon else 0)
        gap = 5 if (icon_w and text_w) else 0
        width = text_w + icon_w + gap + PAD_X * 2
        if self._width:
            width = max(self._width, width)
        # 用 ascent+descent 而不是 linespace：中日韩字体的行高很大，
        # 直接用 linespace 会让按钮看起来又高又空。
        text_h = (font_metric(self._font_spec, 'ascent')
                  + font_metric(self._font_spec, 'descent'))
        # 中日韩字体的字面框偏大，封顶后按钮更紧凑
        height = max(min(int(text_h), 18), 16) + PAD_Y * 2
        return int(width), int(height)

    def _redraw(self):
        self.delete('all')
        width, height = self._measure()
        self.configure(width=width, height=height)
        # 实际分配尺寸可能比请求的大（父容器给了额外高度），
        # 背景按实际尺寸画、文字按实际高度居中，否则字会偏上。
        alloc_w = max(self.winfo_width(), width)
        alloc_h = max(self.winfo_height(), height)

        fill, border, fg, hover_fill, hover_fg = VARIANTS.get(
            self._variant, VARIANTS['secondary'])
        if self._state == 'disabled':
            fill = LINE if self._variant == 'primary' else None
            border = LINE if border else None
            fg = INK_3
            hover_fill, hover_fg = fill, fg
        elif self._hover or self._pressed:
            fill = hover_fill or fill
            fg = hover_fg

        # 圆角用 PIL 渲染成抗锯齿的图（Canvas 画的圆角是硬边，锯齿重）
        if fill or border:
            self._photo = rounded_photo(alloc_w, alloc_h, RADIUS, fill, border)
            self.create_image(0, 0, image=self._photo, anchor='nw')
        if self._focus and self._state == 'normal':
            self._focus_photo = rounded_photo(
                alloc_w - 4, alloc_h - 4, RADIUS - 1, None, ACCENT, 2)
            self.create_image(2, 2, image=self._focus_photo, anchor='nw')

        x = PAD_X
        mid = alloc_h / 2
        if self._icon:
            self.create_text(x, mid, text=self._icon, anchor='w',
                             fill=fg, font=self._icon_font)
            x += text_width(self._icon_font_spec, self._icon)
            if self._text:
                x += 5
        if self._text:
            self.create_text(x, mid, text=self._text, anchor='w',
                             fill=fg, font=self._font)


class Segmented(tk.Frame):
    """分段控件：一排互斥的小按钮（颜色、单双面、N-up 用它）。

    不用 ttk.Combobox 是因为选项少、且要跟缩放条那排按钮保持同一套观感。
    """

    def __init__(self, parent, choices, value='', command=None, bg=None):
        super().__init__(parent, bg=bg or bg_of(parent))
        self._command = command
        self._value = value
        self._buttons = {}
        for item_value, label in choices:
            button = FlatButton(self, label, variant='segment', bg=self.cget('bg'),
                                command=lambda v=item_value: self.set_value(v))
            button.pack(side='left', padx=1, pady=1)
            self._buttons[item_value] = button
        self.set_value(value, notify=False)

    def set_value(self, value, notify=True):
        """选中某一项（value 为 None/'' 表示不选）。"""
        self._value = value
        for item_value, button in self._buttons.items():
            button.set_variant('segment-on' if item_value == value
                               else 'segment')
        if notify and self._command:
            self._command(value)
        return self

    def get(self):
        return self._value

    def disable_item(self, value, disabled=True):
        """把某一项置灰（打印机不支持时用）。"""
        button = self._buttons.get(value)
        if button is not None:
            button.configure_state(not disabled)


class ZoomSlider(tk.Frame):
    """缩放滑块：两侧 -/+，点滑轨直接跳到那个倍率。

    ttk.Scale 默认点滑轨只是"翻一格"，这里改成点哪就是哪；
    按住拖动也能连续调。
    """

    def __init__(self, parent, from_=25, to=400, value=100, step=5,
                 command=None, bg=None, length=130, show_value=True,
                 width=22):
        super().__init__(parent, bg=bg or bg_of(parent))
        self._from = int(from_)
        self._to = int(to)
        self._step = int(step)
        self._command = command
        self._value = int(value)
        self._dragging = False

        self.minus = FlatButton(self, '-', command=self._step_down,
                                variant='segment', bg=self.cget('bg'),
                                width=width)
        self.minus.pack(side='left')

        self.scale = ttk.Scale(self, from_=self._from, to=self._to,
                               orient='horizontal', length=length,
                               command=self._on_scale)
        self.scale.pack(side='left', padx=2)
        self.scale.bind('<Button-1>', self._on_press)
        self.scale.bind('<B1-Motion>', self._on_drag)
        self.scale.bind('<ButtonRelease-1>', self._on_release)
        self.scale.set(self._value)

        self.plus = FlatButton(self, '+', command=self._step_up,
                               variant='segment', bg=self.cget('bg'),
                               width=width)
        self.plus.pack(side='left', padx=(2, 0))

        self.label = None
        if show_value:
            self.label = tk.Label(self, text=self._text(), bg=self.cget('bg'),
                                  fg=INK_2, font=font('num'), width=5,
                                  anchor='e')
            self.label.pack(side='left', padx=(4, 0))

    # ------------------------------------------------------------------

    def _text(self):
        return '{}%'.format(self._value)

    def _on_scale(self, value):
        """滑块被拖动（可能来自 set）。"""
        try:
            new = int(round(float(value)))
        except (TypeError, ValueError):
            return
        new = max(self._from, min(self._to, new))
        if new == self._value:
            return
        self._value = new
        if self.label is not None:
            self.label.configure(text=self._text())
        if self._command:
            self._command(self._value)

    def _value_at(self, x):
        """按点击位置算倍率（滑轨两端是头部的中心）。"""
        width = max(self.scale.winfo_width(), 1)
        head = 16
        usable = max(width - head, 1)
        frac = (x - head / 2.0) / usable
        frac = max(0.0, min(1.0, frac))
        return int(round(self._from + frac * (self._to - self._from)))

    def _on_press(self, event):
        self._dragging = True
        self.set_value(self._value_at(event.x), notify=True)

    def _on_drag(self, event):
        if not self._dragging:
            return
        self.set_value(self._value_at(event.x), notify=True)

    def _on_release(self, event):
        self._dragging = False

    def _step_up(self):
        self.set_value(self._value + self._step, notify=True)

    def _step_down(self):
        self.set_value(self._value - self._step, notify=True)

    # ------------------------------------------------------------------

    def get(self):
        return self._value

    def set_value(self, value, notify=True):
        value = max(self._from, min(self._to, int(value)))
        changed = value != self._value
        self._value = value
        try:
            self.scale.set(value)
        except tk.TclError:
            pass
        if self.label is not None:
            self.label.configure(text=self._text())
        if notify and changed and self._command:
            self._command(value)
        return self

    def set_range(self, from_, to):
        self._from = int(from_)
        self._to = int(to)
        self.scale.configure(from_=self._from, to=self._to)
        self.set_value(self._value, notify=False)


class Chip(tk.Canvas):
    """小色块标签（例如"已选 3 个文件"）。"""

    def __init__(self, parent, text='', bg=ACCENT_TINT, fg=ACCENT, pad_x=10,
                 pad_y=4):
        super().__init__(parent, highlightthickness=0, bd=0,
                         bg=bg_of(parent))
        self._text = text
        self._bg_color = bg
        self._fg = fg
        self._pad_x = pad_x
        self._pad_y = pad_y
        self._font_spec = font('body', 'bold')
        self._font = tkfont.Font(font=self._font_spec)
        self.bind('<Configure>', lambda e: self._redraw())
        self._redraw()

    def set_text(self, text):
        self._text = text
        self._redraw()
        return self

    def get_text(self):
        return self._text

    def _redraw(self):
        self.delete('all')
        text_w = (text_width(self._font_spec, self._text)
                  if self._text else 0)
        width = text_w + self._pad_x * 2
        # 和按钮一样用 ascent+descent：中日韩字体的 linespace 很高，
        # 用 linespace 会让色块比旁边的按钮高出一截
        text_h = (font_metric(self._font_spec, 'ascent')
                  + font_metric(self._font_spec, 'descent'))
        height = max(min(int(text_h), 18), 16) + self._pad_y * 2
        self.configure(width=width, height=height)
        if self._text:
            self._photo = rounded_photo(width, height, RADIUS,
                                        self._bg_color)
            self.create_image(0, 0, image=self._photo, anchor='nw')
            self.create_text(width / 2, height / 2, text=self._text,
                             fill=self._fg, font=self._font)


class RoundedCard(tk.Frame):
    """圆角卡片容器：抗锯齿圆角背景 + 投影，内部可正常放控件。"""

    IMAGE_PAD = 6      # 投影在图里占的边距（卡片本体在 (pad, pad)）

    def __init__(self, parent, radius=10, fill=PAPER, outline=LINE,
                 shadow=True, bg=None):
        super().__init__(parent, bg=bg or bg_of(parent))
        self._radius = radius
        self._fill = fill
        self._outline = outline
        self._shadow = shadow
        self._photo = None
        self._last_size = None
        self._canvas = tk.Canvas(self, highlightthickness=0, bd=0,
                                 bg=self.cget('bg'))
        self._canvas.pack(fill='both', expand=True)
        self.body = tk.Frame(self._canvas, bg=fill)
        self._window = self._canvas.create_window(0, 0, window=self.body,
                                                 anchor='nw')
        self.body.bind('<Configure>', lambda e: self._sync())
        self._canvas.bind('<Configure>', lambda e: self._sync())

    def _sync(self):
        width = self.body.winfo_reqwidth()
        height = self.body.winfo_reqheight()
        if width <= 1 or height <= 1:
            return
        # 尺寸没变就别重画：否则 configure → <Configure> → configure 会打转
        if (width, height) == self._last_size:
            return
        self._last_size = (width, height)
        # 内容要按圆角半径内缩：内容的矩形背景会盖住卡片圆角，
        # 不内缩的话看起来就是"圆角错位/缺一块"。
        shadow_pad = self.IMAGE_PAD if self._shadow else 0
        # 内容只内缩一点（不是整个半径），否则卡片会比内容高出两倍半径
        inset = 3
        card_w = width + inset * 2
        card_h = height + inset * 2
        self._canvas.configure(width=card_w + shadow_pad * 2,
                              height=card_h + shadow_pad * 2)
        # 图片贴在 (0,0)：卡片本体在图里的 (pad, pad)，
        # 内容跟着落在 (pad + inset) —— 两者对得上，圆角才不会被内容盖住。
        self._canvas.coords(self._window,
                             shadow_pad + inset,
                             shadow_pad + inset)
        self._photo = rounded_photo(card_w, card_h, self._radius, self._fill,
                                    self._outline, 1, self._shadow,
                                    root=self.winfo_toplevel(),
                                    pad=shadow_pad)
        # 必须打 tag：没有 tag 的话 delete('card') 删不掉旧图，
        # 每 resize 一次画布上就多一张图。
        self._canvas.delete('card')
        self._canvas.create_image(0, 0, image=self._photo, anchor='nw',
                                  tags='card')
        self._canvas.tag_lower('card')
