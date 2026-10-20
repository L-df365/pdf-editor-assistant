import tkinter as tk
from tkinter import ttk

from gui.feedback import attach_tooltip
from gui.widgets import FlatButton
from gui.menu import MenuPopover, build
from gui.theme import (LINE, PAPER, SHADOW_TONES, STAGE, SURFACE, font)

#: 缩放档位：(显示名, 取值)
ZOOM_MODES = (
    ('适应', 'fit'),
    ('50%', 0.5),
    ('100%', 1.0),
    ('200%', 2.0),
)


class PreviewPanel:
    """右侧预览面板：页面预览 + 缩放分段 + 页码计数。"""

    def __init__(self, parent, on_rotate=None, on_delete=None,
                 on_insert=None, on_export=None, on_undo=None, on_redo=None):
        self.frame = ttk.Frame(parent, style='Surface.TFrame')
        self.current_photo = None
        self._last_doc = None
        self._last_page = 0
        self._mode = 'fit'
        self.on_rotate = on_rotate
        self.on_delete = on_delete
        self.on_insert = on_insert
        self.on_export = on_export
        self.on_undo = on_undo
        self.on_redo = on_redo

        self._build_action_row()
        self._build_canvas()
        self._build_counter_bar()
        self.action_card.place(relx=0, rely=0, x=12, y=12)
        self.action_card.lift()

    # ------------------------------------------------------------------

    def _build_action_row(self):
        """页面级动作：浮在台面上的工具条（不是第二条窗口栏）。

        工具条是方的：底衬做成圆角卡片会和里面一排方角按钮错位，
        看着像两层东西叠歪了。底衬改成一像素描边的方条，按钮贴着边排。
        """
        self.action_card = tk.Frame(self.frame, bg=PAPER,
                                    highlightbackground=LINE,
                                    highlightthickness=1)
        bar = tk.Frame(self.action_card, bg=PAPER)
        bar.pack(padx=3, pady=3)

        def action(text, command, variant='segment', width=None):
            button = FlatButton(bar, text, command=command, variant=variant,
                                bg=PAPER, width=width)
            button.pack(side='left', padx=1, pady=1)
            return button

        if self.on_undo:
            self.undo_button = action('←', self.on_undo, width=30)
            self.undo_button.configure_state(False)
            attach_tooltip(self.undo_button, '撤销（Ctrl+Z）')
        if self.on_redo:
            self.redo_button = action('→', self.on_redo, width=30)
            self.redo_button.configure_state(False)
            attach_tooltip(self.redo_button, '重做（Ctrl+Shift+Z）')
        if self.on_undo or self.on_redo:
            tk.Frame(bar, bg=PAPER, width=1, height=18,
                     highlightbackground=LINE,
                     highlightthickness=0).pack(side='left', padx=4)
        if self.on_rotate:
            action('↺ 逆时针', lambda: self.on_rotate(-90))
            action('↻ 顺时针', lambda: self.on_rotate(90))
        if self.on_insert:
            action('＋ 在此后插入', self.on_insert)
        if self.on_delete:
            action('⌫ 删除此页', self.on_delete, variant='danger')


    def _build_canvas(self):
        canvas_frame = ttk.Frame(self.frame, style='Stage.TFrame')
        canvas_frame.pack(fill='both', expand=True)

        # width/height 给小值：Tk 画布默认申请 396x278，会撑破布局
        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0,
                                bg=STAGE, highlightbackground=STAGE,
                                width=120, height=120)
        self.h_scroll = ttk.Scrollbar(
            canvas_frame, orient='horizontal', command=self.canvas.xview,
            )
        self.v_scroll = ttk.Scrollbar(
            canvas_frame, orient='vertical', command=self.canvas.yview,
            )
        self.canvas.configure(xscrollcommand=self.h_scroll.set,
                              yscrollcommand=self.v_scroll.set)

        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.v_scroll.grid(row=0, column=1, sticky='ns')
        self.h_scroll.grid(row=1, column=0, sticky='ew')
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self.canvas.bind('<Button-4>',
                         lambda e: self.canvas.yview_scroll(-1, 'units'))
        self.canvas.bind('<Button-5>',
                         lambda e: self.canvas.yview_scroll(1, 'units'))
        self._context_menu = MenuPopover(self.frame, [])
        self.canvas.bind('<Button-3>',
                         lambda e: self._popup_menu(e))
        self.canvas.bind('<Configure>', self._on_canvas_resize)
        self._canvas_width = 800
        self._canvas_height = 600

    def _build_counter_bar(self):
        # 分隔线要排在底栏上面：先 pack 分隔线再 pack 底栏，
        # 否则分隔线会被挤到最底下（在底栏下面，看不见）。
        ttk.Separator(self.frame, orient='horizontal').pack(fill='x',
                                                            side='top')
        bar = ttk.Frame(self.frame, style='Surface.TFrame')
        bar.pack(fill='x')
        self.counter = ttk.Label(bar, text='', style='Surface.TLabel',
                                 font=font('num'), padding=(8, 3))
        self.counter.pack(side='right')

        self.zoom_frame = ttk.Frame(bar, style='Surface.TFrame')
        self.zoom_frame.pack(side='left', padx=2, pady=2)
        self._zoom_buttons = {}
        for label, value in ZOOM_MODES:
            btn = FlatButton(self.zoom_frame, label, variant='segment',
                             bg=SURFACE,
                             command=lambda v=value: self.set_zoom(v))
            btn.pack(side='left', padx=1, pady=1)
            self._zoom_buttons[value] = btn
        self._paint_zoom()

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def pack_forget(self):
        self.frame.pack_forget()

    def _popup_menu(self, event):
        page = self._last_page
        self._context_menu.set_items(build([
            ('适应页面', lambda: self.set_zoom('fit'), 'Ctrl+0'),
            ('实际大小 100%', lambda: self.set_zoom(1.0), 'Ctrl+1'),
            ('放大 200%', lambda: self.set_zoom(2.0), 'Ctrl+2'),
            None,
            # on_export / on_insert 传进来的是"无参数"回调，
            # 这里只能调用它们、不能塞页码进去
            ('导出当前页为图片…',
             lambda: self.on_export() if self.on_export else None),
            ('在第 {} 页后插入文件…'.format(page + 1),
             lambda: self.on_insert() if self.on_insert else None),
        ]))
        self._context_menu.show(event.x_root, event.y_root)

    # ------------------------------------------------------------------

    def _on_canvas_resize(self, event):
        self._canvas_width = event.width
        self._canvas_height = event.height
        if self._last_doc is not None:
            self._render_preview(event.width, event.height)

    def set_history(self, can_undo, can_redo):
        if getattr(self, 'undo_button', None) is not None:
            self.undo_button.configure_state(can_undo)
        if getattr(self, 'redo_button', None) is not None:
            self.redo_button.configure_state(can_redo)

    def set_zoom(self, mode):
        self._mode = mode
        self._paint_zoom()
        self._render_preview()

    def _paint_zoom(self):
        for value, btn in self._zoom_buttons.items():
            btn.set_variant('segment-on' if value == self._mode else 'segment')

    def show_page(self, pdf_doc, page_num):
        if not pdf_doc or not pdf_doc.doc:
            return
        self._last_doc = pdf_doc
        self._last_page = page_num
        if self.canvas.winfo_width() <= 1:
            # 窗口尚未布局完成，等空闲时再渲染，保证用真实画布尺寸
            self.canvas.after_idle(self._render_preview)
        else:
            self._render_preview()

    def _render_preview(self, width=None, height=None):
        doc = self._last_doc
        page_num = self._last_page
        if not doc or not doc.doc:
            return
        from PIL import Image, ImageTk

        if width:
            self._canvas_width = width
        if height:
            self._canvas_height = height
        else:
            live_w = self.canvas.winfo_width()
            live_h = self.canvas.winfo_height()
            if live_w > 1:
                self._canvas_width = live_w
            if live_h > 1:
                self._canvas_height = live_h

        if self._mode == 'fit':
            max_w = max(self._canvas_width - 48, 200)
            max_h = max(self._canvas_height - 48, 200)
            pix, zoom = doc.get_page_image(page_num, max_width=max_w,
                                           max_height=max_h, fit_width=False)
        else:
            zoom = float(self._mode)
            pix = doc.get_page_at_zoom(page_num, zoom)
        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        self.current_photo = ImageTk.PhotoImage(img)

        self.canvas.delete('all')
        x = max((self._canvas_width - pix.width) // 2, 12)
        # 顶部留出浮动工具条的位置，页面不会被压住
        y = max((self._canvas_height - pix.height) // 2, 58)

        for offset, tone in enumerate(reversed(SHADOW_TONES), start=1):
            self.canvas.create_rectangle(
                x + offset, y + offset,
                x + pix.width + offset, y + pix.height + offset,
                fill=tone, outline='')
        self.canvas.create_image(x, y, anchor='nw',
                                 image=self.current_photo, tags='preview')
        # 滚动区域覆盖整个画布并归零视图，避免内容被挤到一侧
        self.canvas.configure(scrollregion=(
            0, 0,
            max(self._canvas_width, x + pix.width + 24),
            max(self._canvas_height, y + pix.height + 24)))
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        # 适应模式下页面永远放得下，横向滚动条只会变成一条碍眼的灰带
        if self._mode == 'fit':
            self.h_scroll.grid_remove()
        else:
            self.h_scroll.grid()

        total = doc.page_count
        self.counter.configure(text='{:02d} / {:02d}'.format(page_num + 1,
                                                             total))

    def set_last(self, doc, page_num):
        self._last_doc = doc
        self._last_page = page_num
