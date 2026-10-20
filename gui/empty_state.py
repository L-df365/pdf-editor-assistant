"""空状态：没有打开文档时的主界面。"""

import tkinter as tk

from gui.theme import INK, INK_2, INK_3, MARKER, STAGE, font
from gui.widgets import FlatButton


class EmptyState:
    """样张空台：宋体主标题 + 两个动作 + 一条琥珀标记条。"""

    def __init__(self, parent, on_open=None, on_insert=None):
        self.frame = tk.Frame(parent, bg=STAGE)
        self.on_open = on_open
        self.on_insert = on_insert

        center = tk.Frame(self.frame, bg=STAGE)
        center.place(relx=0.5, rely=0.44, anchor='center')

        row = tk.Frame(center, bg=STAGE)
        row.pack(anchor='w')
        marker = tk.Frame(row, width=3, height=54, bg=MARKER)
        marker.pack(side='left', padx=(0, 16))

        text = tk.Frame(row, bg=STAGE)
        text.pack(side='left')

        tk.Label(text, text='先打开一个 PDF', bg=STAGE, fg=INK,
                 font=font('display', 'bold'), anchor='w').pack(anchor='w')
        tk.Label(text, text='也可以直接把 Word、Excel、图片插进来，\n'
                            '转成页面放到任意位置。',
                 bg=STAGE, fg=INK_2, font=font('body'), anchor='w',
                 justify='left').pack(anchor='w', pady=(6, 0))

        buttons = tk.Frame(center, bg=STAGE)
        buttons.pack(anchor='w', pady=(22, 0))
        FlatButton(buttons, '打开 PDF', command=self._open,
                   variant='primary', bg=STAGE, width=110).pack(
                       side='left', padx=(0, 10))
        FlatButton(buttons, '插入文件', command=self._insert,
                   variant='secondary', bg=STAGE, width=110).pack(side='left')

        tk.Label(center, text='Ctrl+O 打开　·　在文件管理器里双击文件，'
                              '也能用本应用打开',
                 bg=STAGE, fg=INK_3, font=font('meta'),
                 anchor='w').pack(anchor='w', pady=(18, 0))

    def _open(self):
        if self.on_open:
            self.on_open()

    def _insert(self):
        if self.on_insert:
            self.on_insert()

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)
        return self.frame

    def pack_forget(self):
        self.frame.pack_forget()
