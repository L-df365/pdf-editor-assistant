import os
import queue
import sys
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading

from core.backends import installer
from core.pdf_document import PDFDocument
from core.settings import load_backend, save_backend
from gui.theme import init_theme
from gui.thumbnail_panel import ThumbnailPanel
from gui.preview_panel import PreviewPanel


HOME_DIR = '/home/user' if os.path.isdir('/home/user') else os.path.expanduser('~')

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
        init_theme(self.root)
        self.root.title('PDF 内嵌编辑助手')
        self.root.geometry('1100x700')
        self.root.minsize(800, 500)

        self.doc = PDFDocument()
        self.current_page = 0
        self._converting = False
        self._installing = False
        self._install_log = []

        if not os.environ.get('PDF_EDIT_BACKEND'):
            saved = load_backend()
            if saved:
                try:
                    self.doc.converter.set_backend(saved)
                    self.doc.converter.backend
                except RuntimeError:
                    self.doc.converter.set_backend('auto')

        self._last_backend = self._default_last_backend()
        self._backend_var = tk.StringVar(
            value=self.doc.converter.requested_name)
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

        self._build_menu()
        self._build_toolbar()
        self._build_main_area()
        self._build_statusbar()
        self._bind_shortcuts()

        self.root.after(250, self._check_backends_on_startup)

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
        file_menu.add_command(label='退出', command=self._on_close)
        menubar.add_cascade(label='文件', menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(
            label='插入文件到末尾',
            command=lambda: self.insert_file_at(self.doc.page_count))
        menubar.add_cascade(label='编辑', menu=edit_menu)

        settings_menu = tk.Menu(menubar, tearoff=0)
        backend_menu = tk.Menu(settings_menu, tearoff=0)
        self._backend_menu = backend_menu
        for name, label in self._backend_choices_for_ui():
            backend_menu.add_radiobutton(
                label=label,
                value=name,
                variable=self._backend_var,
                command=self._on_backend_changed)
        settings_menu.add_cascade(label='转换后端', menu=backend_menu)
        menubar.add_cascade(label='设置', menu=settings_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label='关于',
                              command=self._show_about)
        menubar.add_cascade(label='帮助', menu=help_menu)

        self.root.config(menu=menubar)

    def _build_toolbar(self):
        toolbar = ttk.Frame(self.root, style='Surface.TFrame')
        toolbar.pack(fill='x')
        ttk.Separator(self.root, orient='horizontal').pack(fill='x')

        ttk.Button(toolbar, text='打开 PDF',
                   command=self.open_pdf).pack(side='left', padx=4, pady=3)
        ttk.Button(toolbar, text='插入文件',
                   command=self.insert_file_dialog).pack(
                       side='left', padx=4, pady=3)
        ttk.Separator(toolbar, orient='vertical').pack(
            side='left', fill='y', padx=6, pady=6)
        ttk.Button(toolbar, text='左旋',
                   command=lambda: self.rotate_page(-90)).pack(
                       side='left', padx=4, pady=3)
        ttk.Button(toolbar, text='右旋',
                   command=lambda: self.rotate_page(90)).pack(
                       side='left', padx=4, pady=3)
        ttk.Separator(toolbar, orient='vertical').pack(
            side='left', fill='y', padx=6, pady=6)
        ttk.Button(toolbar, text='删除当前页',
                   command=self.delete_current_page).pack(
                       side='left', padx=4, pady=3)
        ttk.Button(toolbar, text='保存', style='Primary.TButton',
                   command=self.save_pdf).pack(
                       side='right', padx=4, pady=3)

        self._backend_labels = {
            label: name
            for name, label in self._backend_choices_for_ui()}
        self._backend_display = tk.StringVar(
            value=self._label_for_backend(
                self.doc.converter.requested_name))
        self._backend_combo = ttk.Combobox(
            toolbar,
            textvariable=self._backend_display,
            values=list(self._backend_labels),
            state='readonly',
            width=24)
        self._backend_combo.pack(side='right', padx=4, pady=3)
        self._backend_combo.bind(
            '<<ComboboxSelected>>', self._on_backend_combo)
        ttk.Label(toolbar, text='转换后端:').pack(
            side='right', padx=(8, 2), pady=3)

    def _label_for_backend(self, name):
        for label, value in self._backend_labels.items():
            if value == name:
                return label
        return next(iter(self._backend_labels))

    def _on_backend_combo(self, event=None):
        name = self._backend_labels.get(self._backend_display.get())
        if name:
            self._backend_var.set(name)
            self._on_backend_changed()

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
            self.root, text='就绪', style='Surface.TLabel', anchor='w',
            padding=(8, 4))
        self.statusbar.pack(fill='x', side='bottom')
        ttk.Separator(self.root, orient='horizontal').pack(
            fill='x', side='bottom')
        self._update_status(
            '就绪  |  转换后端: {}'.format(self._backend_label()))

    def _backend_choices_for_ui(self):
        status = {item['name']: item
                  for item in self.doc.converter.backend_status()}
        result = []
        for name, label in self.doc.converter.backend_choices():
            if name != 'auto' and not status.get(name, {}).get('available'):
                label = label + '（未安装）'
            result.append((name, label))
        return result

    def _backend_info(self, name):
        for item in self.doc.converter.backend_status():
            if item['name'] == name:
                return item
        return None

    def _default_last_backend(self):
        requested = self.doc.converter.requested_name
        status = self.doc.converter.backend_status()
        if requested == 'auto':
            return 'auto'
        for item in status:
            if item['name'] == requested and item['available']:
                return requested
        for item in status:
            if item['available']:
                return item['name']
        return 'auto'

    def _backend_label(self):
        try:
            return self.doc.converter.label
        except RuntimeError:
            return '未安装'

    def _on_backend_changed(self):
        if self._installing:
            return
        name = self._backend_var.get()
        if name != 'auto':
            info = self._backend_info(name)
            if info and not info['available']:
                self._prompt_install_backend(name, info)
                return
        self._apply_backend(name)

    def _apply_backend(self, name):
        try:
            self.doc.converter.set_backend(name)
            label = self.doc.converter.label
        except RuntimeError as exc:
            self._update_status('没有可用的文件转换后端')
            messagebox.showwarning(
                '转换后端不可用', str(exc), parent=self.root)
            self._revert_backend()
            return
        self._last_backend = name
        try:
            save_backend(name)
        except OSError:
            pass
        if hasattr(self, '_backend_display'):
            self._backend_display.set(self._label_for_backend(name))
        self._update_status('转换后端已切换: {}'.format(label))

    def _revert_backend(self):
        name = self._last_backend
        self._backend_var.set(name)
        if hasattr(self, '_backend_display'):
            self._backend_display.set(self._label_for_backend(name))
        try:
            self.doc.converter.set_backend(name)
        except Exception:
            pass

    def _check_backends_on_startup(self):
        if self._installing:
            return
        status = {item['name']: item
                  for item in self.doc.converter.backend_status()}
        if any(item['available'] for item in status.values()):
            return
        if installer.is_wps_installed():
            self._update_status('正在自动配置 WPS 转换支持...')
            self._start_backend_install(
                'wps', status['wps']['label'], auto=True)
            return
        if installer.is_libreoffice_installed():
            self._update_status('LibreOffice 已安装但暂不可用')
            return
        self._show_backend_choice()

    def _show_backend_choice(self):
        dialog = tk.Toplevel(self.root)
        dialog.title('需要文件转换工具')
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill='both', expand=True)
        ttk.Label(
            frame,
            justify='left',
            text=('未检测到 WPS Office 或 LibreOffice。\n\n'
                  '插入 Word / Excel 文件需要至少安装其中一个。\n'
                  'PDF 的打开、预览、旋转和保存不受影响。'),
        ).pack(anchor='w')

        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=(14, 0))

        def choose(name):
            keyword = installer.APP_STORE_QUERIES.get(name, name)
            try:
                self.root.clipboard_clear()
                self.root.clipboard_append(keyword)
            except tk.TclError:
                pass
            text = installer.open_app_store(name)
            dialog.destroy()
            self._update_status(text)

        ttk.Button(
            buttons, text='安装 WPS Office',
            command=lambda: choose('wps')).pack(side='left')
        ttk.Button(
            buttons, text='安装 LibreOffice',
            command=lambda: choose('libreoffice')).pack(
                side='left', padx=8)
        ttk.Button(
            buttons, text='稍后',
            command=dialog.destroy).pack(side='right')

        dialog.update_idletasks()
        x = self.root.winfo_rootx() + 80
        y = self.root.winfo_rooty() + 80
        dialog.geometry('+{}+{}'.format(x, y))

    def _prompt_install_backend(self, name, info):
        self._revert_backend()
        reason = info.get('reason') or '本机未安装该后端'
        message = (
            '未检测到 {}。\n\n{}\n\n'
            '是否现在下载并安装？\n'
            '安装完成后需要重启应用。'.format(info['label'], reason))
        if not messagebox.askyesno(
                '安装转换后端', message, parent=self.root):
            return
        self._start_backend_install(name, info['label'])

    def _start_backend_install(self, name, label, auto=False):
        self._installing = True
        self._install_log = []
        self._set_backend_controls_enabled(False)

        dialog = tk.Toplevel(self.root)
        dialog.title('安装 {}'.format(label))
        dialog.geometry('640x420')
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.protocol('WM_DELETE_WINDOW', lambda: None)

        ttk.Label(
            dialog,
            text='正在{} {}，请稍候...'.format(
                '自动配置' if auto else '安装', label),
        ).pack(anchor='w', padx=10, pady=(10, 4))
        progress = ttk.Progressbar(dialog, mode='indeterminate')
        progress.pack(fill='x', padx=10)
        progress.start(12)

        log_box = tk.Text(dialog, height=18, wrap='word', state='disabled')
        scroll = ttk.Scrollbar(dialog, command=log_box.yview)
        log_box.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y', pady=(8, 10))
        log_box.pack(fill='both', expand=True, padx=(10, 0), pady=(8, 10))

        events = queue.Queue()

        def append_log(text):
            self._install_log.append(text)
            events.put(('log', text))

        def task():
            try:
                message = installer.install_backend(name, log=append_log)
            except installer.ManualInstallRequired as exc:
                events.put(('done', (
                    name, label, str(exc), exc.url, None, auto)))
            except Exception as exc:
                events.put(('done', (
                    name, label, '', '', exc, auto)))
            else:
                events.put(('done', (
                    name, label, message, '', None, auto)))

        def poll():
            while True:
                try:
                    kind, payload = events.get_nowait()
                except queue.Empty:
                    break
                if kind == 'log':
                    log_box.configure(state='normal')
                    log_box.insert('end', payload + '\n')
                    log_box.see('end')
                    log_box.configure(state='disabled')
                elif kind == 'done':
                    self._install_done(dialog, progress, *payload)
                    return
            if self._installing:
                self.root.after(100, poll)

        threading.Thread(target=task, daemon=True).start()
        self.root.after(100, poll)

    def _install_done(self, dialog, progress, name, label,
                      message, url, error, auto=False):
        self._installing = False
        progress.stop()
        dialog.grab_release()
        dialog.destroy()
        self._set_backend_controls_enabled(True)

        if error is not None:
            detail = '\n'.join(self._install_log[-30:])
            if len(detail) > 2000:
                detail = '...' + detail[-2000:]
            messagebox.showerror(
                '安装失败',
                '{}\n\n{}'.format(error, detail),
                parent=self.root)
            self._update_status('后端安装失败')
            if auto:
                self._show_backend_choice()
            return

        try:
            save_backend(name)
        except OSError:
            pass

        if url:
            try:
                webbrowser.open(url)
            except Exception:
                pass
            messagebox.showinfo(
                '需要手动安装',
                '{}\n\n安装完成后请重启应用。'.format(message),
                parent=self.root)
            if messagebox.askyesno(
                    '重启应用',
                    '已完成手动安装？是否立即重启应用？',
                    parent=self.root):
                self._restart_app(name)
            else:
                self._update_status('安装完成后重启应用生效')
            return

        if messagebox.askyesno(
                '安装完成',
                '{}\n\n是否立即重启应用以启用该后端？'.format(message),
                parent=self.root):
            self._restart_app(name)
        else:
            self._update_status('安装完成，重启应用后生效')

    def _set_backend_controls_enabled(self, enabled):
        if hasattr(self, '_backend_combo'):
            self._backend_combo.configure(
                state='readonly' if enabled else 'disabled')
        if hasattr(self, '_backend_menu'):
            state = 'normal' if enabled else 'disabled'
            for index in range(self._backend_menu.index('end') + 1):
                self._backend_menu.entryconfigure(index, state=state)

    def _restart_app(self, backend=None):
        if self.doc.is_modified:
            if not messagebox.askyesno(
                    '未保存的修改',
                    '当前文档有未保存的修改，重启会丢失。是否继续？',
                    parent=self.root):
                return
        backend = backend or self.doc.converter.requested_name
        entry = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', 'main.py'))
        args = [sys.executable, entry, '--backend', backend]
        if self.doc.filepath:
            args.append(self.doc.filepath)
        try:
            os.execv(sys.executable, args)
        except OSError as exc:
            messagebox.showerror(
                '重启失败', str(exc), parent=self.root)

    def _on_close(self):
        if self._installing:
            messagebox.showinfo(
                '正在安装',
                '后端安装尚未完成，请稍候。',
                parent=self.root)
            return
        if self._converting:
            messagebox.showinfo(
                '正在转换',
                '文件转换尚未完成，请稍候。',
                parent=self.root)
            return
        self.root.destroy()

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
            '转换后端：{}（按需安装，不随应用打包）\n'
            '技术：Python + PyMuPDF + WPS(pywpsrpc)/LibreOffice'.format(
                self._backend_label()))

    def run(self):
        self.root.mainloop()
