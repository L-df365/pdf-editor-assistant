"""打印当前文档。

「打印当前 PDF」和以后的「批量打印」是两条独立的入口，但共用
core/print 的底座和 PrintOptionsForm 这块参数界面。
"""

import tkinter as tk
from tkinter import ttk

from core.print_core import backend, print_single, ranges
from core.print_core.errors import PrintError
from gui.feedback import Sheet, toast
from gui.theme import INK_2, PAPER, font
from gui.widgets import FlatButton
from gui.print_options import PrintOptionsForm


class PrintSheet(Sheet):
    """打印当前文档的设置面板。"""

    def __init__(self, parent, doc, page_range='', title='打印',
                 on_printed=None):
        super().__init__(parent, title)
        self.doc = doc
        self.on_printed = on_printed
        self._job_id = None
        self._printer = None

        # 先建按钮：面板里的选项一变就会回调到按钮的可用状态上
        self._build_footer()
        self._build_body(page_range)

    # ------------------------------------------------------------------

    def _build_body(self, page_range):
        body = self.body_frame
        body.columnconfigure(1, weight=1)

        self.summary = tk.Label(body, text='', bg=PAPER, fg=INK_2,
                                 font=font('meta'), anchor='w', justify='left')
        self.summary.grid(row=0, column=0, columnspan=2, sticky='w',
                           pady=(0, 10))

        # 打印机
        line = tk.Frame(body, bg=PAPER)
        line.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(0, 10))
        tk.Label(line, text='打印机', bg=PAPER, fg=INK_2, font=font('body'),
                 width=6, anchor='w').pack(side='left')
        self.printer_box = ttk.Combobox(line, state='readonly', width=30,
                                        font=font('body'))
        self.printer_box.pack(side='left')
        self.printer_box.bind('<<ComboboxSelected>>',
                              lambda e: self._on_printer_pick())

        self.form = PrintOptionsForm(body, bg=PAPER, show_pages=True,
                                      on_change=self._on_options_change)
        self.form.grid(row=3, column=0, columnspan=2, sticky='ew')

        self._load_printers()
        self.form.set_page_total(self.doc.page_count)
        if page_range:
            self.form.set_page_range(page_range)
        self._update_summary()

    def _build_footer(self):
        self.print_button = FlatButton(self.button_frame, '打印',
                                       command=self._print,
                                       variant='primary', bg=PAPER)
        self.print_button.pack(side='right')
        FlatButton(self.button_frame, '取消', command=self._cancel,
                   variant='ghost', bg=PAPER).pack(side='right', padx=(0, 8))

    # ------------------------------------------------------------------

    def _load_printers(self):
        if not backend.available():
            self.summary.configure(text='系统没有安装 python3-cups，打印不可用')
            self.printer_box['values'] = ()
            return
        try:
            items = backend.list_printers()
        except PrintError as exc:
            self.summary.configure(text=str(exc))
            return
        if not items:
            self.summary.configure(text='没有找到打印机')
            return
        self._printers = items
        self.printer_box['values'] = [p.label() for p in items]
        default = backend.default_printer()
        index = 0
        if default is not None:
            for i, printer in enumerate(items):
                if printer.name == default.name:
                    index = i
                    break
        self.printer_box.current(index)
        self._on_printer_pick()

    def _on_printer_pick(self):
        index = self.printer_box.current()
        items = getattr(self, '_printers', [])
        if 0 <= index < len(items):
            self._printer = items[index]
            self.form.set_printer(self._printer)
        self._update_summary()

    def _on_options_change(self, issues):
        self.print_button.configure_state(not issues)
        self._update_summary()

    def _update_summary(self):
        total = self.doc.page_count
        opts = self.form.options()
        text = '共 {} 页'.format(total)
        if opts.pages:
            try:
                segments = ranges.parse(opts.pages, total)
                text += ' · 将打印 {} 页（{}）'.format(
                    ranges.count_pages(segments), ranges.describe(segments))
            except ranges.RangeError:
                text += ' · 页码范围有误'
        if self._printer is not None:
            reason = self._printer.reason_text()
            if reason:
                text += '\n注意：{}'.format(reason)
        self.summary.configure(text=text)

    # ------------------------------------------------------------------

    def _print(self):
        """交给 print_core 打印：当前文档和批量打印走同一套逻辑。"""
        if not self._printer:
            return
        opts = self.form.options()
        if self.form.problems():
            return
        try:
            # print_single 打印的是内存里的当前状态（改了没保存也算数）
            job_id = print_single(self.doc, opts, printer=self._printer.name)
        except PrintError as exc:
            toast(self.master, str(exc), 'error')
            return
        except Exception as exc:
            toast(self.master, '打印失败：{}'.format(exc), 'error')
            return
        self._job_id = job_id
        self.result = job_id
        if self.on_printed:
            self.on_printed(job_id)
        self.destroy()

    @staticmethod
    def show(parent, doc, page_range='', title='打印', on_printed=None):
        sheet = PrintSheet(parent, doc, page_range, title, on_printed)
        sheet._place(parent)
        parent.wait_window(sheet)
        return sheet.result
