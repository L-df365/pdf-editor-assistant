"""拆分文件面板。

拆什么、怎么拆、拆出来叫什么，全在这一个面板里定下来；
真正的拆分和命名交给 ``core.splitter`` / ``core.naming``。

预览用的计划和最后执行的计划是同一份（``SplitPlan``），
所以看到的文件名就是拆出来的文件名。
"""

import os
import queue
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from core import naming
from core.naming import Namer, NamingError
from core.splitter import (MODE_CHUNK, MODE_LABELS, MODE_PAGE, MODE_RANGES,
                           SplitError, count_pages, plan_split, split_pdf)
from gui.feedback import ErrorPanel, Sheet, attach_tooltip, toast
from gui.file_sheet import FileSheet
from gui.theme import DANGER, INK, INK_2, INK_3, LINE, OK, PAPER, font
from gui.widgets import FlatButton, Segmented

HOME_DIR = '/home/user' if os.path.isdir('/home/user') else os.path.expanduser('~')

#: 面板宽度（左右两栏 + 底部预览）
PANEL_WIDTH = 980

#: 预览表格最多铺多少行（几百页的文档全铺进去会卡）
MAX_PREVIEW = 300


class SplitSheet(Sheet):
    """拆分面板：方式 + 命名规则 + 实时预览。"""

    def __init__(self, parent, doc=None):
        super().__init__(parent, '拆分文件', panel_width=PANEL_WIDTH)
        self.doc = doc
        self._from_doc = bool(doc is not None and doc.doc is not None)
        self.source_path = doc.filepath if (self._from_doc and doc.filepath) \
            else ''
        self.source_name = os.path.basename(self.source_path) \
            if self.source_path else '未保存的文档.pdf'
        self.page_count = doc.page_count if self._from_doc else 0
        self.out_dir = os.path.dirname(self.source_path) \
            if self.source_path else HOME_DIR

        self._plan = None
        self._table = None
        self._column_index = 0
        self._busy = False
        self._messages = queue.Queue()
        self._refresh_job = None

        self._build()
        self.after(80, self._refresh)

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------

    def _build(self):
        body = self.body_frame
        body.columnconfigure(0, weight=0, minsize=330)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(2, weight=1)

        self._build_source(body)
        ttk.Separator(body, orient='horizontal').grid(
            row=1, column=0, columnspan=2, sticky='ew', pady=(0, 8))

        left = ttk.Frame(body, style='Paper.TFrame')
        left.grid(row=2, column=0, sticky='nsew', padx=(0, 18))
        right = ttk.Frame(body, style='Paper.TFrame')
        right.grid(row=2, column=1, sticky='nsew')

        self._build_mode(left)
        self._build_naming(right)
        self._build_preview(body)
        self._build_footer()
        self._sync_mode()

    def _section(self, parent, text):
        ttk.Label(parent, text=text, style='Paper.TLabel',
                  font=font('meta'), foreground=INK_3
                  ).pack(anchor='w', pady=(0, 6))

    def _line(self, parent, label, width=6):
        """一行「标签 + 控件」，返回这一行的容器。"""
        row = ttk.Frame(parent, style='Paper.TFrame')
        row.pack(fill='x', pady=(0, 6))
        ttk.Label(row, text=label, style='Paper.TLabel', font=font('meta'),
                  foreground=INK_2, width=width, anchor='w'
                  ).pack(side='left')
        return row

    def _build_source(self, body):
        row = ttk.Frame(body, style='Paper.TFrame')
        row.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 10))
        ttk.Label(row, text='源文件', style='Paper.TLabel', font=font('meta'),
                  foreground=INK_2, width=6, anchor='w').pack(side='left')
        self.source_label = ttk.Label(
            row, text=self._source_text(), style='Paper.TLabel',
            font=font('body'), foreground=INK)
        self.source_label.pack(side='left')
        FlatButton(row, '换一个文件…', command=self._pick_source,
                   variant='ghost', bg=PAPER).pack(side='right')

    def _source_text(self):
        if not self.page_count:
            return '还没有文档'
        return '{}　·　{} 页'.format(self.source_name, self.page_count)

    def _build_mode(self, parent):
        self._section(parent, '拆分方式')
        self.mode_choice = Segmented(parent, list(MODE_LABELS),
                                     value=MODE_PAGE,
                                     command=lambda v: self._on_mode_change())
        self.mode_choice.pack(anchor='w', pady=(0, 6))
        self.mode_note = tk.Label(parent, text='', bg=PAPER, fg=INK_3,
                                  font=font('meta'), justify='left',
                                  anchor='w', wraplength=300)
        self.mode_note.pack(anchor='w', pady=(0, 8))
        self._update_mode_note()

        row = self._line(parent, '每 N 页')
        self.chunk_spin = self._spin(row, 1, 1, 9999, width=5)
        ttk.Label(row, text='页一份', style='Paper.TLabel',
                  font=font('meta'), foreground=INK_3
                  ).pack(side='left', padx=(6, 0))

        row = self._line(parent, '页码范围')
        self.ranges_entry = ttk.Entry(row, font=font('body'), width=14)
        self.ranges_entry.pack(side='left')
        self.ranges_entry.bind('<KeyRelease>', lambda e: self._schedule())
        ttk.Label(row, text='如 1-3, 4-8', style='Paper.TLabel',
                  font=font('meta'), foreground=INK_3
                  ).pack(side='left', padx=(6, 0))

        self._section(parent, '输出位置')
        row = ttk.Frame(parent, style='Paper.TFrame')
        row.pack(fill='x', pady=(0, 6))
        self.dir_entry = ttk.Entry(row, font=font('body'))
        self.dir_entry.pack(side='left', fill='x', expand=True)
        self.dir_entry.insert(0, self.out_dir)
        self.dir_entry.bind('<KeyRelease>', lambda e: self._schedule())
        FlatButton(row, '选择…', command=self._pick_dir, variant='secondary',
                   bg=PAPER).pack(side='left', padx=(8, 0))

        self._section(parent, '查找替换（作用在最终文件名上）')
        row = ttk.Frame(parent, style='Paper.TFrame')
        row.pack(fill='x')
        self.find_entry = ttk.Entry(row, font=font('body'), width=11)
        self.find_entry.pack(side='left')
        ttk.Label(row, text='→', style='Paper.TLabel', font=font('meta'),
                  foreground=INK_3).pack(side='left', padx=5)
        self.replace_entry = ttk.Entry(row, font=font('body'), width=11)
        self.replace_entry.pack(side='left')
        self.regex_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text='正则', variable=self.regex_var,
                        style='Paper.TCheckbutton',
                        command=self._schedule).pack(side='left', padx=(6, 0))
        for entry in (self.find_entry, self.replace_entry):
            entry.bind('<KeyRelease>', lambda e: self._schedule())

        row = self._line(parent, '大小写')
        self.case_choice = Segmented(
            row, [('keep', '保持'), ('upper', '大写'), ('lower', '小写'),
                  ('title', '首字母')], value='keep',
            command=lambda v: self._schedule())
        self.case_choice.pack(side='left')

    def _build_naming(self, parent):
        self._section(parent, '命名规则')
        self.naming_choice = Segmented(
            parent,
            [('default', '原文件名 + 序号'),
             ('template', '自定义模板'),
             ('table', '表格名单')],
            value='default', command=lambda v: self._on_naming_change())
        self.naming_choice.pack(anchor='w', pady=(0, 12))

        row = self._line(parent, '前/后缀', width=7)
        self.prefix_entry = ttk.Entry(row, font=font('body'), width=12)
        self.prefix_entry.pack(side='left')
        ttk.Label(row, text='↔', style='Paper.TLabel', font=font('meta'),
                  foreground=INK_3).pack(side='left', padx=6)
        self.suffix_entry = ttk.Entry(row, font=font('body'), width=12)
        self.suffix_entry.pack(side='left')
        for entry in (self.prefix_entry, self.suffix_entry):
            entry.bind('<KeyRelease>', lambda e: self._schedule())

        row = self._line(parent, '模板', width=7)
        self.template_entry = ttk.Entry(row, font=font('body'))
        self.template_entry.pack(side='left', fill='x', expand=True)
        self.template_entry.insert(0, naming.DEFAULT_TEMPLATE)
        self.template_entry.bind('<KeyRelease>', lambda e: self._on_typed())

        tokens = ttk.Frame(parent, style='Paper.TFrame')
        tokens.pack(fill='x', pady=(0, 10), padx=(0, 0))
        ttk.Label(tokens, text='插入：', style='Paper.TLabel',
                  font=font('meta'), foreground=INK_3).pack(side='left')
        labels = dict(naming.TOKENS)
        for token in ('{name}', '{n}', '{N}', '{page}', '{date}'):
            button = FlatButton(tokens, token,
                                command=lambda t=token: self._insert(t),
                                variant='ghost', bg=PAPER)
            button.pack(side='left')
            attach_tooltip(button, labels.get(token, token))

        row = self._line(parent, '序号', width=7)
        ttk.Label(row, text='起始', style='Paper.TLabel', font=font('meta'),
                  foreground=INK_3).pack(side='left')
        self.start_spin = self._spin(row, 1, -99999, 99999, width=4)
        ttk.Label(row, text='步长', style='Paper.TLabel', font=font('meta'),
                  foreground=INK_3).pack(side='left', padx=(8, 0))
        self.step_spin = self._spin(row, 1, 1, 999, width=3)
        ttk.Label(row, text='位数', style='Paper.TLabel', font=font('meta'),
                  foreground=INK_3).pack(side='left', padx=(8, 0))
        self.digits_spin = self._spin(row, 0, 0, 8, width=3)

        row = self._line(parent, '名单', width=7)
        self.table_entry = ttk.Entry(row, font=font('body'), state='readonly')
        self.table_entry.pack(side='left', fill='x', expand=True)
        FlatButton(row, '选择…', command=self._pick_table, variant='secondary',
                   bg=PAPER).pack(side='left', padx=(8, 0))

        row = ttk.Frame(parent, style='Paper.TFrame')
        row.pack(fill='x', pady=(0, 6))
        ttk.Label(row, text='', width=7, style='Paper.TLabel'
                  ).pack(side='left')
        self.sheet_box = ttk.Combobox(row, state='disabled', width=10,
                                      font=font('meta'))
        self.sheet_box.pack(side='left')
        self.sheet_box.bind('<<ComboboxSelected>>',
                            lambda e: self._on_sheet_pick())
        self.column_box = ttk.Combobox(row, state='disabled', width=16,
                                       font=font('meta'))
        self.column_box.pack(side='left', padx=(6, 0))
        self.column_box.bind('<<ComboboxSelected>>',
                             lambda e: self._on_column_pick())
        self.header_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text='首行是表头', variable=self.header_var,
                        style='Paper.TCheckbutton',
                        command=self._on_header_toggle
                        ).pack(side='left', padx=(8, 0))

        self.table_note = tk.Label(parent, text='', bg=PAPER, fg=INK_3,
                                   font=font('meta'), justify='left',
                                   anchor='w', wraplength=540)
        self.table_note.pack(anchor='w', pady=(0, 6))


    def _build_preview(self, body):
        wrap = ttk.Frame(body, style='Paper.TFrame')
        wrap.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        head = ttk.Frame(wrap, style='Paper.TFrame')
        head.pack(fill='x', pady=(0, 6))
        ttk.Label(head, text='预览', style='Paper.TLabel',
                  font=font('meta'), foreground=INK_3).pack(side='left')
        self.summary_label = tk.Label(head, text='', bg=PAPER, fg=INK_2,
                                      font=font('meta'))
        self.summary_label.pack(side='left', padx=(10, 0))

        columns = ('n', 'pages', 'name')
        self.preview = ttk.Treeview(wrap, columns=columns, show='headings',
                                     height=4, style='Paper.Treeview')
        self.preview.heading('n', text='#')
        self.preview.heading('pages', text='页码', anchor='w')
        self.preview.heading('name', text='文件名', anchor='w')
        self.preview.column('n', width=46, stretch=False, anchor='center')
        self.preview.column('pages', width=110, stretch=False, anchor='w')
        self.preview.column('name', width=600, stretch=True, anchor='w')
        vsb = ttk.Scrollbar(wrap, orient='vertical',
                            command=self.preview.yview)
        self.preview.configure(yscrollcommand=vsb.set)
        self.preview.pack(side='left', fill='both', expand=True)
        vsb.pack(side='left', fill='y')

    def _build_footer(self):
        foot = self.button_frame
        self.open_button = FlatButton(foot, '打开输出文件夹',
                                      command=self._open_dir,
                                      variant='ghost', bg=PAPER)
        self.open_button.configure_state(False)
        self.open_button.pack(side='left')
        self.split_button = FlatButton(foot, '拆分', command=self._split,
                                       variant='primary', bg=PAPER)
        self.split_button.pack(side='right')
        FlatButton(foot, '取消', command=self._cancel, variant='ghost',
                   bg=PAPER).pack(side='right', padx=(0, 8))

        self.progress_label = tk.Label(foot, text='', bg=PAPER, fg=INK_3,
                                       font=font('meta'))
        self.progress_label.pack(side='right', padx=(0, 12))

    # ------------------------------------------------------------------
    # 小控件
    # ------------------------------------------------------------------

    def _spin(self, parent, value, low, high, width=4):
        spin = tk.Spinbox(parent, from_=low, to=high, width=width,
                          font=font('num'), justify='center',
                          bg=PAPER, fg=INK, relief='flat',
                          highlightbackground=LINE, highlightthickness=1,
                          buttonbackground=PAPER,
                          command=self._schedule)
        spin.delete(0, 'end')
        spin.insert(0, str(value))
        spin.pack(side='left')
        spin.bind('<KeyRelease>', lambda e: self._schedule())
        return spin

    def _insert(self, token):
        """点模板下面的占位符，插到光标处。"""
        entry = self.template_entry
        try:
            index = entry.index('insert')
        except tk.TclError:
            index = 'end'
        entry.insert(index, token)
        entry.focus_set()
        self._on_typed()

    def _regrab(self):
        """嵌套面板关掉后把模态抓取拿回来。"""
        try:
            self.grab_set()
            self.focus_set()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------

    def _on_mode_change(self):
        self._sync_mode()
        self._schedule()

    def _sync_mode(self):
        mode = self.mode_choice.get()
        self.chunk_spin.configure(
            state='normal' if mode == MODE_CHUNK else 'disabled')
        self.ranges_entry.configure(
            state='normal' if mode == MODE_RANGES else 'disabled')

    def _on_naming_change(self):
        mode = self.naming_choice.get()
        if mode == 'default':
            # 「原文件名 + 序号」就是默认模板，切回来时把模板一起复位
            self.template_entry.delete(0, 'end')
            self.template_entry.insert(0, naming.DEFAULT_TEMPLATE)
        if mode == 'table':
            self._on_header_toggle()
        self._schedule()

    def _on_typed(self):
        """手改了模板：命名规则自动切到「自定义模板」。"""
        if self.naming_choice.get() != 'template':
            self.naming_choice.set_value('template', notify=False)
        self._schedule()

    def _on_header_toggle(self):
        self._sync_columns()
        self._schedule()

    def _on_column_pick(self):
        index = self.column_box.current()
        if index >= 0:
            self._column_index = index
        self._sync_columns()
        self._schedule()

    def _on_sheet_pick(self):
        if not self._table:
            return
        sheet = self.sheet_box.get()
        try:
            self._table = naming.read_table(self._table.path, sheet=sheet)
        except NamingError as exc:
            self.table_note.configure(text=str(exc), foreground=DANGER)
            return
        self._sync_columns()
        self._schedule()

    # ------------------------------------------------------------------
    # 表格
    # ------------------------------------------------------------------

    def _pick_table(self):
        sheet = FileSheet(self, mode='open', exts=naming.TABLE_EXTS,
                          title='选择名单表格', confirm_text='选择',
                          on_browse=self._browse_table)
        paths = sheet.wait(self)
        self._regrab()
        if paths:
            self._load_table(paths[0])

    def _browse_table(self, directory):
        return filedialog.askopenfilename(
            parent=self, title='选择名单表格',
            initialdir=directory or HOME_DIR,
            filetypes=[('表格文件', '*.csv *.tsv *.txt *.xlsx *.xlsm'),
                       ('所有文件', '*.*')])

    def _load_table(self, path):
        try:
            data = naming.read_table(path)
        except NamingError as exc:
            self._table = None
            self.table_entry.configure(state='normal')
            self.table_entry.delete(0, 'end')
            self.table_entry.configure(state='readonly')
            self.table_note.configure(text=str(exc), foreground=DANGER)
            self._schedule()
            return
        self._table = data
        self.table_entry.configure(state='normal')
        self.table_entry.delete(0, 'end')
        self.table_entry.insert(0, path)
        self.table_entry.configure(state='readonly')

        if data.sheets:
            self.sheet_box.configure(state='readonly', values=data.sheets)
            self.sheet_box.current(data.sheets.index(data.sheet))
            self.sheet_box.pack(side='left', before=self.column_box)
        else:
            self.sheet_box.configure(values=('',))
            self.sheet_box.set('')
            self.sheet_box.pack_forget()
        self._column_index = 0
        self._sync_columns()
        self.naming_choice.set_value('table', notify=False)
        self._schedule()

    def _sync_columns(self):
        box = self.column_box
        if not self._table or not self._table.rows:
            box.configure(state='disabled', values=())
            self.table_note.configure(text='还没选名单表格', foreground=INK_3)
            return
        header = bool(self.header_var.get())
        labels = []
        for index in range(max(self._table.column_count, 1)):
            label = '第 {} 列'.format(index + 1)
            if header and index < len(self._table.headers):
                title = self._table.headers[index].strip()
                if title:
                    label = '{}（第 {} 列）'.format(title, index + 1)
            labels.append(label)
        box.configure(state='readonly', values=labels)
        box.current(min(self._column_index, len(labels) - 1))

        values = self._table.column_values(self._column_index,
                                           has_header=header)
        note = '名单 {} 行'.format(len(values))
        if self._table.sheets:
            note += '　·　工作表「{}」'.format(self._table.sheet)
        if not values:
            note += '（这一列是空的）'
        self.table_note.configure(text=note, foreground=INK_3)

    def _table_names(self):
        if not self._table or not self._table.rows:
            return None
        return self._table.column_values(
            self._column_index, has_header=bool(self.header_var.get()))

    # ------------------------------------------------------------------
    # 源文件 / 输出目录
    # ------------------------------------------------------------------

    def _pick_source(self):
        sheet = FileSheet(self, mode='open', title='选择要拆分的 PDF',
                          confirm_text='选择', on_browse=self._browse_source)
        paths = sheet.wait(self)
        self._regrab()
        if not paths:
            return
        path = paths[0]
        try:
            pages = count_pages(path)
        except SplitError as exc:
            ErrorPanel.show(self, '这个文件打不开', '换个 PDF 试试。',
                            detail=str(exc))
            self._regrab()
            return
        self.source_path = path
        self.source_name = os.path.basename(path)
        self.page_count = pages
        self._from_doc = False
        self.source_label.configure(text=self._source_text())
        if not self.dir_entry.get().strip() or \
                self.dir_entry.get().strip() == self.out_dir:
            self.out_dir = os.path.dirname(path)
            self.dir_entry.delete(0, 'end')
            self.dir_entry.insert(0, self.out_dir)
        self._schedule()

    def _browse_source(self, directory):
        return filedialog.askopenfilename(
            parent=self, title='选择要拆分的 PDF',
            initialdir=directory or HOME_DIR,
            filetypes=[('PDF 文件', '*.pdf'), ('所有文件', '*.*')])

    def _pick_dir(self):
        self.withdraw()
        try:
            self.grab_release()
        except tk.TclError:
            pass
        try:
            path = filedialog.askdirectory(
                parent=self, title='拆分后的文件放在哪里',
                initialdir=self.dir_entry.get().strip() or HOME_DIR)
        finally:
            self.deiconify()
            self._regrab()
        if path:
            self.dir_entry.delete(0, 'end')
            self.dir_entry.insert(0, path)
            self._schedule()

    def _open_dir(self):
        path = self._plan.out_dir if self._plan else self.out_dir
        if not os.path.isdir(path):
            toast(self, '这个文件夹还不存在', 'warn')
            return
        try:
            subprocess.Popen(['xdg-open', path])
        except OSError as exc:
            toast(self, '打不开文件夹：{}'.format(exc), 'error')

    # ------------------------------------------------------------------
    # 预览
    # ------------------------------------------------------------------

    def _schedule(self, *args):
        if self._refresh_job is not None:
            try:
                self.after_cancel(self._refresh_job)
            except (tk.TclError, ValueError):
                pass
        self._refresh_job = self.after(120, self._refresh)

    def _refresh(self):
        self._refresh_job = None
        if self._busy:
            return
        self._update_mode_note()
        try:
            plan = self._make_plan()
        except (SplitError, NamingError) as exc:
            self._plan = None
            self._note(str(exc), DANGER)
            self._fill([])
            self.split_button.configure_state(False)
            return
        self._plan = plan
        self._fill(plan.entries())
        self.split_button.configure_state(plan.total > 0)
        text = '共 {} 页 → {} 个文件'.format(plan.page_count, plan.total)
        if not plan.overwrite and plan.names and \
                any(name.endswith(' (2).pdf') for name in plan.names):
            text += '　·　同名文件自动加了 (2)'
        if self.naming_choice.get() == 'table':
            names = self._table_names() or []
            if len(names) < plan.total:
                text += '　·　名单只有 {} 行，其余按模板命名'.format(len(names))
        self._note(text, INK_2)

    def _note(self, text, color):
        self.summary_label.configure(text=text, foreground=color)

    def _fill(self, entries):
        self.preview.delete(*self.preview.get_children())
        for number, pages, name in entries[:MAX_PREVIEW]:
            self.preview.insert('', 'end', values=(number, pages, name))
        if len(entries) > MAX_PREVIEW:
            self.preview.insert(
                '', 'end', values=('…', '',
                                   '其余 {} 个不铺开预览'.format(
                                       len(entries) - MAX_PREVIEW)))

    def _update_mode_note(self):
        mode = self.mode_choice.get()
        parts = {
            MODE_PAGE: '每页存成一个文件。',
            MODE_CHUNK: '按固定页数分段。',
            MODE_RANGES: '一段页码范围存一个文件。',
        }
        self.mode_note.configure(text=parts.get(mode, ''))

    def _make_plan(self):
        if not self.page_count:
            raise SplitError('还没有打开要拆分的文档')
        out_dir = self.dir_entry.get().strip() or ''
        if not out_dir:
            raise SplitError('先选一个输出位置')
        out_dir = os.path.abspath(os.path.expanduser(out_dir))
        if os.path.exists(out_dir) and not os.path.isdir(out_dir):
            raise SplitError('输出位置是个文件，不是文件夹')

        naming_mode = self.naming_choice.get()
        names = ()
        if naming_mode == 'table':
            names = self._table_names()
            if not names:
                raise NamingError('还没选名单表格，或者表里没有名字')

        namer = Namer(
            template=self.template_entry.get().strip(),
            start=self._number(self.start_spin, '起始序号'),
            step=self._number(self.step_spin, '步长'),
            digits=self._number(self.digits_spin, '位数'),
            prefix=self.prefix_entry.get().strip(),
            suffix=self.suffix_entry.get().strip(),
            find=self.find_entry.get(),
            replace=self.replace_entry.get(),
            regex=bool(self.regex_var.get()),
            case=self.case_choice.get(),
            names=names or ())
        return plan_split(
            self.page_count, self.source_name, out_dir,
            mode=self.mode_choice.get(),
            chunk=self._number(self.chunk_spin, '每 N 页'),
            ranges_text=self.ranges_entry.get(),
            namer=namer)

    @staticmethod
    def _number(widget, label):
        text = widget.get().strip()
        try:
            return int(text)
        except ValueError:
            raise NamingError('{}要填整数'.format(label))

    # ------------------------------------------------------------------
    # 拆分
    # ------------------------------------------------------------------

    def _cancel(self):
        if self._busy:
            toast(self, '正在拆分，完成后再关闭', 'warn')
            return
        super()._cancel()

    def _split(self):
        if self._busy:
            return
        try:
            plan = self._make_plan()
        except (SplitError, NamingError) as exc:
            self._note(str(exc), DANGER)
            return
        self._plan = plan
        source, temp_dir = self._prepare_source()
        if source is None:
            return

        self._busy = True
        self.split_button.configure_state(False)
        self.progress_label.configure(text='正在拆分…', foreground=INK_2)
        thread = threading.Thread(target=self._worker,
                                  args=(source, plan, temp_dir), daemon=True)
        thread.start()
        self.after(80, self._poll)

    def _prepare_source(self):
        """要拆的文件：当前文档用内存快照（没保存的改动也算数）。"""
        if not self._from_doc:
            return self.source_path, None
        temp_dir = tempfile.mkdtemp(prefix='pdf_split_')
        path = os.path.join(temp_dir, self.source_name or 'document.pdf')
        try:
            self.doc.snapshot(path)
        except Exception as exc:
            shutil.rmtree(temp_dir, ignore_errors=True)
            ErrorPanel.show(self, '准备文件失败', '当前文档没能写出临时副本。',
                            detail=str(exc))
            self._regrab()
            return None, None
        return path, temp_dir

    def _worker(self, source, plan, temp_dir):
        try:
            report = split_pdf(
                source, plan,
                progress=lambda done, total, name: self._messages.put(
                    ('progress', (done, total))))
            self._messages.put(('done', report))
        except Exception as exc:
            self._messages.put(('error', exc))
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _poll(self):
        """轮询后台线程的消息（Tk 控件只能在主线程里碰）。"""
        try:
            while True:
                kind, payload = self._messages.get_nowait()
                if kind == 'progress':
                    done, total = payload
                    self.progress_label.configure(
                        text='正在拆分 {}/{}…'.format(done, total))
                elif kind == 'done':
                    self._finish(payload)
                    return
                else:
                    self._fail(payload)
                    return
        except queue.Empty:
            pass
        except tk.TclError:
            # 窗口已经关了（拆到一半退出应用时）
            return
        if self._busy:
            try:
                self.after(80, self._poll)
            except tk.TclError:
                pass

    def _finish(self, report):
        self._busy = False
        self.open_button.configure_state(True)
        self.split_button.configure_state(True)
        self.result = report
        if report.failures:
            self.progress_label.configure(
                text='已拆成 {} 个，{} 个失败'.format(report.count,
                                                    len(report.failures)),
                foreground=DANGER)
            detail = '\n'.join('{}：{}'.format(name, error)
                               for name, error in report.failures)
            ErrorPanel.show(
                self, '有 {} 份没拆出来'.format(len(report.failures)),
                '其余文件已经拆好了，失败的那几份可以再点一次「拆分」重试。',
                detail=detail)
            self._regrab()
            return
        self.progress_label.configure(
            text='已拆成 {} 个文件'.format(report.count), foreground=OK)
        self.split_button.set_text('完成')
        self.split_button.set_command(self.destroy)
        toast(self.master, '已拆成 {} 个文件'.format(report.count), 'ok')

    def _fail(self, error):
        self._busy = False
        self.split_button.configure_state(True)
        self.progress_label.configure(text='拆分失败', foreground=DANGER)
        ErrorPanel.show(self, '拆分失败', '文件没有拆出来，输出目录里可能留下'
                        '了部分文件。', detail=str(error))
        self._regrab()

    # ------------------------------------------------------------------

    @staticmethod
    def show(parent, doc=None):
        sheet = SplitSheet(parent, doc)
        sheet._place(parent)
        parent.wait_window(sheet)
        return sheet.result
