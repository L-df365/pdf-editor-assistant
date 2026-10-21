"""反馈组件：轻提示、确认面板、错误面板、信息面板。

替代系统 messagebox —— 系统的对话框是 Tk 内置控件，图标无语义、按钮是英文
"OK"，与整个界面的视觉语言割裂。
"""

import tkinter as tk
from tkinter import ttk

from gui.draw import rounded_photo
from gui.widgets import FlatButton
from gui.theme import (ACCENT, DANGER, INK, INK_2, INK_3, LINE, MARKER, OK,
                        PAPER, font)

KIND_COLORS = {
    'info': ACCENT,
    'ok': OK,
    'warn': MARKER,
    'error': DANGER,
}


def toast(parent, message, kind='info', duration=3500):
    """右下角轻提示，3.5 秒后自动消失。"""
    win = tk.Toplevel(parent)
    win.overrideredirect(True)
    try:
        win.attributes('-topmost', True)
    except tk.TclError:
        pass

    color = KIND_COLORS.get(kind, ACCENT)
    frame = tk.Frame(win, bg=PAPER, highlightbackground=LINE,
                     highlightthickness=1)
    frame.pack(fill='both', expand=True)
    bar = tk.Frame(frame, width=3, bg=color)
    bar.pack(side='left', fill='y')
    tk.Label(frame, text=message, font=font('body'), bg=PAPER, fg=INK,
             justify='left', wraplength=340, padx=14, pady=11).pack(side='left')

    win.update_idletasks()
    width = win.winfo_reqwidth()
    height = win.winfo_reqheight()
    x = parent.winfo_rootx() + parent.winfo_width() - width - 24
    y = parent.winfo_rooty() + parent.winfo_height() - height - 78
    win.geometry('+{}+{}'.format(x, y))

    def slide(step=0):
        if not win.winfo_exists() or step >= 6:
            return
        offset = (6 - step) * 4
        win.geometry('+{}+{}'.format(x, y + offset))
        win.after(20, lambda: slide(step + 1))

    slide()
    win.after(duration, win.destroy)
    return win


