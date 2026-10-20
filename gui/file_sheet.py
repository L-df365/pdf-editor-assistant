"""快速入口文件面板。

替代系统文件对话框（Tk 内置的 tk_getOpenFile 是 1994 年的英文灰框），
但保留「浏览全部文件…」作为网络位置、特殊权限等场景的兜底出口。

两个要点：
- 「当前文档所在文件夹」置顶，插入流程默认打开这个目录 —— 要合成的东西
  通常就在同一个文件夹里。
- 插入模式支持多选，插入顺序按文件名字典序。
"""

import os
import time
import tkinter as tk
from tkinter import ttk

from core import formats
from core.settings import load_recent
from gui.feedback import Sheet
from gui.theme import (ACCENT, ACCENT_TINT, INK, INK_2, INK_3, LINE, PAPER,
                        SURFACE, font)

HOME = os.path.expanduser('~')
RECENT = '__recent__'


def _human_size(size):
    if not size:
        return '0 B'
    value = float(size)
    for unit in ('B', 'KB', 'MB', 'GB'):
        if value < 1024 or unit == 'GB':
            if unit == 'B':
                return '{:.0f} B'.format(value)
            return '{:.1f} {}'.format(value, unit)
        value /= 1024.0


def _human_time(timestamp):
    return time.strftime('%m-%d %H:%M', time.localtime(timestamp))


