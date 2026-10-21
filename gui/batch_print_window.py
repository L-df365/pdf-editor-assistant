"""批量打印窗口。

**只有这一套界面**：
- 从主程序里打开：主窗口 → 批量打印…（作为子窗口）
- 独立启动：pdf-editor --print / pdf-print（自己开一个窗口）

两边行为完全一致（同一套队列、同一套参数表单、同一套底座）。

这个窗口本身不依赖 PyMuPDF：它只管列文件、设参数、提交队列；
需要渲染页面的场合（打印内存里打开的文档）由主程序那边负责。
"""

import os
import tkinter as tk
from tkinter import ttk

from core import formats
from core.print_core import backend, PrintJob, PrintOptions, PrintQueue
from core.print_core import PrintState
from core.print_core.errors import PrintError
from gui.feedback import Sheet, toast
from gui.print_options import PrintOptionsForm
from gui.theme import (ACCENT, DANGER, INK, INK_2, INK_3, LINE, PAPER, SURFACE,
                        font, init_theme)
from gui.widgets import FlatButton

#: 表格列：(表头, 宽度)
COLUMNS = (
    ('文件名', 200),
    ('格式', 55),
    ('页码', 70),
    ('份数', 45),
    ('颜色', 50),
    ('单双面', 65),
    ('状态', 75),
    ('↑', 26),
    ('↓', 26),
)

#: 队列排序方式
SORT_MODES = (
    ('manual', '添加顺序'),
    ('name', '文件名'),
    ('mtime', '修改时间'),
    ('size', '大小'),
    ('type', '类型'),
)

#: 上下移动两列在表格里的位置（最后两列，从 0 起数）
UP_COLUMN = len(COLUMNS) - 2
DOWN_COLUMN = len(COLUMNS) - 1

#: 文件夹展开的限制
MAX_FOLDER_FILES = 500
MAX_FOLDER_DEPTH = 4


