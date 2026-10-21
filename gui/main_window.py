import os
import queue
import sys
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog
import threading

from core.backends import installer
from core.pdf_document import PDFDocument
from core.settings import load_backend, load_recent, save_backend
from gui.backend_dialog import BackendDialog
from core import formats
from core.settings import push_recent
from gui.feedback import ConfirmPanel, ErrorPanel, InfoPanel, toast
from gui.empty_state import EmptyState
from gui.file_sheet import FileSheet
from gui.insert_sheet import InsertSheet
from gui.widgets import FlatButton
from gui.menu import MenuPopover, accel_label, build
from gui.theme import (ACCENT, INK_2, INK_3, MARKER, OK, SURFACE, font,
                        init_theme)
from gui.thumbnail_panel import ThumbnailPanel
from gui.preview_panel import PreviewPanel
from gui.version import VERSION


HOME_DIR = '/home/user' if os.path.isdir('/home/user') else os.path.expanduser('~')


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
        self._menus = []
        self._menu_cache = {}
        self._installing = False
        self._install_log = []
        self._tasks = queue.Queue()
        self._pending_paths = []
        self._batch_windows = []
        # 页面轨默认就是"一列的宽度"：一列页样放得下，右边不留空白
        self._rail_width = 210
        self.RAIL_MIN_WIDTH = 170  # 再窄就没法用了（下限，防止被挤没）

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

        self._build_topbar()
        self._build_main_area()
        self._build_statusbar()
        self._bind_shortcuts()

        self.root.after(250, self._check_backends_on_startup)
        self.root.after(120, self._poll_tasks)

    def _build_topbar(self):
        """顶栏：左侧文字菜单（文件 / 插入 / 设置 / 帮助），右侧 保存 + ⋯。

        文件名由窗口标题栏承担，顶栏不重复。
        """
        bar = ttk.Frame(self.root, style='Surface.TFrame')
        bar.pack(fill='x')
        ttk.Separator(self.root, orient='horizontal').pack(fill='x')

        self._menu_items = {}
        for label, builder in (('文件', self._menu_file),
                               ('插入', self._menu_insert),
                               ('设置', self._menu_settings),
                               ('帮助', self._menu_help)):
            # 菜单在"松手"时打开：按下就开会和菜单自己的"点外面关闭"
            # 打架，表现为点一下没反应。
            button = FlatButton(bar, label, variant='menu', bg=SURFACE)
            button.set_command(
                lambda b=button, fn=builder: self._open_top_menu(fn, b))
            button.pack(side='left', padx=(2, 2), pady=6)
            self._menu_items[label] = button

        FlatButton(bar, '⋯', command=self._show_more_menu, variant='ghost',
                   bg=SURFACE, width=32).pack(side='right', padx=(2, 12),
                                             pady=6)
        self._dirty_dot = tk.Canvas(bar, width=10, height=10,
                                    highlightthickness=0, bg=SURFACE)
        self._dirty_dot.pack(side='right', padx=(0, 2))
        self._save_button = FlatButton(
            bar, '保存', command=self.save_pdf, variant='primary', bg=SURFACE)
        self._save_button.pack(side='right', padx=(0, 4), pady=6)

    def _open_top_menu(self, builder, button):
        """点顶栏的文字项：弹出菜单浮层（浮层实例复用，不再每次重建）。"""
        menu = self._menu_cache.get(builder)
        if menu is None:
            menu = MenuPopover(self.root, builder())
            self._menu_cache[builder] = menu
        else:
            menu.set_items(builder())
        if menu not in self._menus:
            self._menus.append(menu)
        menu.show(button.winfo_rootx(),
                  button.winfo_rooty() + button.winfo_height() + 2)

    def _menu_file(self):
        return build([
            ('打开 PDF…', self.open_pdf, accel_label('Ctrl+O')),
            # 第 5 个位置是 danger、第 6 个才是 enabled：
            # 没有最近文件时这一条要置灰，而不是变红
            ('打开最近文件…', self._open_recent, accel_label('Ctrl+Shift+O'),
             '', False, bool(load_recent())),
            None,
            ('保存', self.save_pdf, accel_label('Ctrl+S')),
            ('另存为…', self.save_as, accel_label('Ctrl+Shift+S')),
            ('打印…', self.print_document, accel_label('Ctrl+P')),
            ('批量打印…', self.open_batch_print),
            None,
            ('页面信息…', self._show_page_info, accel_label('Ctrl+Shift+I')),
            None,
            ('退出', self._on_close, accel_label('Ctrl+Q')),
        ])

    def _menu_insert(self):
        return build([
            ('在当前页后插入文件…', self.insert_file_dialog,
             accel_label('Ctrl+I')),
            ('插入到文末', lambda: self.insert_file_at(self.doc.page_count)),
            None,
            ('导出当前页为图片…', lambda: self._export_current_page(self.current_page)),
        ])

    def _menu_settings(self):
        return build([
            ('转换后端…', self._open_backend_dialog, accel_label('Ctrl+,')),
        ])

    def _menu_help(self):
        return build([
            ('快捷键', self._show_shortcuts, accel_label('Ctrl+/')),
            ('关于本应用', self._show_about),
        ])

    def _paint_dirty(self):
        self._dirty_dot.delete('all')
        if self.doc.is_modified:
            self._dirty_dot.create_oval(1, 1, 9, 9, fill=MARKER, outline='')

    def _open_backend_dialog(self):
        dialog = BackendDialog(
            self.root,
            self.doc.converter.backend_status(),
            self.doc.converter.requested_name,
            on_select=self._apply_backend,
            on_install=self._prompt_install_backend)
        dialog.wait_window()

    def _show_more_menu(self):
        items = build([
            ('适应页面', lambda: self.preview.set_zoom('fit'), 'Ctrl+0'),
            ('实际大小 100%', lambda: self.preview.set_zoom(1.0), 'Ctrl+1'),
            ('放大 200%', lambda: self.preview.set_zoom(2.0), 'Ctrl+2'),
            None,
            ('页面信息…', self._show_page_info, 'Ctrl+Shift+I'),
            ('重新载入文件', self._reload_document),
            None,
            ('转换后端…', self._open_backend_dialog, 'Ctrl+,'),
            None,
            ('快捷键', self._show_shortcuts, 'Ctrl+/'),
            ('关于本应用', self._show_about),
        ])
        self._more_menu = MenuPopover(self.root, items)
        self._more_menu.show(
            self.root.winfo_pointerx(),
            self.root.winfo_pointery() + 18)

    def _open_recent(self):
        items = self._recent_files()
        if not items:
            return
        self._more_menu = MenuPopover(
            self.root, build([(os.path.basename(p),
                               lambda path=p: self.open_file(path))
                              for p in items]))
        self._more_menu.show(self.root.winfo_pointerx(),
                              self.root.winfo_pointery() + 18)

    def _recent_files(self):
        """最近打开过的文件（还在的、还是 PDF 的）。"""
        return [path for path in load_recent()
                if os.path.isfile(path) and path.lower().endswith('.pdf')]

    def _show_shortcuts(self):
        InfoPanel.show(
            self.root, '快捷键',
            [('打开 PDF', 'Ctrl+O'),
             ('保存 / 另存为', 'Ctrl+S / Ctrl+Shift+S'),
             ('插入文件', 'Ctrl+I'),
             ('撤销 / 重做', 'Ctrl+Z / Ctrl+Shift+Z'),
             ('顺时针 / 逆时针旋转', 'Ctrl+R / Ctrl+Shift+R'),
             ('删除当前页', 'Delete'),
             ('移到开头 / 结尾', 'Ctrl+Shift+↑ / Ctrl+Shift+↓'),
             ('适应 / 100% / 200%', 'Ctrl+0 / Ctrl+1 / Ctrl+2'),
             ('页面信息', 'Ctrl+Shift+I'),
             ('转换后端', 'Ctrl+,'),
             ('退出', 'Ctrl+Q')])

    def _move_current_page(self, target):
        if not self.doc.doc:
            toast(self.root, '还没有打开文档', 'warn')
            return
        count = self.doc.page_count
        index = 0 if target == 0 else count - 1
        if self.current_page == index:
            return
        self._on_reorder(self.current_page, index)

    def _build_main_area(self):
        paned = ttk.PanedWindow(self.root, orient='horizontal')
        paned.pack(fill='both', expand=True)
        self._paned_pack = dict(fill='both', expand=True)

        # 请求宽度 = 目标宽度：分栏第一次分配时左栏就能拿到该有的宽度
        left_frame = ttk.Frame(paned, width=self._rail_width)
        # 宽度固定下来：ttk 的分栏会按"子控件的请求宽度"重新分配，
        # 轨道内容一窄，整栏就被压回去（打开文件时界面横向跳一下的元凶）。
        left_frame.pack_propagate(False)
        self._left_frame = left_frame
        self.thumb_panel = ThumbnailPanel(
            left_frame,
            on_select=self._on_page_select,
            on_reorder=self._on_reorder,
            on_delete=self._on_delete_page,
            on_rotate=self._on_rotate_page,
            on_insert_after=self._on_insert_after,
        )
        self.thumb_panel.pack(fill='both', expand=True)
        self.thumb_panel.load_document(None)
        paned.add(left_frame, weight=0)
        self._paned = paned
        # 左栏宽度变化时守着下限（分栏重排不会把侧栏挤没）
        left_frame.bind('<Configure>', self._watch_rail)
        paned.bind('<Configure>', self._watch_rail)
        # 宽度只在启动时定一次，之后用户自己拖
        self.root.after(60, lambda: self._apply_rail_width())
        self.root.after(800, lambda: self._settle_rail())

        right_frame = ttk.Frame(paned)
        # 空状态住在预览这一格里：这样「打开文件」只是把内容换掉，
        # 不会像整屏浮层那样让预览区宽度突然翻一倍。
        self.empty_state = EmptyState(
            right_frame, on_open=self.open_pdf,
            on_insert=self.insert_file_dialog)
        self.preview = PreviewPanel(
            right_frame,
            on_rotate=lambda angle: self.rotate_page(angle),
            on_delete=self.delete_current_page,
            on_insert=self.insert_file_dialog,
            on_export=lambda: self._export_current_page(self.current_page),
            on_undo=self.undo,
            on_redo=self.redo,
            on_print=self.print_current_page)
        self.preview.pack(fill='both', expand=True)
        paned.add(right_frame, weight=1)
        self._show_empty(True)

    def _show_empty(self, empty):
        """没有文档时预览区显示空状态，有文档时显示页面。

        页面轨和预览区始终在同一个位置：切换只换内容，不动分栏宽度，
        否则打开文件的一瞬整块界面会横向跳一下。
        """
        if empty:
            self.preview.pack_forget()
            self.empty_state.pack(fill='both', expand=True)
            self._save_button.configure_state(False)
            self._refresh_undo_buttons()
        else:
            self.empty_state.pack_forget()
            self.preview.pack(fill='both', expand=True)
            self._save_button.configure_state(True)

    def _set_rail_width(self, paned, width=None):
        """设定页面轨宽度。"""
        width = self._rail_width if width is None else width
        try:
            if abs(paned.sashpos(0) - width) > 1:
                paned.sashpos(0, width)
        except tk.TclError:
            pass

    def _watch_rail(self, event=None):
        """守住页面轨：它不能被分栏挤没。

        ttk 的分栏按子控件的请求宽度重新分配，右边内容一宽、或者分栏位置
        和实际宽度对不上，左栏就可能被压到 0 —— 表现是"侧边的预览框不见了"。

        注意：**不能**用"分栏位置变了 = 用户拖过"来判断要不要接管：
        分栏自己重排也会变，一误判就再也不管宽度了（这正是出问题的原因）。
        现在只有启动时定一次宽度，之后用户拖成什么样都随他。
        """
        try:
            actual = self._left_frame.winfo_width()
            current = self._paned.sashpos(0)
        except tk.TclError:
            return
        if actual >= self.RAIL_MIN_WIDTH:
            return                      # 侧栏好好的，不管它
        if current < self.RAIL_MIN_WIDTH:
            try:
                self._paned.sashpos(0, self.RAIL_MIN_WIDTH)
                # 光改分栏位置不会立刻重排，得让分栏再算一次
                self._paned.update_idletasks()
            except tk.TclError:
                pass

    def _apply_rail_width(self, attempts=0):
        """把页面轨宽度定到 280。

        必须等分栏真的有宽度再定：窗口还没被窗口管理器摆好的时候，
        sashpos 会被夹到 0，页面轨就再也拉不回来了（侧栏不见了）。
        定不上就稍后再试。
        """
        paned = self._paned
        try:
            width = paned.winfo_width()
        except tk.TclError:
            return
        if width <= 1:
            if attempts < 12:
                self.root.after(150,
                                lambda: self._apply_rail_width(attempts + 1))
            return
        self._set_rail_width(paned)

    def _settle_rail(self):
        """初始布局稳定之后，把页面轨宽度定下来（之后不再动它）。"""
        self._apply_rail_width()

    def _build_statusbar(self):
        bar = ttk.Frame(self.root, style='Surface.TFrame')
        bar.pack(fill='x', side='bottom')
        ttk.Separator(self.root, orient='horizontal').pack(
            fill='x', side='bottom')

        self.statusbar = ttk.Label(
            bar, text='就绪', style='Surface.TLabel', anchor='w',
            padding=(12, 4))
        self.statusbar.pack(side='left', fill='x', expand=True)

        self._facts_backend = ttk.Label(
            bar, text='', style='Surface.TLabel', font=font('meta'),
            anchor='e', padding=(4, 4))
        self._facts_backend.pack(side='right')
        self._facts_backend.bind('<Button-1>',
                                 lambda e: self._open_backend_dialog())
        self._facts_backend.bind(
            '<Enter>', lambda e: self._facts_backend.configure(
                foreground=ACCENT))
        self._facts_backend.bind(
            '<Leave>', lambda e: self._facts_backend.configure(
                foreground=INK_2))

        self._facts_pages = ttk.Label(
            bar, text='', style='Surface.TLabel', font=font('meta'),
            anchor='e', padding=(12, 4))
        self._facts_pages.pack(side='right')
        self._refresh_facts()

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
            toast(self.root, '这个转换后端现在用不了：{}'.format(
                str(exc).split('\n')[0]), 'warn')
            self._revert_backend()
            return
        self._last_backend = name
        try:
            save_backend(name)
        except OSError:
            pass
        self._refresh_facts()
        self._update_status('转换后端已切换：{}'.format(label))

    def _revert_backend(self):
        name = self._last_backend
        self._backend_var.set(name)
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
        if not ConfirmPanel.ask(
                self.root, '安装 {}'.format(info['label']),
                '{}\n\n要现在下载并安装吗？装好后需要重启一次应用。'.format(
                    reason),
                confirm_text='安装', danger=False):
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
            ErrorPanel.show(
                self.root, '安装失败',
                '后端没能装上。可以在「设置 → 转换后端」里重试，'
                '或者改用另一个后端。',
                detail='{}\n\n{}'.format(error, detail))
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
            InfoPanel.show(
                self.root, '需要手动安装',
                [('说明', message)], footnote='装好之后重启应用即可生效。')
            if ConfirmPanel.ask(
                    self.root, '重启应用',
                    '已经装好了吗？现在重启就能用上这个后端。',
                    confirm_text='重启', danger=False):
                self._restart_app(name)
            else:
                self._update_status('安装完成后重启应用生效')
            return

        if ConfirmPanel.ask(
                self.root, '安装完成',
                '{}\n\n现在重启应用就能用上这个后端。'.format(message),
                confirm_text='重启', danger=False):
            self._restart_app(name)
        else:
            self._update_status('安装完成，重启应用后生效')

    def _set_backend_controls_enabled(self, enabled):
        if hasattr(self, '_backend_button'):
            self._backend_button.configure(
                state='normal' if enabled else 'disabled')

    def _restart_app(self, backend=None):
        if self.doc.is_modified:
            if not ConfirmPanel.ask(
                    self.root, '还有没保存的修改',
                    '重启会丢掉这些修改。',
                    confirm_text='仍然重启', danger=True):
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
            ErrorPanel.show(self.root, '重启失败',
                            '应用没能自动重启，手动关掉再打开就行。',
                            detail=str(exc))

    def _on_close(self):
        if self._installing:
            toast(self.root, '后端安装还没完成，稍等一下', 'warn')
            return
        if self._converting:
            toast(self.root, '文件还在转换中，稍等一下', 'warn')
            return
        try:
            self.doc.dispose()      # 清掉历史快照、转换出来的临时 PDF
        except Exception:
            pass
        self.root.destroy()

    def _bind_shortcuts(self):
        bind = self.root.bind
        bind('<Control-o>', lambda e: self.open_pdf())
        bind('<Control-O>', lambda e: self.open_pdf())
        bind('<Control-s>', lambda e: self.save_pdf())
        bind('<Control-S>', lambda e: self.save_pdf())
        bind('<Control-Shift-S>', lambda e: self.save_as())
        bind('<Control-i>', lambda e: self.insert_file_dialog())
        bind('<Control-I>', lambda e: self.insert_file_dialog())
        bind('<Control-r>', lambda e: self.rotate_page(90))
        bind('<Control-R>', lambda e: self.rotate_page(90))
        bind('<Control-Shift-R>', lambda e: self.rotate_page(-90))
        bind('<Control-Shift-Up>', lambda e: self._move_current_page(0))
        bind('<Control-Shift-Down>', lambda e: self._move_current_page(-1))
        bind('<Control-0>', lambda e: self.preview.set_zoom('fit'))
        bind('<Control-1>', lambda e: self.preview.set_zoom(1.0))
        bind('<Control-2>', lambda e: self.preview.set_zoom(2.0))
        bind('<Control-Shift-I>', lambda e: self._show_page_info())
        bind('<Control-comma>', lambda e: self._open_backend_dialog())
        bind('<Control-p>', lambda e: self.print_document())
        bind('<Control-P>', lambda e: self.print_document())
        bind('<Control-question>', lambda e: self._show_shortcuts())
        bind('<Control-z>', lambda e: self.undo())
        bind('<Control-Z>', lambda e: self.undo())
        bind('<Control-Shift-Z>', lambda e: self.redo())
        bind('<Control-y>', lambda e: self.redo())
        bind('<Control-Y>', lambda e: self.redo())
        bind('<Control-q>', lambda e: self._on_close())
        bind('<Control-Q>', lambda e: self._on_close())
        bind('<Delete>', self._on_delete_key)

    def _poll_tasks(self):
        """工作线程只投递结果，由主线程统一消费（避免跨线程操作 Tk）。"""
        try:
            while True:
                kind, payload = self._tasks.get_nowait()
                if kind == 'insert':
                    self._insert_done_many(*payload)
        except queue.Empty:
            pass
        self.root.after(120, self._poll_tasks)

    def _on_delete_key(self, event=None):
        widget = self.root.focus_get()
        if isinstance(widget, (tk.Entry, tk.Text, ttk.Entry)):
            return
        self.delete_current_page()

    def undo(self):
        if not self.doc.undo():
            toast(self.root, '没有可撤销的修改', 'warn')
            return
        self._after_history_change('已撤销')

    def redo(self):
        if not self.doc.redo():
            toast(self.root, '没有可重做的修改', 'warn')
            return
        self._after_history_change('已重做')

    def _after_history_change(self, label):
        self.thumb_panel.refresh()
        if self.doc.page_count:
            self.current_page = min(self.current_page,
                                    self.doc.page_count - 1)
        self._show_page(self.current_page)
        self._update_title()
        self._refresh_facts()
        self._refresh_undo_buttons()
        self._update_status('{}（还能撤销 {} 步）'.format(
            label, self.doc.history.undo_steps))

    def _refresh_undo_buttons(self):
        can_undo = self.doc.history.can_undo
        can_redo = self.doc.history.can_redo
        self.preview.set_history(can_undo, can_redo)

    def _update_status(self, text):
        self.statusbar.configure(text=text)

    def _refresh_facts(self):
        pages = self.doc.page_count
        self._facts_pages.configure(
            text='共 {} 页'.format(pages) if pages else '')
        label = self._backend_label().split(' (')[0]
        available = False
        try:
            active = self.doc.converter.name
        except RuntimeError:
            active = None
        for item in self.doc.converter.backend_status():
            if item['name'] == active:
                available = item['available']
                break
        self._facts_backend.configure(
            text='{} {}'.format(label, '●' if available else '○'),
            foreground=OK if available else INK_3)

    def _export_current_page(self, page_num):
        if not self.doc.doc:
            toast(self.root, '还没有打开文档', 'warn')
            return
        path = filedialog.asksaveasfilename(
            title='导出第 {} 页'.format(page_num + 1),
            initialdir=HOME_DIR,
            defaultextension='.png',
            filetypes=[('PNG 图片', '*.png')])
        if not path:
            return
        try:
            self.doc.export_page_image(page_num, path)
        except Exception as e:
            ErrorPanel.show(self.root, '导出失败',
                            '这一页没能存成图片。', detail=str(e))
            return
        toast(self.root, '已导出第 {} 页'.format(page_num + 1), 'ok')

    def print_document(self, page_range=''):
        """打印当前文档（单双面、颜色、纸张等在打印面板里选）。"""
        if not self.doc.doc:
            toast(self.root, '还没有打开文档', 'warn')
            return
        from gui.print_sheet import PrintSheet
        PrintSheet.show(self.root, self.doc, page_range=page_range,
                        title='打印 {}'.format(
                            os.path.basename(self.doc.filepath or '文档')),
                        on_printed=self._on_printed)

    def open_batch_print(self):
        """批量打印窗口（和独立工具是同一套界面）。"""
        from gui.batch_print_window import BatchPrintWindow
        window = BatchPrintWindow(self.root)
        self._batch_windows.append(window)
        return window

    def print_current_page(self):
        """只打印当前这一页。"""
        self.print_document(page_range=str(self.current_page + 1))

    def _on_printed(self, job_id):
        toast(self.root, '已提交打印作业 #{}'.format(job_id), 'ok')
        self._update_status('已提交打印作业 #{}'.format(job_id))

    def _show_page_info(self):
        if not self.doc.doc:
            toast(self.root, '还没有打开文档', 'warn')
            return
        try:
            width, height = self.doc.get_page_size(0)
        except Exception:
            width = height = 0
        size = 0
        if self.doc.filepath and os.path.isfile(self.doc.filepath):
            size = os.path.getsize(self.doc.filepath)
        InfoPanel.show(
            self.root, '页面信息',
            [('文件', os.path.basename(self.doc.filepath or '未命名')),
             ('页数', '共 {} 页'.format(self.doc.page_count)),
             ('页面尺寸', '{:.0f} × {:.0f} pt'.format(width, height)),
             ('文件大小', formats.human_size(size)),
             ('转换后端', self._backend_label())])

    def _reload_document(self):
        if not self.doc.filepath:
            return
        if self.doc.is_modified and not ConfirmPanel.ask(
                self.root, '重新载入文件',
                '当前修改还没保存，重新载入会丢掉这些修改。',
                confirm_text='重新载入'):
            return
        path = self.doc.filepath
        self.open_file(path)

    def _update_title(self):
        name = (os.path.basename(self.doc.filepath)
                if self.doc.filepath else '未命名')
        self.root.title('{} — PDF 内嵌编辑助手'.format(name))
        self._paint_dirty()

    # ---------- 文件操作 ----------

    def open_file(self, path):
        if not path or not os.path.isfile(path):
            return
        try:
            self.doc.close()
            self.doc.open(path)
            push_recent(path)
            self.current_page = 0
            self._show_empty(False)
            self._refresh_undo_buttons()
            self.thumb_panel.load_document(self.doc)
            self._show_page(0)
            self._update_status('已打开 {}'.format(
                os.path.basename(path)))
            self._refresh_facts()
            self._update_title()
        except Exception as e:
            ErrorPanel.show(
                self.root, '打不开这个文件',
                '文件可能已被移动，或者不是有效的 PDF。',
                detail=str(e))

    def open_pdf(self):
        sheet = FileSheet(self.root, mode='open', confirm_text='打开',
                          on_browse=self._browse_open)
        paths = sheet.wait(self.root)
        if paths:
            self.open_file(paths[0])

    def _browse_open(self, directory):
        return filedialog.askopenfilename(
            parent=self.root,
            title='打开 PDF 文件',
            initialdir=directory or HOME_DIR,
            filetypes=[('PDF 文件', '*.pdf'), ('所有文件', '*.*')])

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
            ErrorPanel.show(
                self.root, '保存失败',
                '文件可能是只读的，或者所在目录没有写入权限。',
                detail=str(e))

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
            self._update_status('已保存 {}'.format(os.path.basename(path)))
            self._update_title()
        except Exception as e:
            ErrorPanel.show(
                self.root, '保存失败',
                '文件可能是只读的，或者所在目录没有写入权限。',
                detail=str(e))

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
            self._refresh_undo_buttons()
            self.thumb_panel.refresh()
            self.current_page = to_pos
            self.thumb_panel.select_page(to_pos)
            self._show_page(to_pos)
            self._update_title()
        except Exception as e:
            ErrorPanel.show(self.root, '移动失败',
                            '这一页没能移动到新的位置。', detail=str(e))

    def _on_delete_page(self, page_num):
        if self.doc.page_count <= 1:
            toast(self.root, '至少要保留一页', 'warn')
            return
        total = self.doc.page_count
        if not ConfirmPanel.ask(
                self.root,
                '删除第 {} 页'.format(page_num + 1),
                '这一页会从文档里移除，{} 页会变成 {} 页。'.format(
                    total, total - 1),
                confirm_text='删除'):
            return
        try:
            self.doc.delete_page(page_num)
            self._refresh_undo_buttons()
            self.thumb_panel.refresh()
            new_pos = min(page_num, self.doc.page_count - 1)
            self._show_page(new_pos)
            self._update_title()
        except Exception as e:
            ErrorPanel.show(self.root, '删除失败',
                            '这一页没能从文档里移除。', detail=str(e))

    def _on_rotate_page(self, page_num, angle=90):
        try:
            self.doc.rotate_page(page_num, angle)
            self._refresh_undo_buttons()
            self.thumb_panel.refresh_page(page_num)
            self._show_page(page_num)
            self._update_title()
        except Exception as e:
            ErrorPanel.show(self.root, '旋转失败',
                            '这一页没能旋转。', detail=str(e))

    def rotate_page(self, angle):
        self._on_rotate_page(self.current_page, angle)

    def delete_current_page(self):
        self._on_delete_page(self.current_page)

    # ---------- 插入文件 ----------

    def _on_insert_after(self, page_num):
        paths = self._pick_insert_files()
        if not paths:
            return
        self._do_insert_many(paths, page_num + 1)

    def insert_file_dialog(self):
        paths = self._pick_insert_files()
        if not paths:
            return
        self._pending_paths = paths
        pos = self._ask_insert_position()
        if pos is not None:
            self._do_insert_many(paths, pos)

    def _ask_insert_position(self):
        """插入位置：当前页之后 / 文末 / 指定页。"""
        sheet = InsertSheet(self.root, paths=self._pending_paths,
                            current_page=self.current_page,
                            page_count=self.doc.page_count)
        sheet._place(self.root)
        self.root.wait_window(sheet)
        return sheet.result

    def insert_file_at(self, position):
        paths = self._pick_insert_files()
        if not paths:
            return
        self._do_insert_many(paths, position)

    def _pick_insert_files(self):
        """快速入口面板选文件；插入模式默认停在当前 PDF 所在文件夹。"""
        sheet = FileSheet(self.root, mode='insert',
                          current_path=self.doc.filepath,
                          confirm_text='插入',
                          on_browse=self._browse_insert)
        paths = sheet.wait(self.root)
        return list(paths or [])

    def _browse_insert(self, directory):
        return filedialog.askopenfilename(
            parent=self.root,
            title='选择要插入的文件',
            initialdir=directory or HOME_DIR,
            filetypes=formats.filetypes())

    def _do_insert_many(self, paths, position):
        if self._converting or not paths:
            return
        self._converting = True
        names = '、'.join(os.path.basename(p) for p in paths[:2])
        if len(paths) > 2:
            names += ' 等 {} 个文件'.format(len(paths))
        self._update_status('正在转换 {}…'.format(names))
        self.root.config(cursor='watch')

        def task():
            try:
                results = self.doc.insert_files(paths, position)
            except Exception as e:
                results = []
                error = e
            else:
                error = None
            self._tasks.put(('insert', (position, results, error)))

        threading.Thread(target=task, daemon=True).start()

    def _insert_done_many(self, position, results, error):
        self._converting = False
        self.root.config(cursor='')
        if error is not None:
            ErrorPanel.show(
                self.root, '插入失败',
                '这个文件没能转成页面。如果它正被 WPS 或 Word 打开着，'
                '关掉之后重试一次。',
                detail=str(error))
            self._update_status('插入失败')
            return

        failed = [r for r in results if not r['ok']]
        added = sum(r['pages'] for r in results)
        self.thumb_panel.refresh()
        new_page = min(position, max(self.doc.page_count - 1, 0))
        self._show_page(new_page)
        self._update_title()
        self._refresh_facts()

        if failed:
            names = '、'.join(os.path.basename(r['path']) for r in failed)
            ErrorPanel.show(
                self.root, '有 {} 个文件没插进去'.format(len(failed)),
                '其余文件已经插好了。{} 没能转成页面 —— 如果它正被 WPS 或 '
                'Word 打开着，关掉之后重试一次。'.format(names),
                detail='\n'.join(r['error'] for r in failed))
            self._update_status('已插入 {} 页，{} 个文件失败'.format(
                added, len(failed)))
            self._refresh_undo_buttons()
            return

        self._update_status('已插入 {} 页，共 {} 页'.format(
            added, self.doc.page_count))
        toast(self.root, '已插入 {} 页，共 {} 页'.format(
            added, self.doc.page_count), 'ok')
        self._refresh_undo_buttons()

    def _do_insert(self, filepath, position):
        self._do_insert_many([filepath], position)

    def _show_about(self):
        InfoPanel.show(
            self.root, 'PDF 内嵌编辑助手',
            [('版本', VERSION),
             ('作用', '把 Word、Excel、图片转成页面，插进 PDF 的任意位置'),
             ('转换后端', '{}（按需安装，不随应用打包）'.format(
                 self._backend_label())),
             ('技术', 'Python + PyMuPDF + WPS / LibreOffice')],
            footnote='页面可以拖拽排序、旋转、删除；改动随时可以撤销保存。')

    def run(self):
        self.root.mainloop()