class FileSheet(Sheet):
    """文件选择面板。

    mode='open'   单选，PDF 文档
    mode='insert' 多选，可插入的文件类型
    """

    def __init__(self, parent, mode='open', current_path=None,
                 confirm_text='打开', on_browse=None, on_confirm=None):
        self.mode = mode
        self.multi = mode == 'insert'
        self.current_path = current_path
        self.on_browse = on_browse
        self.on_confirm = on_confirm
        self.cwd = os.path.dirname(os.path.abspath(current_path)) \
            if current_path else HOME
        self.directory = self.cwd
        self.selected = set()
        self.rows = []

        title = '插入文件' if self.multi else '打开 PDF'
        super().__init__(parent, title)

        self._build_body()
        self._build_footer(confirm_text)
        self._load_directory(self.cwd)

    # ------------------------------------------------------------------
    # 构建
    # ------------------------------------------------------------------

    def _build_body(self):
        body = self.body_frame
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        # 左：常用位置
        left = ttk.Frame(body, style='Paper.TFrame')
        left.grid(row=0, column=0, sticky='nsw', padx=(0, 12))
        ttk.Label(left, text='常用位置', style='Paper.TLabel',
                  font=font('meta'), foreground=INK_3).pack(anchor='w',
                                                            pady=(0, 6))
        self.loc_tree = ttk.Treeview(left, show='tree', height=8,
                                     style='Paper.Treeview')
        self.loc_tree.pack(fill='both', expand=True)
        self.loc_tree.bind('<<TreeviewSelect>>', self._on_location)

        # 中：文件列表
        middle = ttk.Frame(body, style='Paper.TFrame')
        middle.grid(row=0, column=1, sticky='nsew')
        columns = ('sel', 'name', 'type', 'mtime', 'size')
        self.tree = ttk.Treeview(middle, columns=columns, show='headings',
                                  selectmode='extended')
        self.tree.heading('sel', text='')
        self.tree.heading('name', text='名称',
                          command=lambda: self._sort_by('name'))
        self.tree.heading('type', text='类型',
                          command=lambda: self._sort_by('type'))
        self.tree.heading('mtime', text='修改时间',
                          command=lambda: self._sort_by('mtime'))
        self.tree.heading('size', text='大小',
                          command=lambda: self._sort_by('size'))
        self.tree.column('sel', width=26, stretch=False, anchor='center')
        self.tree.column('name', width=200, stretch=False, anchor='w')
        self.tree.column('type', width=52, stretch=False, anchor='w')
        self.tree.column('mtime', width=84, stretch=False, anchor='w')
        self.tree.column('size', width=62, stretch=False, anchor='e')
        self.tree.tag_configure('picked', foreground=ACCENT)
        self.tree.tag_configure('dim', foreground=INK_3)
        vsb = ttk.Scrollbar(middle, orient='vertical',
                             command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        middle.rowconfigure(0, weight=1)
        middle.columnconfigure(0, weight=1)
        self.tree.bind('<Button-1>', self._on_click)
        self.tree.bind('<Double-1>', self._on_double)

        # 右：预览
        right = ttk.Frame(body, style='Paper.TFrame')
        right.grid(row=0, column=2, sticky='nse', padx=(12, 0))
        ttk.Label(right, text='预览', style='Paper.TLabel', font=font('meta'),
                  foreground=INK_3).pack(anchor='w', pady=(0, 6))
        self.preview_label = tk.Label(right, text='', bg=PAPER, fg=INK_3,
                                      font=font('meta'), width=16, height=6,
                                      justify='center')
        self.preview_label.pack(anchor='w')
        self.info_label = tk.Label(right, text='选一个文件看看',
                                   bg=PAPER, fg=INK_2, font=font('meta'),
                                   justify='left', width=16, anchor='w')
        self.info_label.pack(anchor='w', pady=(8, 0))

    def _build_footer(self, confirm_text):
        foot = self.button_frame
        ttk.Button(foot, text='浏览全部文件…', style='Paper.Secondary.TButton',
                   command=self._browse).pack(side='left')

        entry = ttk.Entry(foot, width=16, font=font('body'))
        entry.pack(side='left', padx=(12, 8))
        entry.insert(0, self.cwd)
        self.path_entry = entry
        entry.bind('<Return>', lambda e: self._confirm_entry())
        entry.bind('<FocusOut>', lambda e: self._sync_entry())

        self.confirm_button = ttk.Button(
            foot, text=confirm_text, style='Paper.Primary.TButton',
            command=self._confirm, state='disabled')
        self.confirm_button.pack(side='right')
        ttk.Button(foot, text='取消', style='Paper.Ghost.TButton',
                   command=self._cancel).pack(side='right', padx=(0, 8))
        self.selection_label = tk.Label(
            foot, text='', bg=ACCENT_TINT, fg=ACCENT,
            anchor='w', font=font('body', 'bold'), padx=12, pady=6)
        self.selection_label.pack(side='right', padx=(0, 12))
        self.selection_label.pack_forget()
        if self.multi:
            ttk.Button(foot, text='全选', style='Paper.Ghost.TButton',
                       command=self._select_all).pack(side='left',
                                                       padx=(8, 0))

    # ------------------------------------------------------------------
    # 常用位置
    # ------------------------------------------------------------------

    def _locations(self):
        """常用位置：当前文档所在文件夹固定在最上面。"""
        places = []
        if self.current_path:
            folder = os.path.dirname(os.path.abspath(self.current_path))
            places.append(('当前文档所在文件夹', folder))
        places.append(('最近使用', RECENT))
        for label, path in (('桌面', os.path.join(HOME, 'Desktop')),
                            ('下载', os.path.join(HOME, 'Downloads')),
                            ('主目录', HOME)):
            if os.path.isdir(path):
                places.append((label, path))
        return places

    def _refresh_locations(self):
        self.loc_tree.delete(*self.loc_tree.get_children())
        for label, path in self._locations():
            self.loc_tree.insert('', 'end', text=label, values=(path,))

    def _on_location(self, event=None):
        selection = self.loc_tree.selection()
        if not selection:
            return
        path = self.loc_tree.item(selection[0], 'values')[0]
        if path == RECENT:
            self._load_recent()
        else:
            self._load_directory(path)

    # ------------------------------------------------------------------
    # 文件列表
    # ------------------------------------------------------------------

    def _load_recent(self):
        """最近使用：把最近打开过的文件列在中间。"""
        self.directory = RECENT
        self.tree.delete(*self.tree.get_children())
        self.rows = []
        for full in load_recent():
            if not os.path.isfile(full):
                continue
            try:
                stat = os.stat(full)
            except OSError:
                continue
            self.rows.append({
                'path': full, 'name': os.path.basename(full),
                'type': formats.badge_of(full),
                'mtime': _human_time(stat.st_mtime),
                'size': _human_size(stat.st_size),
                'dir': False, 'mtime_raw': stat.st_mtime,
                'size_raw': stat.st_size})
        self._sort_by('mtime')
        self._update_selection_label()

    def _allowed(self, path):
        ext = formats.ext_of(path)
        if self.multi:
            return ext in formats.INSERTABLE_EXTS
        return ext in formats.PDF_EXTS

    def _load_directory(self, path):
        path = os.path.abspath(os.path.expanduser(path))
        if not os.path.isdir(path):
            return
        self.directory = path
        self.path_entry.delete(0, 'end')
        self.path_entry.insert(0, path)
        self._refresh_locations()
        self.tree.delete(*self.tree.get_children())
        self.rows = []
        try:
            names = sorted(os.listdir(path))
        except OSError:
            names = []
        for name in names:
            full = os.path.join(path, name)
            if os.path.isdir(full):
                self.rows.append({
                    'path': full, 'name': name + '/', 'type': '文件夹',
                    'mtime': _human_time(os.path.getmtime(full)),
                    'size': '', 'dir': True, 'mtime_raw': 0,
                    'size_raw': 0})
                continue
            if not self._allowed(full):
                continue
            try:
                stat = os.stat(full)
            except OSError:
                continue
            self.rows.append({
                'path': full, 'name': name,
                'type': formats.badge_of(full),
                'mtime': _human_time(stat.st_mtime),
                'size': _human_size(stat.st_size),
                'dir': False, 'mtime_raw': stat.st_mtime,
                'size_raw': stat.st_size})
        self._sort_by('name')
        self._update_selection_label()

    def _sort_by(self, key):
        self._sort_key = key
        if key == 'name':
            self.rows.sort(key=lambda r: (not r['dir'], r['name'].lower()))
        elif key == 'mtime':
            self.rows.sort(key=lambda r: (not r['dir'], -r['mtime_raw']))
        elif key == 'size':
            self.rows.sort(key=lambda r: (not r['dir'], -r['size_raw']))
        elif key == 'type':
            self.rows.sort(key=lambda r: (not r['dir'], r['type'],
                                          r['name'].lower()))
        self.tree.delete(*self.tree.get_children())
        for row in self.rows:
            mark = '✓' if row['path'] in self.selected else ''
            tags = ['picked'] if row['path'] in self.selected else []
            if row['path'] == self.current_path:
                tags.append('dim')
            self.tree.insert(
                '', 'end', iid=row['path'],
                values=(mark, row['name'], row['type'], row['mtime'],
                        row['size']),
                tags=tuple(tags))

    def _on_click(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        row = self._row(item)
        if row is None:
            return
        if row['dir']:
            self.tree.selection_set(item)
            return
        if self.multi:
            if item in self.selected:
                self.selected.discard(item)
            else:
                self.selected.add(item)
            self._sort_by(self._sort_key)
            self.tree.selection_set(item)
            self._update_preview(item)
            self._update_selection_label()
        else:
            self.selected = {item}
            self.tree.selection_set(item)
            self._update_preview(item)
            self._update_selection_label()

    def _on_double(self, event):
        item = self.tree.identify_row(event.y)
        if not item:
            return
        row = self._row(item)
        if row and row['dir']:
            self._load_directory(row['path'])
            return
        self._confirm()

    def _row(self, path):
        for row in self.rows:
            if row['path'] == path:
                return row
        return None

    def _select_all(self):
        self.selected = {row['path'] for row in self.rows if not row['dir']}
        self._sort_by(self._sort_key)
        self._update_selection_label()

    def _update_selection_label(self):
        count = len(self.selected)
        if count and self.multi:
            self.selection_label.configure(
                text='✓ 已选 {} 个文件'.format(count))
            if not self.selection_label.winfo_ismapped():
                self.selection_label.pack(side='right', padx=(0, 12))
        else:
            self.selection_label.configure(text='')
            if self.selection_label.winfo_ismapped():
                self.selection_label.pack_forget()
        self.confirm_button.configure(
            state='normal' if count else 'disabled')

    def _update_preview(self, path):
        row = self._row(path)
        if row is None:
            return
        if formats.ext_of(path) == '.pdf':
            try:
                import pymupdf
                from PIL import Image, ImageTk
                doc = pymupdf.open(path)
                page = doc.load_page(0)
                zoom = 150.0 / max(page.rect.width, 1)
                pix = page.get_pixmap(
                    matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                img = Image.frombytes('RGB', [pix.width, pix.height],
                                     pix.samples)
                photo = ImageTk.PhotoImage(img)
                doc.close()
                self.preview_label.configure(image=photo, text='')
                self.preview_label.image = photo
            except Exception:
                self.preview_label.configure(image='', text='无法预览')
        else:
            self.preview_label.configure(image='', text=row['type'])
        self.info_label.configure(
            text='{}\n{}\n{}'.format(row['name'], row['mtime'], row['size']))

    # ------------------------------------------------------------------
    # 确认
    # ------------------------------------------------------------------

    def _sync_entry(self):
        value = self.path_entry.get().strip()
        if value and os.path.isdir(os.path.abspath(os.path.expanduser(value))):
            self.directory = os.path.abspath(os.path.expanduser(value))

    def _confirm_entry(self):
        value = self.path_entry.get().strip()
        if not value:
            return
        path = os.path.abspath(os.path.expanduser(value))
        if os.path.isdir(path):
            self._load_directory(path)
            return
        if os.path.isfile(path):
            self.selected = {path}
            self._confirm()

    def _browse(self):
        if not self.on_browse:
            return
        path = self.on_browse(self.directory)
        if not path:
            return
        self.selected = {path}
        self._sort_by(self._sort_key)
        self._update_selection_label()
        self._update_preview(path)

    def _confirm(self):
        paths = sorted(self.selected)
        if not paths:
            return
        self.result = paths
        if self.on_confirm:
            self.on_confirm(paths)
        self.destroy()

    _sort_key = 'name'
