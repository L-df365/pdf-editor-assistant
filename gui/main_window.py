import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading

from core.pdf_document import PDFDocument
from gui.thumbnail_panel import ThumbnailPanel
from gui.preview_panel import PreviewPanel


HOME_DIR = '/home/user' if os.path.isdir('/home/user') else HOME_DIR

FILETYPES = [
    ('所有支持的文件',
     '*.pdf *.docx *.doc *.xlsx *.xls *.pptx *.ppt '
     '*.png *.jpg *.jpeg *.bmp *.gif *.tiff'),
    ('PDF 文件', '*.pdf'),
    ('Word 文档', '*.docx *.doc'),
    ('Excel 表格', '*.xlsx *.xls'),
    ('PowerPoint 演示', '*.pptx *.ppt'),
    ('图片文件', '*.png *.jpg *.jpeg *.bmp *.gif *.tiff'),
    ('所有文件', '*.*'),
]


class MainWindow:
    """主窗口。"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title('PDF 内嵌编辑助手')
        self.root.geometry('1100x700')
        self.root.minsize(800, 500)

        self.doc = PDFDocument()
        self.current_page = 0
        self._converting = False

        self._build_menu()
        self._build_toolbar()
        self._build_main_area()
        self._build_statusbar()
        self._bind_shortcuts()

    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label='打开 PDF  (Ctrl+O)',
                              command=self.open_pdf, accelerator='Ctrl+O')
        file_menu.add_command(label='保存  (Ctrl+S)',
                              command=self.save_pdf, accelerator='Ctrl+S')
        file_menu.add_command(label='另存为  (Ctrl+Shift+S)',
                              command=self.save_as, accelerator='Ctrl+Shift+S')
        file_menu.add_separator()
        file_menu.add_command(label='退出', command=self.root.quit)
        menubar.add_cascade(label='文件', menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(
            label='插入文件到末尾',
            command=lambda: self.insert_file_at(self.doc.page_count))
        menubar.add_cascade(label='编辑', menu=edit_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label='关于',
                              command=self._show_about)
        menubar.add_cascade(label='帮助', menu=help_menu)

        self.root.config(menu=menubar)

    def _build_toolbar(self):
        toolbar = ttk.Frame(self.root, relief='raised')
        toolbar.pack(fill='x', padx=2, pady=2)

        ttk.Button(toolbar, text='打开 PDF',
                   command=self.open_pdf).pack(side='left', padx=4, pady=3)
        ttk.Button(toolbar, text='插入文件',
                   command=self.insert_file_dialog).pack(
                       side='left', padx=4, pady=3)
        ttk.Separator(toolbar, orient='vertical').pack(
            side='left', fill='y', padx=6, pady=3)
        ttk.Button(toolbar, text='左旋',
                   command=lambda: self.rotate_page(-90)).pack(
                       side='left', padx=4, pady=3)
        ttk.Button(toolbar, text='右旋',
                   command=lambda: self.rotate_page(90)).pack(
                       side='left', padx=4, pady=3)
        ttk.Separator(toolbar, orient='vertical').pack(
            side='left', fill='y', padx=6, pady=3)
        ttk.Button(toolbar, text='删除当前页',
                   command=self.delete_current_page).pack(
                       side='left', padx=4, pady=3)
        ttk.Button(toolbar, text='保存',
                   command=self.save_pdf).pack(
                       side='right', padx=4, pady=3)

    def _build_main_area(self):
        paned = ttk.PanedWindow(self.root, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=2, pady=2)

        left_frame = ttk.Frame(paned, width=200)
        self.thumb_panel = ThumbnailPanel(
            left_frame,
            on_select=self._on_page_select,
            on_reorder=self._on_reorder,
            on_delete=self._on_delete_page,
            on_rotate=self._on_rotate_page,
            on_insert_after=self._on_insert_after,
        )
        self.thumb_panel.pack(fill='both', expand=True)
        paned.add(left_frame, weight=0)

        right_frame = ttk.Frame(paned)
        self.preview = PreviewPanel(right_frame)
        self.preview.pack(fill='both', expand=True)
        paned.add(right_frame, weight=1)

    def _build_statusbar(self):
        self.statusbar = ttk.Label(
            self.root, text='就绪', relief='sunken', anchor='w')
        self.statusbar.pack(fill='x', side='bottom', padx=2, pady=2)

    def _bind_shortcuts(self):
        self.root.bind('<Control-o>', lambda e: self.open_pdf())
        self.root.bind('<Control-s>', lambda e: self.save_pdf())
        self.root.bind('<Control-Shift-S>', lambda e: self.save_as())

    def _update_status(self, text):
        self.statusbar.configure(text=text)

    def _update_title(self):
        name = os.path.basename(self.doc.filepath) if self.doc.filepath else '未命名'
        mod = ' *' if self.doc.is_modified else ''
        self.root.title(f'{name}{mod} - PDF 内嵌编辑助手')

    # ---------- 文件操作 ----------

    def open_file(self, path):
        if not path or not os.path.isfile(path):
            return
        try:
            self.doc.close()
            self.doc.open(path)
            self.current_page = 0
            self.thumb_panel.load_document(self.doc)
            self._show_page(0)
            self._update_status(f'已加载: {path}  |  共 {self.doc.page_count} 页')
            self._update_title()
        except Exception as e:
            messagebox.showerror('打开失败', str(e))

    def open_pdf(self):
        path = filedialog.askopenfilename(
            title='打开 PDF 文件',
            initialdir=HOME_DIR,
            filetypes=[('PDF 文件', '*.pdf'), ('所有文件', '*.*')])
        if not path:
            return
        self.open_file(path)

    def save_pdf(self):
        if not self.doc.doc:
            return
        if not self.doc.filepath:
            self.save_as()
            return
        try:
            self.doc.save()
            self._update_status('已保存')
            self._update_title()
        except Exception as e:
            messagebox.showerror('保存失败', str(e))

    def save_as(self):
        if not self.doc.doc:
            return
        path = filedialog.asksaveasfilename(
            title='另存为',
            initialdir=HOME_DIR,
            defaultextension='.pdf',
            filetypes=[('PDF 文件', '*.pdf')])
        if not path:
            return
        try:
            self.doc.save(path)
            self._update_status(f'已保存: {path}')
            self._update_title()
        except Exception as e:
            messagebox.showerror('保存失败', str(e))

    # ---------- 页面操作 ----------

    def _show_page(self, page_num):
        if not self.doc.doc:
            return
        page_num = max(0, min(page_num, self.doc.page_count - 1))
        self.current_page = page_num
        self.preview.set_last(self.doc, page_num)
        self.preview.show_page(self.doc, page_num)
        self.thumb_panel.select_page(page_num)

    def _on_page_select(self, page_num):
        self._show_page(page_num)

    def _on_reorder(self, from_pos, to_pos):
        try:
            self.doc.move_page(from_pos, to_pos)
            self.thumb_panel.refresh()
            self.current_page = to_pos
            self.thumb_panel.select_page(to_pos)
            self._show_page(to_pos)
            self._update_title()
        except Exception as e:
            messagebox.showerror('移动失败', str(e))

    def _on_delete_page(self, page_num):
        if self.doc.page_count <= 1:
            messagebox.showwarning('提示', '至少保留一页')
            return
        if not messagebox.askyesno(
                '确认', f'确定删除第 {page_num + 1} 页？'):
            return
        try:
            self.doc.delete_page(page_num)
            self.thumb_panel.refresh()
            new_pos = min(page_num, self.doc.page_count - 1)
            self._show_page(new_pos)
            self._update_title()
        except Exception as e:
            messagebox.showerror('删除失败', str(e))

    def _on_rotate_page(self, page_num):
        try:
            self.doc.rotate_page(page_num, 90)
            self.thumb_panel.refresh_page(page_num)
            self._show_page(page_num)
            self._update_title()
        except Exception as e:
            messagebox.showerror('旋转失败', str(e))

    def rotate_page(self, angle):
        self._on_rotate_page(self.current_page)

    def delete_current_page(self):
        self._on_delete_page(self.current_page)

    # ---------- 插入文件 ----------

    def _on_insert_after(self, page_num):
        path = filedialog.askopenfilename(
            title='选择要插入的文件',
            initialdir=HOME_DIR,
            filetypes=FILETYPES)
        if not path:
            return
        self._do_insert(path, page_num + 1)

    def insert_file_dialog(self):
        path = filedialog.askopenfilename(
            title='选择要插入的文件',
            initialdir=HOME_DIR,
            filetypes=FILETYPES)
        if not path:
            return
        pos = self._ask_insert_position()
        if pos is not None:
            self._do_insert(path, pos)

    def insert_file_at(self, position):
        path = filedialog.askopenfilename(
            title='选择要插入的文件',
            initialdir=HOME_DIR,
            filetypes=FILETYPES)
        if not path:
            return
        self._do_insert(path, position)

    def _ask_insert_position(self):
        dialog = tk.Toplevel(self.root)
        dialog.title('选择插入位置')
        dialog.geometry('300x150')
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text='插入到第几页前？').pack(padx=15, pady=10)

        var = tk.IntVar(value=self.current_page + 1)
        max_val = self.doc.page_count + 1 if self.doc.doc else 1
        spin = ttk.Spinbox(dialog, from_=1, to=max_val,
                           textvariable=var, width=10)
        spin.pack(pady=5)

        result = [None]

        def on_ok():
            result[0] = var.get() - 1
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text='确定', command=on_ok).pack(
            side='left', padx=10)
        ttk.Button(btn_frame, text='取消', command=on_cancel).pack(
            side='left', padx=10)

        self.root.wait_window(dialog)
        return result[0]

    def _do_insert(self, filepath, position):
        if self._converting:
            return
        self._converting = True
        self._update_status('正在转换并插入文件，请稍候...')
        self.root.config(cursor='watch')
        self.root.update()

        def task():
            try:
                self.doc.insert_file(filepath, position)
                self.root.after(0, self._insert_done, position, None)
            except Exception as e:
                self.root.after(0, self._insert_done, position, e)

        threading.Thread(target=task, daemon=True).start()

    def _insert_done(self, position, error):
        self._converting = False
        self.root.config(cursor='')
        if error:
            messagebox.showerror('插入失败', str(error))
            self._update_status('插入失败')
            return

        self.thumb_panel.refresh()
        new_page = min(position, self.doc.page_count - 1)
        self._show_page(new_page)
        self._update_title()
        self._update_status(
            f'已插入文件，当前共 {self.doc.page_count} 页')

    def _show_about(self):
        messagebox.showinfo(
            '关于',
            'PDF 内嵌编辑助手\n\n'
            '功能：打开 PDF，在任意位置插入 Word/Excel/图片\n'
            '自动转换为 PDF 页面，支持拖拽排序\n\n'
            '技术：Python + PyMuPDF + LibreOffice')

    def run(self):
        self.root.mainloop()
