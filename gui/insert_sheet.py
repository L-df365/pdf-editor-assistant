"""插入面板：选好文件之后，确认插到哪里。"""

import os
import tkinter as tk
from tkinter import ttk

from gui.feedback import Sheet
from gui.theme import INK, INK_2, INK_3, LINE, font


class InsertSheet(Sheet):
    """插入位置选择。

    位置三选一，默认「当前页之后」——这是最常见的意图；
    不用数字输入框让人猜页码。
    """

    def __init__(self, parent, paths, current_page, page_count,
                 on_confirm=None):
        self.paths = list(paths)
        self.current_page = current_page
        self.page_count = page_count
        self.on_confirm = on_confirm
        super().__init__(parent, '插入文件')

        self._build_body()
        self._build_footer()

    def _build_body(self):
        body = self.body_frame
        names = '、'.join(os.path.basename(p) for p in self.paths[:3])
        if len(self.paths) > 3:
            names += ' 等 {} 个文件'.format(len(self.paths))
        ttk.Label(body, text='要插入', style='Paper.TLabel', font=font('meta'),
                  foreground=INK_3).pack(anchor='w')
        ttk.Label(body, text=names, style='Paper.TLabel', font=font('body'),
                  foreground=INK, wraplength=400, justify='left'
                  ).pack(anchor='w', pady=(2, 14))

        ttk.Label(body, text='插到哪里', style='Paper.TLabel',
                  font=font('meta'), foreground=INK_3).pack(anchor='w')

        self._choice = tk.StringVar(value='after')
        options = (
            ('after', '当前页之后（第 {} 页）'.format(self.current_page + 1)),
            ('end', '文末（第 {} 页）'.format(self.page_count)),
        )
        for value, label in options:
            ttk.Radiobutton(body, text=label, value=value,
                            variable=self._choice,
                            style='Paper.TRadiobutton').pack(anchor='w',
                                                            pady=2)

        row = ttk.Frame(body, style='Paper.TFrame')
        row.pack(anchor='w', pady=(2, 0))
        ttk.Radiobutton(row, text='指定位置：第', value='at',
                        variable=self._choice,
                        style='Paper.TRadiobutton').pack(side='left')
        self._index = tk.IntVar(value=min(self.current_page + 1,
                                           max(self.page_count, 1)))
        ttk.Spinbox(row, from_=1, to=max(self.page_count, 1), width=5,
                    textvariable=self._index,
                    font=font('num')).pack(side='left', padx=6)
        ttk.Label(row, text='页之前', style='Paper.TLabel',
                  font=font('body'), foreground=INK_2).pack(side='left')

    def _build_footer(self):
        foot = self.button_frame
        ttk.Button(foot, text='取消', style='Paper.Ghost.TButton',
                   command=self._cancel).pack(side='right')
        ttk.Button(foot, text='插入 {} 个文件'.format(len(self.paths)),
                   style='Primary.TButton',
                   command=self._confirm).pack(side='right', padx=(0, 8))

    def _confirm(self):
        choice = self._choice.get()
        if choice == 'after':
            position = self.current_page + 1
        elif choice == 'end':
            position = self.page_count
        else:
            position = max(0, min(self.page_count, self._index.get() - 1))
        self.result = position
        if self.on_confirm:
            self.on_confirm(position)
        self.destroy()
