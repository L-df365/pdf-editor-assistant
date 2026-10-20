"""自绘圆角按钮。

ttk 画不出圆角（clam 主题只有方角），所以可见的操作按钮统一用这个：
纸面填充 / 1px 细线 / 墨青主色 / 悬停与按下反馈 / 焦点环。
"""

import tkinter as tk
from tkinter import font as tkfont

from gui.draw import rounded_photo
from gui.theme import (ACCENT, ACCENT_DEEP, ACCENT_TINT, DANGER, DANGER_TINT,
                        INK, INK_2, INK_3, LINE, PAPER, font)

RADIUS = 6
PAD_X = 12
PAD_Y = 4

# 变体: (填充, 描边, 文字, 悬停填充, 悬停文字)
VARIANTS = {
    'primary': (ACCENT, ACCENT, PAPER, ACCENT_DEEP, PAPER),
    'secondary': (PAPER, LINE, INK, ACCENT_TINT, INK),
    'ghost': ('', '', INK_2, ACCENT_TINT, INK),
    'danger': ('', '', DANGER, DANGER_TINT, DANGER),
    'menu': ('', '', INK, ACCENT_TINT, INK),
    'segment': ('', '', INK_2, ACCENT_TINT, INK),
    'segment-on': (ACCENT_TINT, '', ACCENT, ACCENT_TINT, ACCENT),
}


def bg_of(parent, fallback=PAPER):
    """取父容器的背景色（ttk 控件没有 -bg 选项）。"""
    try:
        return parent.cget('bg')
    except tk.TclError:
        return fallback


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
        self._font = tkfont.Font(font=font('body'))
        self._icon_font = tkfont.Font(font=font('body', 'bold'))
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
        text_w = self._font.measure(self._text) if self._text else 0
        icon_w = self._icon_font.measure(self._icon) if self._icon else 0
        gap = 5 if (icon_w and text_w) else 0
        width = text_w + icon_w + gap + PAD_X * 2
        if self._width:
            width = max(self._width, width)
        # 用 ascent+descent 而不是 linespace：中日韩字体的行高很大，
        # 直接用 linespace 会让按钮看起来又高又空。
        text_h = (self._font.metrics('ascent')
                  + self._font.metrics('descent'))
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
            x += self._icon_font.measure(self._icon)
            if self._text:
                x += 5
        if self._text:
            self.create_text(x, mid, text=self._text, anchor='w',
                             fill=fg, font=self._font)


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
        self._font = tkfont.Font(font=font('body', 'bold'))
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
        text_w = self._font.measure(self._text) if self._text else 0
        width = text_w + self._pad_x * 2
        height = max(self._font.metrics('linespace'), 16) + self._pad_y * 2
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
        if (width, height) == getattr(self, '_last_size', None):
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
        self._canvas.coords(self._window,
                             shadow_pad + inset,
                             shadow_pad + inset)
        self._photo = rounded_photo(card_w, card_h, self._radius, self._fill,
                                    self._outline, 1, self._shadow,
                                    root=self.winfo_toplevel(),
                                    pad=shadow_pad)
        self._canvas.delete('card')
        self._canvas.create_image(shadow_pad, shadow_pad,
                                  image=self._photo, anchor='nw')
        self._canvas.tag_lower('card')