class BatchPrintWindow:
    """批量打印窗口。parent 为 None 时独立运行。"""

    def __init__(self, parent=None):
        self.standalone = parent is None
        if self.standalone:
            self.root = tk.Tk()
            init_theme(self.root)
            self.root.title('批量打印')
            self.root.geometry('1140x700')
            self.root.minsize(880, 560)
            self.frame = self.root
        else:
            self.root = parent
            self.win = tk.Toplevel(parent)
            self.win.title('批量打印')
            self.win.geometry('1140x700')
            self.win.minsize(880, 560)
            self.frame = self.win
        self._printers = []
        self._printer = None
        self.directory = os.path.expanduser('~')
        self._rows = {}          # iid → PrintJob
        self.queue = PrintQueue(on_event=self._on_event)
        self._build()

    # ------------------------------------------------------------------
    # 界面
    # ------------------------------------------------------------------

    def _build(self):
        self._build_top()
        self._build_body()
        self._build_log()
        self.frame.after(60, self._place_sash)
        self._load_printers()
        self._refresh_rows()

    def _place_sash(self):
        """左右分栏的比例：左边队列宽，右边参数区够放下。"""
        try:
            width = self.frame.winfo_width()
            if width > 100:
                self.frame.children[list(self.frame.children)[0]].sashpos(
                    0, int(width * 0.56))
        except Exception:
            pass

    def _build_top(self):
        bar = ttk.Frame(self.frame, style='Surface.TFrame')
        bar.pack(fill='x')
        ttk.Separator(self.frame, orient='horizontal').pack(fill='x')

        tk.Label(bar, text='打印机', bg=SURFACE, fg=INK_2, font=font('body')
                 ).pack(side='left', padx=(12, 6), pady=8)
        self.printer_box = ttk.Combobox(bar, state='readonly', width=30,
                                        font=font('body'))
        self.printer_box.pack(side='left')
        self.printer_box.bind('<<ComboboxSelected>>',
                              lambda e: self._on_printer_pick())
        self.status_label = tk.Label(bar, text='', bg=SURFACE, fg=INK_3,
                                     font=font('meta'))
        self.status_label.pack(side='left', padx=(12, 0))

        FlatButton(bar, '添加文件…', command=self._add_files,
                   variant='secondary', bg=SURFACE).pack(side='right',
                                                         padx=(6, 12), pady=8)
        FlatButton(bar, '添加文件夹…', command=self._add_folder,
                   variant='secondary', bg=SURFACE).pack(side='right',
                                                         padx=(0, 6), pady=8)

    def _build_body(self):
        paned = ttk.PanedWindow(self.frame, orient='horizontal')
        paned.pack(fill='both', expand=True)

        # 左：队列
        left = ttk.Frame(paned, style='Surface.TFrame')
        paned.add(left, weight=3)
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        head = ttk.Frame(left, style='Surface.TFrame')
        head.grid(row=0, column=0, sticky='ew', padx=12, pady=(10, 6))
        tk.Label(head, text='队列', bg=SURFACE, fg=INK, font=font('h2', 'bold')
                 ).pack(side='left')
        self.count_label = tk.Label(head, text='', bg=SURFACE, fg=INK_3,
                                    font=font('meta'))
        self.count_label.pack(side='left', padx=(8, 0))
        # 排序：按文件名/时间/大小/类型，或保持添加顺序
        tk.Label(head, text='排序', bg=SURFACE, fg=INK_2,
                 font=font('meta')).pack(side='right', padx=(8, 4))
        self.sort_box = ttk.Combobox(head, state='readonly', width=9,
                                      font=font('meta'))
        self.sort_box['values'] = [label for _, label in SORT_MODES]
        self.sort_box.current(0)
        self.sort_box.pack(side='right')
        self.sort_box.bind('<<ComboboxSelected>>', lambda e: self._on_sort())

        columns = [c[0] for c in COLUMNS]
        self.tree = ttk.Treeview(left, columns=columns, show='headings',
                                  selectmode='extended')
        for title, width in COLUMNS:
            self.tree.heading(title, text=title, anchor='w')
            self.tree.column(title, width=width,
                             stretch=(title == '文件名'), anchor='w')
        vsb = ttk.Scrollbar(left, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=1, column=0, sticky='nsew', padx=(12, 0))
        vsb.grid(row=1, column=1, sticky='ns')
        self.tree.bind('<Double-1>', lambda e: self._edit_selected())
        self.tree.bind('<Button-1>', self._on_tree_click)
        self.tree.tag_configure('failed', foreground=DANGER)
        self.tree.tag_configure('done', foreground=INK_3)
        self.tree.tag_configure('picked', foreground=ACCENT)

        actions = ttk.Frame(left, style='Surface.TFrame')
        actions.grid(row=2, column=0, columnspan=2, sticky='ew', padx=12,
                     pady=8)
        FlatButton(actions, '移除', command=self._remove_selected,
                   variant='ghost', bg=SURFACE).pack(side='left')
        FlatButton(actions, '改参数…', command=self._edit_selected,
                   variant='ghost', bg=SURFACE).pack(side='left', padx=(6, 0))
        FlatButton(actions, '清空队列', command=self._clear_queue,
                   variant='ghost', bg=SURFACE).pack(side='right')

        # 右：全局默认参数 + 控制
        right = ttk.Frame(paned, style='Surface.TFrame')
        paned.add(right, weight=2)
        tk.Label(right, text='默认参数', bg=SURFACE, fg=INK,
                 font=font('h2', 'bold')).pack(anchor='w', padx=16,
                                                pady=(10, 2))
        tk.Label(right, text='对队列里所有文件生效；单个文件可以单独覆盖。',
                 bg=SURFACE, fg=INK_3, font=font('meta'),
                 justify='left').pack(anchor='w', padx=16)
        self.form = PrintOptionsForm(right, bg=SURFACE, show_pages=False,
                                      on_change=self._on_defaults_change)
        self.form.pack(fill='x', padx=16, pady=(8, 0))

        controls = ttk.Frame(right, style='Surface.TFrame')
        controls.pack(fill='x', padx=16, pady=12)
        self.start_button = FlatButton(controls, '开始打印', command=self._start,
                                       variant='primary', bg=SURFACE)
        self.start_button.pack(side='left')
        self.pause_button = FlatButton(controls, '暂停', command=self._pause,
                                       variant='secondary', bg=SURFACE)
        self.pause_button.pack(side='left', padx=(6, 0))
        FlatButton(controls, '取消', command=self._cancel,
                   variant='ghost', bg=SURFACE).pack(side='left', padx=(6, 0))
        FlatButton(controls, '重试失败', command=self._retry_failed,
                   variant='ghost', bg=SURFACE).pack(side='left', padx=(6, 0))

    def _build_log(self):
        ttk.Separator(self.frame, orient='horizontal').pack(fill='x')
        pane = ttk.Frame(self.frame, style='Surface.TFrame')
        pane.pack(fill='both', expand=False, padx=12, pady=8)
        pane.pack_propagate(False)
        pane.configure(height=110)
        self.log = tk.Text(pane, height=5, font=font('num'), bg=PAPER,
                            fg=INK_2, relief='flat', highlightbackground=LINE,
                            highlightthickness=1, wrap='word')
        self.log.pack(fill='both', expand=True)
        self.log.configure(state='disabled')

    # ------------------------------------------------------------------
    # 打印机
    # ------------------------------------------------------------------

    def _load_printers(self):
        if not backend.available():
            self.status_label.configure(text='系统没装 python3-cups，打印不可用')
            return
        try:
            self._printers = backend.list_printers()
        except PrintError as exc:
            self.status_label.configure(text=str(exc))
            return
        if not self._printers:
            self.status_label.configure(text='没有找到打印机')
            return
        self.printer_box['values'] = [p.label() for p in self._printers]
        default = backend.default_printer()
        index = 0
        if default is not None:
            for i, printer in enumerate(self._printers):
                if printer.name == default.name:
                    index = i
                    break
        self.printer_box.current(index)
        self._on_printer_pick()

    def _on_printer_pick(self):
        index = self.printer_box.current()
        if 0 <= index < len(self._printers):
            self._printer = self._printers[index]
            self.queue.printer = self._printer.name
            self.form.set_printer(self._printer)
            reason = self._printer.reason_text()
            self.status_label.configure(
                text='{}{}'.format(self._printer.state_text,
                                   '　注意：' + reason if reason else ''))
        self._refresh_rows()

    # ------------------------------------------------------------------
    # 队列
    # ------------------------------------------------------------------

    def _add_files(self):
        from gui.file_sheet import FileSheet
        sheet = FileSheet(self.root, mode='insert', confirm_text='加入队列',
                          title='选择要打印的文件')
        paths = sheet.wait(self.root)
        if paths:
            self.add_paths(paths)

    def _add_folder(self):
        """选文件夹：用我们自己画的那个面板（比系统对话框顺手）。"""
        from gui.file_sheet import FileSheet
        sheet = FileSheet(self.root, mode='folder',
                          current_path=self.directory,
                          confirm_text='选择此文件夹')
        path = sheet.wait(self.root)
        if not path:
            return
        self.directory = path
        paths = []
        self._scan(path, paths, 0)
        if not paths:
            toast(self.root, '这个文件夹里没有可打印的文件', 'warn')
            return
        self.add_paths(paths)

    def _scan(self, directory, paths, depth):
        """递归收文件（层数与数量都有限制，免得卡住）。"""
        if depth > MAX_FOLDER_DEPTH or len(paths) >= MAX_FOLDER_FILES:
            return
        try:
            names = sorted(os.listdir(directory))
        except OSError:
            return
        for name in names:
            full = os.path.join(directory, name)
            if os.path.isdir(full):
                self._scan(full, paths, depth + 1)
            elif formats.ext_of(full) in formats.INSERTABLE_EXTS:
                paths.append(full)
                if len(paths) >= MAX_FOLDER_FILES:
                    return

    def add_paths(self, paths):
        """把文件加进队列（已有同名的不重复加）。"""
        existing = {job.path for job in self.queue.jobs}
        added = 0
        for path in paths:
            if path in existing:
                continue
            self.queue.add(PrintJob(path, options=PrintOptions(),
                                    printer=self._printer.name
                                    if self._printer else ''))
            added += 1
        self._sort_jobs()
        self._refresh_rows()
        self._log('加入 {} 个文件'.format(added))

    # ------------------------------------------------------------------
    # 排序
    # ------------------------------------------------------------------

    def _on_sort(self):
        self._sort_jobs()
        self._refresh_rows()
        label = self.sort_box.get()
        self._log('按{}排序'.format(label))

    def _sort_jobs(self):
        """按当前排序方式重排队列（"添加顺序"就是不动）。"""
        index = self.sort_box.current() if hasattr(self, 'sort_box') else 0
        mode = SORT_MODES[index][0] if 0 <= index < len(SORT_MODES) else 'manual'
        if mode == 'manual':
            return
        jobs = self.queue.jobs
        if mode == 'name':
            jobs.sort(key=lambda job: job.name.lower())
        elif mode == 'type':
            jobs.sort(key=lambda job: (formats.badge_of(job.path)
                                       if job.path else '', job.name.lower()))
        elif mode in ('mtime', 'size'):
            jobs.sort(key=lambda job: self._stat_of(job, mode),
                      reverse=(mode == 'mtime'))

    @staticmethod
    def _stat_of(job, mode):
        """取文件的修改时间/大小（取不到就排最后）。"""
        try:
            stat = os.stat(job.path)
        except OSError:
            return 0 if mode == 'size' else -1
        return stat.st_size if mode == 'size' else stat.st_mtime

    def _on_tree_click(self, event):
        """点表格：最后两列是上下箭头，用来手动调顺序。"""
        column = self.tree.identify_column(event.x)
        if not column:
            return
        index = int(column.replace('#', '')) - 1
        if index not in (UP_COLUMN, DOWN_COLUMN):
            return
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        job = self._rows.get(iid)
        if job is None:
            return
        self._move_job(job, -1 if index == UP_COLUMN else 1)
        return 'break'

    def _move_job(self, job, delta):
        """把某个文件在队列里上移/下移。"""
        jobs = self.queue.jobs
        try:
            position = jobs.index(job)
        except ValueError:
            return
        target = position + delta
        if target < 0 or target >= len(jobs):
            return
        jobs[position], jobs[target] = jobs[target], jobs[position]
        # 手动调过顺序，排序方式回到"添加顺序"，免得下一次刷新又排回去
        self.sort_box.current(0)
        self._refresh_rows()
        self._log('{} → 第 {} 位'.format(job.name, target + 1))

    def _remove_selected(self):
        selection = self.tree.selection()
        for iid in selection:
            job = self._rows.get(iid)
            if job is not None:
                self.queue.remove(job)
        self._refresh_rows()

    def _clear_queue(self):
        self.queue.clear()
        self._refresh_rows()

    def _edit_selected(self):
        selection = self.tree.selection()
        if not selection:
            return
        job = self._rows.get(selection[0])
        if job is None:
            return
        sheet = JobOptionsSheet(self.root, job, self._printer)
        sheet._place(self.root)
        self.root.wait_window(sheet)
        self._refresh_rows()

    def _refresh_rows(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._rows = {}
        total_jobs = len(self.queue.jobs)
        for index, job in enumerate(self.queue.jobs):
            options = job.options
            iid = 'job{}'.format(index)
            self._rows[iid] = job
            # 最后两列是上下箭头：第一行没有"上移"，最后一行没有"下移"
            up = '↑' if index > 0 else ''
            down = '↓' if index < total_jobs - 1 else ''
            self.tree.insert(
                '', 'end', iid=iid,
                values=(job.name, formats.badge_of(job.path) if job.path else '',
                        options.pages or '全部', str(options.copies),
                        {'color': '彩色', 'mono': '黑白'}.get(options.color,
                                                              '默认'),
                        {'one': '单面', 'long': '双面长边',
                         'short': '双面短边'}.get(options.duplex, '默认'),
                        job.state_text, up, down),
                tags=('failed',) if job.state == PrintState.FAILED
                else (('done',) if job.state == PrintState.DONE else ()))
        total = len(self.queue.jobs)
        done = sum(1 for job in self.queue.jobs
                   if job.state == PrintState.DONE)
        self.count_label.configure(
            text='{} 个文件'.format(total) if total else '')
        self.status_label_extra = '{} / {}'.format(done, total)

    # ------------------------------------------------------------------
    # 执行
    # ------------------------------------------------------------------

    def _on_defaults_change(self, issues):
        for job in self.queue.jobs:
            job.options = job.options.merged(self.form.options())
        self._refresh_rows()
        if issues:
            self._log('参数提示：{}'.format('；'.join(issues)))

    def _start(self):
        if not self.queue.jobs:
            toast(self.root, '队列是空的，先添加文件', 'warn')
            return
        if self._printer is None:
            toast(self.root, '没有可用的打印机', 'warn')
            return
        for job in self.queue.jobs:
            if job.state in (PrintState.PENDING, PrintState.FAILED):
                job.state = PrintState.PENDING
                job.error = ''
        self.queue.start()
        self._log('开始打印 {} 个文件'.format(len(self.queue.jobs)))
        self._refresh_rows()

    def _pause(self):
        if self.queue.running:
            self.queue.pause()
            self._log('已暂停（已经提交的作业照打）')
        else:
            self.queue.resume()
            self._log('继续')

    def _cancel(self):
        self.queue.cancel()
        self._log('已取消')
        self._refresh_rows()

    def _retry_failed(self):
        jobs = self.queue.retry_failed()
        if not jobs:
            toast(self.root, '没有失败的任务', 'info')
            return
        self._log('{} 个失败任务已重置'.format(len(jobs)))
        self._refresh_rows()

    # ------------------------------------------------------------------
    # 状态与日志
    # ------------------------------------------------------------------

    def _on_event(self, job, state, message):
        """队列线程回调 → 丢到主线程处理（这里用 after 排队）。"""
        try:
            self.root.after(0, self._handle_event, job, state, message)
        except Exception:
            pass

    def _handle_event(self, job, state, message):
        self._log('{}：{}'.format(job.name, message))
        self._refresh_rows()

    def _log(self, text):
        self.log.configure(state='normal')
        self.log.insert('end', text + '\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    # ------------------------------------------------------------------

    def run(self):
        """独立运行时进主循环。"""
        if self.standalone:
            self.root.mainloop()


class JobOptionsSheet(Sheet):
    """单个队列项的参数覆盖。"""

    def __init__(self, parent, job, printer=None):
        super().__init__(parent, '改参数 · {}'.format(job.name))
        self.job = job
        self.printer = printer
        self.form = PrintOptionsForm(self.body_frame, bg=PAPER,
                                      show_pages=True,
                                      on_change=lambda issues: None)
        self.form.pack(fill='x')
        if printer is not None:
            self.form.set_printer(printer)
        self.form.set_options(job.options)
        self._build_footer()

    def _build_footer(self):
        FlatButton(self.button_frame, '恢复默认', command=self._reset,
                   variant='ghost', bg=PAPER).pack(side='left', pady=2)
        FlatButton(self.button_frame, '确定', command=self._confirm,
                   variant='primary', bg=PAPER).pack(side='right', pady=2)
        FlatButton(self.button_frame, '取消', command=self._cancel,
                   variant='ghost', bg=PAPER).pack(side='right', padx=(0, 8),
                                                  pady=2)

    def _reset(self):
        self.job.options = PrintOptions()
        self.form.set_options(self.job.options)
        self._confirm()

    def _confirm(self):
        self.job.options = self.form.options()
        self.result = True
        self.destroy()