def attach_tooltip(widget, text, delay=500):
    """给控件挂一个简单提示（图标按钮没有文字时需要）。"""
    state = {'win': None, 'job': None}

    def show():
        if state['win'] is not None:
            return
        try:
            x = widget.winfo_rootx() + widget.winfo_width() // 2
            y = widget.winfo_rooty() + widget.winfo_height() + 6
        except tk.TclError:
            return   # 控件已经被销毁
        win = tk.Toplevel(widget)
        win.overrideredirect(True)
        try:
            win.attributes('-topmost', True)
        except tk.TclError:
            pass
        tk.Label(win, text=text, bg=INK, fg=PAPER, font=font('meta'),
                 padx=8, pady=4).pack()
        win.update_idletasks()
        win.geometry('+{}+{}'.format(
            x - win.winfo_reqwidth() // 2, y))
        state['win'] = win

    def hide():
        if state['job'] is not None:
            try:
                widget.after_cancel(state['job'])
            except tk.TclError:
                pass
            state['job'] = None
        if state['win'] is not None:
            try:
                state['win'].destroy()
            except tk.TclError:
                pass
            state['win'] = None

    widget.bind('<Enter>', lambda e: state.update(
        job=widget.after(delay, show)), add='+')
    widget.bind('<Leave>', lambda e: hide(), add='+')
    widget.bind('<ButtonPress>', lambda e: hide(), add='+')
    widget.bind('<Destroy>', lambda e: hide(), add='+')
    return hide


class Sheet(tk.Toplevel):
    """统一样式的模态卡片：无系统边框，圆角纸面 + 投影。"""

    MARGIN = 12
    RADIUS = 10

    def __init__(self, parent, title, body='', width=420, panel_width=None):
        super().__init__(parent)
        self.withdraw()
        self.overrideredirect(True)
        self.transient(parent)
        self.result = None
        # 固定宽度：内容多寡不该让窗口宽度跳来跳去（选不同文件宽度就变，很不专业）
        self._panel_width = panel_width

        self._bg = tk.Canvas(self, highlightthickness=0, bg=PAPER)
        self._bg.place(x=0, y=0, relwidth=1, relheight=1)
        self._bg.bind('<Configure>', self._paint_card)

        frame = ttk.Frame(self, style='Paper.TFrame', padding=(22, 16))
        # fill=both：窗口被压矮时正文让位、底部按钮行保持完整
        frame.pack(padx=self.MARGIN, pady=self.MARGIN, fill='both', expand=True)
        self._frame = frame

        header = ttk.Frame(frame, style='Paper.TFrame')
        header.pack(fill='x')
        ttk.Label(header, text=title, style='Paper.TLabel',
                  font=font('h1', 'bold')).pack(side='left')
        ttk.Button(header, text='×', style='Paper.Ghost.TButton',
                   command=self._cancel, width=3).pack(side='right')
        if body:
            ttk.Label(frame, text=body, style='Paper.TLabel',
                      font=font('body'), foreground=INK_2, wraplength=width,
                      justify='left').pack(anchor='w', pady=(8, 0))

        self.body_frame = ttk.Frame(frame, style='Paper.TFrame')
        self.body_frame.pack(fill='both', expand=True, pady=(12, 0))

        self.button_frame = ttk.Frame(frame, style='Paper.TFrame')
        self.button_frame.pack(fill='x', pady=(16, 0))

        self.bind('<Escape>', lambda e: self._cancel())

    def _paint_card(self, event=None):
        w = max(self._bg.winfo_width(), 40)
        h = max(self._bg.winfo_height(), 40)
        self._bg.delete('card')
        m = self.MARGIN
        # 抗锯齿圆角 + 柔和投影。
        # pad 是投影留白：图比卡片大 pad*2，卡片本体在图里的 (pad, pad)，
        # 所以图要往左上挪 pad，卡片才落在原来的 (m, m) 上。
        pad = 6
        self._card_photo = rounded_photo(
            w - m * 2, h - m * 2, self.RADIUS, PAPER, LINE, 1, shadow=True,
            root=self.winfo_toplevel(), pad=pad)
        self._bg.create_image(m - pad, m - pad, image=self._card_photo,
                              anchor='nw', tags='card')

    def _cancel(self):
        self.result = False
        self.destroy()

    def _place(self, parent):
        self.update_idletasks()
        width = self.winfo_reqwidth()
        height = self.winfo_reqheight()
        if self._panel_width:
            width = self._panel_width
        if width <= 1:
            width = self._frame.winfo_reqwidth() + self.MARGIN * 2
        if height <= 1:
            height = self._frame.winfo_reqheight() + self.MARGIN * 2
        # 屏幕装不下就压高度：正文（列表）可以让步，按钮行必须留在屏幕上，
        # 否则小屏上「取消/确定」会被切掉半截。
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(width, screen_w - 16)
        height = min(height, screen_h - 16)
        self.geometry('{}x{}'.format(width, height))
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - height) // 3
        x = max(parent.winfo_rootx() + 8, min(x,
                parent.winfo_rootx() + parent.winfo_width() - width - 8))
        # 别让卡片下半截掉到屏幕外
        y = max(8, min(y, screen_h - height - 8))
        self.geometry('+{}+{}'.format(x, y))
        self.deiconify()
        self.grab_set()
        self.focus_set()

    def wait(self, parent):
        self._place(parent)
        parent.wait_window(self)
        return self.result


class ConfirmPanel(Sheet):
    """破坏性或不可逆动作的确认。"""

    def __init__(self, parent, title, body, confirm_text='确认',
                 danger=True):
        super().__init__(parent, title, body)
        # 先放确定、再放取消：side='right' 时后放的排左边，
        # 这样确定在右、取消在左（和系统对话框一致）。
        FlatButton(self.button_frame, confirm_text, command=self._confirm,
                   variant='danger-solid' if danger else 'primary',
                   bg=PAPER).pack(side='right', padx=(0, 8), pady=2)
        FlatButton(self.button_frame, '取消', command=self._cancel,
                   variant='ghost', bg=PAPER).pack(side='right', pady=2)

    def _confirm(self):
        self.result = True
        self.destroy()

    @staticmethod
    def ask(parent, title, body, confirm_text='确认', danger=True):
        panel = ConfirmPanel(parent, title, body, confirm_text, danger)
        return bool(panel.wait(parent))


class ErrorPanel(Sheet):
    """错误：说清发生了什么 + 怎么修，原始信息收进「诊断详情」。"""

    def __init__(self, parent, title, body, detail=''):
        super().__init__(parent, title, body)
        self._detail = detail
        self._detail_visible = False

        if detail:
            self._toggle = ttk.Button(
                self.body_frame, text='诊断详情', style='Paper.Ghost.TButton',
                command=self._show_detail)
            self._toggle.pack(anchor='w')
            self._detail_box = tk.Text(
                self.body_frame, height=6, width=52, wrap='word',
                font=font('num'), bg=PAPER, fg=INK_3, relief='flat',
                highlightbackground=LINE, highlightthickness=1)
            self._detail_box.pack(fill='both', expand=True, pady=(8, 0))
            self._detail_box.insert('1.0', detail)
            self._detail_box.configure(state='disabled')
            self._detail_box.pack_forget()

        FlatButton(self.button_frame, '复制详情', command=self._copy_detail,
                   variant='ghost', bg=PAPER).pack(side='left', pady=2)
        FlatButton(self.button_frame, '关闭', command=self._cancel,
                   variant='primary', bg=PAPER).pack(side='right', pady=2)

    def _show_detail(self):
        self._detail_visible = not self._detail_visible
        if self._detail_visible:
            self._detail_box.pack(fill='both', expand=True, pady=(8, 0))
            self._toggle.configure(text='收起诊断详情')
        else:
            self._detail_box.pack_forget()
            self._toggle.configure(text='诊断详情')

    def _copy_detail(self):
        try:
            parent = self.master
            parent.clipboard_clear()
            parent.clipboard_append(self._detail)
            toast(parent, '详情已复制到剪贴板', 'ok')
        except tk.TclError:
            pass

    @staticmethod
    def show(parent, title, body, detail=''):
        panel = ErrorPanel(parent, title, body, detail)
        panel.wait(parent)


class InfoPanel(Sheet):
    """信息展示（页面信息、关于）。"""

    def __init__(self, parent, title, rows, footnote=''):
        super().__init__(parent, title)
        for index, (key, value) in enumerate(rows):
            ttk.Label(self.body_frame, text=key, style='Paper.TLabel',
                      font=font('meta'), foreground=INK_3
                      ).grid(row=index, column=0, sticky='w', pady=2)
            ttk.Label(self.body_frame, text=value, style='Paper.TLabel',
                      font=font('body'), foreground=INK
                      ).grid(row=index, column=1, sticky='w', pady=2,
                            padx=(16, 0))
        self.body_frame.columnconfigure(1, weight=1)
        if footnote:
            # 同一个容器里只能有一种几何管理器：这里要用 grid，
            # 混用 pack 会直接抛 TclError（面板根本打不开）。
            ttk.Label(self.body_frame, text=footnote, style='Paper.TLabel',
                      font=font('meta'), foreground=INK_2, wraplength=420,
                      justify='left').grid(row=len(rows), column=0,
                                           columnspan=2, sticky='w',
                                           pady=(12, 0))
        FlatButton(self.button_frame, '关闭', command=self._cancel,
                   variant='primary', bg=PAPER).pack(side='right', pady=2)

    @staticmethod
    def show(parent, title, rows, footnote=''):
        panel = InfoPanel(parent, title, rows, footnote)
        panel.wait(parent)
