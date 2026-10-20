import tkinter as tk
from tkinter import ttk

from gui.theme import (ACCENT, INK, INK_2, INK_3, OK, SURFACE, font)


class BackendDialog(tk.Toplevel):
    """转换后端：选择 + 可用状态 + 按需安装入口。"""

    def __init__(self, parent, status_list, current, on_select, on_install):
        super().__init__(parent)
        self.title('转换后端')
        self.transient(parent)
        self.resizable(False, False)
        self.on_select = on_select
        self.on_install = on_install
        self._status = {item['name']: item for item in status_list}
        self._var = tk.StringVar(value=current)

        frame = ttk.Frame(self, style='Paper.TFrame', padding=(16, 14))
        frame.pack(fill='both', expand=True)

        ttk.Label(
            frame,
            text='后端不随应用安装，只调用本机已安装的程序。',
            style='Paper.TLabel', font=font('meta'), foreground=INK_2,
        ).grid(row=0, column=0, columnspan=3, sticky='w', pady=(0, 10))

        row_index = 1
        for item in status_list:
            name = item['name']
            available = item['available']
            radio = ttk.Radiobutton(
                frame, text=item['label'], value=name, variable=self._var,
                command=lambda n=name: self._pick(n),
                style='Paper.TRadiobutton')
            radio.grid(row=row_index, column=0, sticky='w', pady=4)

            dot = tk.Label(frame, text='●', font=font('body'),
                           bg='#FFFFFF',
                           foreground=OK if available else INK_3)
            dot.grid(row=row_index, column=1, sticky='w', padx=(12, 6))

            reason = ttk.Label(
                frame,
                text='' if available else (item['reason'] or '未安装'),
                style='Paper.TLabel', font=font('meta'),
                foreground=INK_2 if available else INK_3)
            reason.grid(row=row_index, column=2, sticky='w')

            if not available:
                ttk.Button(
                    frame, text='安装…', style='Paper.Ghost.TButton',
                    command=lambda n=name: self._install(n)
                ).grid(row=row_index, column=3, sticky='e', padx=(16, 0))

            row_index += 1

        ttk.Separator(frame, orient='horizontal').grid(
            row=row_index, column=0, columnspan=4, sticky='ew', pady=(12, 10))
        ttk.Button(frame, text='关闭', style='Paper.Ghost.TButton',
                   command=self.destroy).grid(row=row_index + 1, column=3,
                                             sticky='e')

        self.bind('<Escape>', lambda e: self.destroy())
        self.update_idletasks()
        self.focus_set()

    def _pick(self, name):
        item = self._status.get(name, {})
        if not item.get('available'):
            # 不可用：撤销选择并交给安装流程
            self._var.set('')
            self.on_install(name, item)
            return
        self.on_select(name)
        self.destroy()

    def _install(self, name):
        item = self._status.get(name, {})
        self.destroy()
        self.on_install(name, item)
