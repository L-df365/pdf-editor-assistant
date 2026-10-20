"""反馈组件：轻提示、确认面板、错误面板、信息面板。

替代系统 messagebox —— 系统的对话框是 Tk 内置控件，图标无语义、按钮是英文
"OK"，与整个界面的视觉语言割裂。
"""

import tkinter as tk
from tkinter import ttk

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
    y = parent.winfo_rooty() + parent.winfo_height() - height - 64
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


class Sheet(tk.Toplevel):
    """统一样式的模态面板骨架。"""

    def __init__(self, parent, title, body='', width=420):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.configure(bg=PAPER)
        self.result = None

        border = tk.Frame(self, bg=LINE)
        border.pack(fill='both', expand=True)
        frame = ttk.Frame(border, style='Paper.TFrame', padding=(20, 16))
        frame.pack(fill='both', expand=True, padx=1, pady=1)

        ttk.Label(frame, text=title, style='Paper.TLabel',
                  font=font('h1', 'bold')).pack(anchor='w')
        if body:
            ttk.Label(frame, text=body, style='Paper.TLabel',
                      font=font('body'), foreground=INK_2, wraplength=width,
                      justify='left').pack(anchor='w', pady=(8, 0))

        self.body_frame = ttk.Frame(frame, style='Paper.TFrame')
        self.body_frame.pack(fill='both', expand=True, pady=(12, 0))

        self.button_frame = ttk.Frame(frame, style='Paper.TFrame')
        self.button_frame.pack(fill='x', pady=(16, 0))

        self.bind('<Escape>', lambda e: self._cancel())

    def _cancel(self):
        self.result = False
        self.destroy()

    def _place(self, parent):
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width()
                                    - self.winfo_reqwidth()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height()
                                    - self.winfo_reqheight()) // 3
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
        ttk.Button(self.button_frame, text='取消',
                   style='Paper.Ghost.TButton',
                   command=self._cancel).pack(side='right')
        ttk.Button(self.button_frame, text=confirm_text,
                   style='Paper.Danger.TButton' if danger
                   else 'Primary.TButton',
                   command=self._confirm).pack(side='right', padx=(0, 8))

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

        ttk.Button(self.button_frame, text='复制详情',
                   style='Paper.Ghost.TButton',
                   command=self._copy_detail).pack(side='left')
        ttk.Button(self.button_frame, text='关闭',
                   style='Primary.TButton',
                   command=self._cancel).pack(side='right')

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
            ttk.Label(self.body_frame, text=footnote, style='Paper.TLabel',
                      font=font('meta'), foreground=INK_2, wraplength=420,
                      justify='left').pack(anchor='w', pady=(12, 0))
        ttk.Button(self.button_frame, text='关闭', style='Primary.TButton',
                   command=self._cancel).pack(side='right')

    @staticmethod
    def show(parent, title, rows, footnote=''):
        panel = InfoPanel(parent, title, rows, footnote)
        panel.wait(parent)
