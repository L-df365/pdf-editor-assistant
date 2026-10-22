"""右侧预览区。

两种看法：
- **瀑布流**（默认）：所有页面竖着排下去，宽度自适应，像读一份连续的文档
- **单页**：一次看一页，可以放大看细节

缩放：适应宽度 / 适应页面 / 手动（滑块）。
页码区可以直接输入跳转，也有上一页/下一页。
"""

import tkinter as tk
from tkinter import ttk

from gui.feedback import attach_tooltip
from gui.widgets import FlatButton, Segmented, ZoomSlider
from gui.menu import MenuPopover, build
from gui.theme import (LINE, PAPER, SHADOW_TONES, STAGE, SURFACE, font)

#: 缩放档位
ZOOM_MODES = (
    ('fit-width', '适应宽度'),
    ('fit-page', '适应页面'),
)

#: 手动缩放的范围（百分比）
ZOOM_MIN = 10
ZOOM_MAX = 600
ZOOM_STEP = 5

#: 瀑布流里页面之间的间距
FLOW_GAP = 14
#: 瀑布流里页面左右留白
FLOW_MARGIN = 16


class PreviewPanel:
    """右侧预览面板：瀑布流 / 单页、缩放、页码跳转。"""

    VIEW_FLOW = 'flow'        # 瀑布流（默认）
    VIEW_SINGLE = 'single'    # 单页

    def __init__(self, parent, on_rotate=None, on_delete=None,
                 on_insert=None, on_export=None, on_undo=None, on_redo=None,
                 on_print=None, on_page_change=None):
        self.frame = ttk.Frame(parent, style='Surface.TFrame')
        self.current_photo = None
        self._last_doc = None
        self._last_page = 0
        self._view = self.VIEW_FLOW
        self._mode = 'fit-width'      # fit-width / fit-page / 手动缩放值
        self._zoom = 100              # 手动缩放（以适应状态为 100% 基准）
        self._base_scale = 1.0        # 离开适应状态时的基准比例
        self._ready = False           # 控件还在建，先别响应滑块
        self._flow_layout = []        # [{'page','y','w','h'}]
        self._flow_photos = {}        # page → PhotoImage（只留视口附近的）
        self._flow_items = {}         # page → canvas item id
        self.on_rotate = on_rotate
        self.on_delete = on_delete
        self.on_insert = on_insert
        self.on_export = on_export
        self.on_undo = on_undo
        self.on_redo = on_redo
        self.on_print = on_print
        self.on_page_change = on_page_change

        self._build_action_row()
        self._build_canvas()
        self._build_counter_bar()
        self.action_card.place(relx=0, rely=0, x=12, y=12)
        self.action_card.lift()
        self._ready = True

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
        if self.on_print:
            action('打印此页', self.on_print)
        if self.on_delete:
            action('✂ 删除此页', self.on_delete, variant='danger')

    def _build_canvas(self):
        canvas_frame = ttk.Frame(self.frame, style='Stage.TFrame')
        canvas_frame.pack(fill='both', expand=True)

        # width/height 给小值：Tk 画布默认申请 396x278，会撑破布局
        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0,
                                bg=STAGE, highlightbackground=STAGE,
                                width=120, height=120)

        def scroll(*args):
            """滚动后要把视口附近的页画出来（只渲染可见部分）。"""
            self.canvas.yview(*args)
            self._after_scroll()

        self.h_scroll = ttk.Scrollbar(
            canvas_frame, orient='horizontal', command=self.canvas.xview,
            )
        self.v_scroll = ttk.Scrollbar(
            canvas_frame, orient='vertical', command=scroll,
            )
        self.canvas.configure(xscrollcommand=self.h_scroll.set,
                              yscrollcommand=self.v_scroll.set)

        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.v_scroll.grid(row=0, column=1, sticky='ns')
        self.h_scroll.grid(row=1, column=0, sticky='ew')
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self.canvas.bind('<Button-4>', self._wheel_up)
        self.canvas.bind('<Button-5>', self._wheel_down)
        self.canvas.bind('<MouseWheel>', self._wheel)
        self.canvas.bind('<Configure>', self._on_canvas_resize)
        self.canvas.bind('<Button-1>', self._on_canvas_press)
        self.canvas.bind('<B1-Motion>', self._on_canvas_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_canvas_release)
        self._context_menu = MenuPopover(self.frame, [])
        self.canvas.bind('<Button-3>',
                         lambda e: self._popup_menu(e))
        self._canvas_width = 800
        self._canvas_height = 600
        self._flow_job = None
        self._flow_total_h = 0
        self._drag = None

    def _wheel_up(self, event=None):
        self.canvas.yview_scroll(-3, 'units')
        self._after_scroll()

    def _wheel_down(self, event=None):
        self.canvas.yview_scroll(3, 'units')
        self._after_scroll()

    def _wheel(self, event):
        self.canvas.yview_scroll(-3 if event.delta > 0 else 3, 'units')
        self._after_scroll()

    def _after_scroll(self):
        """滚动之后：画视口附近的页，并把"当前页"跟着挪。"""
        self._schedule_flow()
        self._sync_current_to_view()

    def _sync_current_to_view(self):
        """视口最上面那一页成为当前页（页面轨跟着走）。

        不改视图位置 —— 用户正在滚，动一下就会打架。
        """
        if self._view != self.VIEW_FLOW or not self._flow_layout:
            return
        top = self.canvas.canvasy(0)
        page = None
        for item in self._flow_layout:
            if item['y'] + item['h'] > top:
                page = item['page']
                break
        if page is None or page == self._last_page:
            return
        self._last_page = page
        if self.on_page_change:
            self.on_page_change(page)

    def _build_counter_bar(self):
        # 缩放：适应宽度 / 适应页面 + 滑块
        ttk.Separator(self.frame, orient='horizontal').pack(fill='x',
                                                            side='top')
        bar = ttk.Frame(self.frame, style='Surface.TFrame')
        bar.pack(fill='x')
        self.counter = ttk.Label(bar, text='', style='Surface.TLabel',
                                 font=font('num'), padding=(8, 3))
        self.counter.pack(side='right')

        # 缩放控件在左下
        zoom_box = ttk.Frame(bar, style='Surface.TFrame')
        zoom_box.pack(side='left', padx=6, pady=3)

        self.zoom_choice = Segmented(
            zoom_box, [(value, label) for value, label in ZOOM_MODES],
            value='fit-width', bg=SURFACE, command=self._on_zoom_choice)
        self.zoom_choice.pack(side='left')

        self.zoom_slider = ZoomSlider(
            zoom_box, from_=ZOOM_MIN, to=ZOOM_MAX, value=self._zoom,
            step=ZOOM_STEP, bg=SURFACE, length=120,
            command=self._on_zoom_slider)
        self.zoom_slider.pack(side='left', padx=(10, 0))

        # 视图切换：瀑布流 / 单页
        self.view_choice = Segmented(
            zoom_box, [(self.VIEW_FLOW, '瀑布流'), (self.VIEW_SINGLE, '单页')],
            value=self.VIEW_FLOW, bg=SURFACE, command=self._on_view_choice)
        self.view_choice.pack(side='left', padx=(12, 0))

        # 页码跳转：上一页 / 输入框 / 下一页
        nav = ttk.Frame(bar, style='Surface.TFrame')
        nav.pack(side='right', padx=(0, 4))
        self.prev_button = FlatButton(nav, '‹', command=self._prev_page,
                                      variant='segment', bg=SURFACE,
                                      width=22)
        self.prev_button.pack(side='left')
        self.page_entry = ttk.Entry(nav, font=font('num'), width=4,
                                    justify='center')
        self.page_entry.pack(side='left', padx=2)
        self.page_entry.bind('<Return>', lambda e: self._jump_to_entry())
        self.page_entry.bind('<KP_Enter>', lambda e: self._jump_to_entry())
        self.total_label = ttk.Label(nav, text='', style='Surface.TLabel',
                                     font=font('num'), padding=(2, 0))
        self.total_label.pack(side='left')
        self.next_button = FlatButton(nav, '›', command=self._next_page,
                                      variant='segment', bg=SURFACE,
                                      width=22)
        self.next_button.pack(side='left', padx=(2, 0))

    # ------------------------------------------------------------------
    # 缩放与视图
    # ------------------------------------------------------------------

    def _on_zoom_choice(self, value):
        """点了「适应宽度 / 适应页面」。"""
        if value:
            self._mode = value
            self._render()
        self._update_zoom_label()

    def _on_zoom_slider(self, value):
        """缩放滑块动了 → 手动缩放。

        滑块的值是"相对实际尺寸的百分比"，而适应模式下页面显示的比例
        往往不是 100% —— 所以要先用视图的真实比例起步，
        否则从"适应宽度"点一下 +，页面会突然缩掉一半。
        """
        if not self._ready:
            return          # 控件还在建，先别动
        zoom = max(ZOOM_MIN, min(ZOOM_MAX, int(value)))
        if self._mode not in ('fit-width', 'fit-page') \
                and zoom == self._zoom:
            return
        self._zoom = zoom
        self._mode = zoom
        self.zoom_choice.set_value('', notify=False)
        self._render()

    def _on_view_choice(self, value):
        """切换 瀑布流 / 单页。"""
        if value == self._view:
            return
        self._view = value
        self._render()

    def set_view(self, view):
        """外部切换看法（菜单里也能进）。"""
        if view in (self.VIEW_FLOW, self.VIEW_SINGLE) and view != self._view:
            self._view = view
            self.view_choice.set_value(view, notify=False)
            self._render()

    def _fit_scale(self):
        """适应模式下页面相对实际尺寸的缩放系数（1.95 = 195%）。"""
        doc = self._last_doc
        if not doc or not doc.doc:
            return 1.0
        try:
            page_w, page_h = doc.get_page_size(self._last_page)
        except Exception:
            return 1.0
        if self._mode == 'fit-page':
            box = max(self._canvas_height - 48, 100)
            return box / page_h if page_h else 1.0
        box = max(self._canvas_width - 48, 100)
        return box / page_w if page_w else 1.0

    def _render_scale(self):
        """实际渲染用的缩放系数（相对实际页面尺寸）。

        手动缩放是**相对适应状态**的：适应宽度时是 100%，
        滑到 150% 就是"适应宽度的 1.5 倍"。这样从适应切到手动不会跳。
        """
        if self._mode in ('fit-width', 'fit-page'):
            return self._fit_scale()
        return self._base_scale * (self._zoom / 100.0)

    def _update_zoom_label(self):
        """滑块和百分比：始终以适应状态为 100% 基准。"""
        slider = getattr(self, 'zoom_slider', None)
        if slider is None:
            return
        if self._mode in ('fit-width', 'fit-page'):
            # 适应状态就是 100% 基准；
            # 记住离开适应状态时的比例，手动微调从这儿接着走
            self._base_scale = self._fit_scale()
            self._zoom = 100
        slider.set_value(self._zoom, notify=False)

    def set_zoom(self, mode):
        """兼容旧的接口：'fit' / 1.0 / 2.0。"""
        if mode == 'fit':
            self._mode = 'fit-width'
        elif isinstance(mode, (int, float)):
            self._zoom = int(mode * 100)
            self._mode = self._zoom
        else:
            self._mode = mode
        self.zoom_choice.set_value(self._mode if self._mode in
                                   ('fit-width', 'fit-page') else '',
                                   notify=False)
        self._update_zoom_label()
        self._render()

    def _popup_menu(self, event):
        page = self._last_page
        self._context_menu.set_items(build([
            ('适应宽度', lambda: self.set_zoom('fit-width'), 'Ctrl+0'),
            ('适应页面', lambda: self.set_zoom('fit-page'), 'Ctrl+1'),
            ('放大 200%', lambda: self.set_zoom(2.0), 'Ctrl+2'),
            None,
            ('瀑布流视图', lambda: self.set_view(self.VIEW_FLOW)),
            ('单页视图', lambda: self.set_view(self.VIEW_SINGLE)),
            None,
            ('导出当前页为图片…', lambda: self.on_export()
             if self.on_export else None),
            ('在第 {} 页后插入文件…'.format(page + 1),
             lambda: self.on_insert() if self.on_insert else None),
        ]))
        self._context_menu.show(event.x_root, event.y_root)

    # ------------------------------------------------------------------
    # 页码跳转
    # ------------------------------------------------------------------

    def _jump_to_entry(self):
        """页码框里输入的数字 → 跳过去。"""
        try:
            page = int(self.page_entry.get().strip())
        except (ValueError, tk.TclError):
            self._sync_page_entry()
            return
        total = self._last_doc.page_count if self._last_doc else 0
        if page < 1 or page > total:
            self._sync_page_entry()     # 越界：把框里的数字改回当前页
            return
        self._goto_page(page - 1)

    def _sync_page_entry(self):
        """把当前页写回页码框。

        但用户正在框里打字时**不能改** —— 后台重绘会把他输入的数字
        冲掉（按回车就变成跳到当前页，像"没反应"）。
        """
        total = self._last_doc.page_count if self._last_doc else 0
        if self.page_entry.focus_get() is self.page_entry:
            return
        self.page_entry.delete(0, 'end')
        self.page_entry.insert(0, str(self._last_page + 1))
        self.total_label.configure(text='/ {}'.format(total) if total else '')

    def _prev_page(self):
        if self._last_page > 0:
            self._goto_page(self._last_page - 1)

    def _next_page(self):
        total = self._last_doc.page_count if self._last_doc else 0
        if self._last_page + 1 < total:
            self._goto_page(self._last_page + 1)

    def _goto_page(self, page):
        self.show_page(self._last_doc, page)
        if self.on_page_change:
            self.on_page_change(page)

    def _on_canvas_press(self, event):
        """按下：准备拖动（瀑布流可以拖着翻页，像别的 PDF 软件那样）。"""
        self._drag = {'x': event.x_root, 'y': event.y_root, 'moved': False}

    def _on_canvas_drag(self, event):
        """拖动：把视图跟着手指挪。"""
        if self._drag is None:
            return
        dx = event.x_root - self._drag['x']
        dy = event.y_root - self._drag['y']
        if abs(dx) > 3 or abs(dy) > 3:
            self._drag['moved'] = True
        if not self._drag['moved'] or self._view != self.VIEW_FLOW:
            return
        total = max(self._flow_total_h, 1)
        top = self.canvas.yview()[0] - dy / float(total)
        self.canvas.yview_moveto(max(0.0, min(1.0, top)))
        self._drag['x'] = event.x_root
        self._drag['y'] = event.y_root
        self._after_scroll()

    def _on_canvas_release(self, event):
        """松开：没怎么动就是点选一页。"""
        drag = self._drag
        self._drag = None
        if drag is not None and drag['moved']:
            return
        self._on_canvas_click(event)

    def _on_canvas_click(self, event):
        """点画布：瀑布流里是选那一页。"""
        if self._view != self.VIEW_FLOW:
            return
        y = self.canvas.canvasy(event.y)
        for item in self._flow_layout:
            if item['y'] <= y < item['y'] + item['h']:
                self._goto_page(item['page'])
                return

    # ------------------------------------------------------------------
    # 渲染
    # ------------------------------------------------------------------

    def _on_canvas_resize(self, event):
        self._canvas_width = event.width
        self._canvas_height = event.height
        if self._last_doc is not None:
            if self._view == self.VIEW_FLOW:
                self._schedule_flow()
            else:
                self._render_preview(event.width, event.height)

    def _schedule_flow(self):
        """滚动/缩放后重画瀑布流（合并成一次）。"""
        if self._flow_job is not None:
            try:
                self.canvas.after_cancel(self._flow_job)
            except tk.TclError:
                pass
        self._flow_job = self.canvas.after(60, self._render_flow)

    def set_last(self, doc, page_num):
        self._last_doc = doc
        self._last_page = page_num

    def show_page(self, pdf_doc, page_num):
        if not pdf_doc or not pdf_doc.doc:
            return
        self._last_doc = pdf_doc
        self._last_page = page_num
        if self.canvas.winfo_width() <= 1:
            # 窗口尚未布局完成，等空闲时再渲染，保证用真实画布尺寸
            self.canvas.after_idle(self._render)
        else:
            self._render()
        self._ensure_page_visible(page_num)

    def _ensure_page_visible(self, page_num):
        """跳到某一页时，把视图滚过去。

        不滚的话，页码变了但画面还是原处 —— 用户看着像"没反应"。
        """
        if self._view != self.VIEW_FLOW:
            return
        for item in self._flow_layout:
            if item['page'] != page_num:
                continue
            top = self.canvas.canvasy(0)
            bottom = top + self._canvas_height
            if item['y'] + item['h'] > top and item['y'] < bottom:
                return                      # 已经看得见，不用动
            y = max(item['y'] - 54, 0)   # 留出顶部浮动工具条的位置
            if self._flow_total_h > 0:
                self.canvas.yview_moveto(min(1.0, y / self._flow_total_h))
            self._schedule_flow()
            return

    def _render(self):
        if self._view == self.VIEW_FLOW:
            self._render_flow()
        else:
            self._render_preview()

    def _render_preview(self, width=None, height=None):
        """单页视图。"""
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

        if self._mode == 'fit-page':
            max_w = max(self._canvas_width - 48, 200)
            max_h = max(self._canvas_height - 48, 200)
            pix, zoom = doc.get_page_image(page_num, max_width=max_w,
                                           max_height=max_h, fit_width=False)
        elif self._mode == 'fit-width':
            max_w = max(self._canvas_width - 48, 200)
            max_h = 100000
            pix, zoom = doc.get_page_image(page_num, max_width=max_w,
                                           max_height=max_h, fit_width=False)
        else:
            zoom = self._render_scale()
            pix = doc.get_page_at_zoom(page_num, zoom)
        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        self.current_photo = ImageTk.PhotoImage(img)

        self.canvas.delete('all')
        self._flow_items = {}
        self._flow_photos = {}
        self._flow_key = None
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
        if self._mode in ('fit-width', 'fit-page'):
            self.h_scroll.grid_remove()
        else:
            self.h_scroll.grid()

        self._update_page_info(page_num)
        self._update_zoom_label()

    # ------------------------------------------------------------------

    def _flow_geometry(self):
        """算好瀑布流里每页的位置和尺寸（只算，不渲染）。"""
        doc = self._last_doc
        if not doc or not doc.doc:
            return [], 0
        width = max(self._canvas_width - FLOW_MARGIN * 2, 120)
        height = max(self._canvas_height - 48, 120)
        items = []
        y = 12
        for page in range(doc.page_count):
            try:
                pw, ph = doc.get_page_size(page)
            except Exception:
                pw, ph = 595.0, 842.0
            if not pw or not ph:
                pw, ph = 595.0, 842.0
            if self._mode == 'fit-page':
                page_h = height
                page_w = page_h * (pw / ph)
            elif self._mode == 'fit-width':
                page_w = width
                page_h = page_w * (ph / pw)
            else:
                scale = self._render_scale()
                page_w = pw * scale
                page_h = ph * scale
            items.append({'page': page, 'y': y, 'w': page_w, 'h': page_h})
            y += page_h + FLOW_GAP
        return items, y

    def _render_flow(self):
        """瀑布流：所有页面竖着排，只渲染视口附近的几页。"""
        doc = self._last_doc
        if not doc or not doc.doc:
            return

        live_w = self.canvas.winfo_width()
        live_h = self.canvas.winfo_height()
        if live_w > 1:
            self._canvas_width = live_w
        if live_h > 1:
            self._canvas_height = live_h

        # 缩放或宽度变了，之前渲染的图就作废（否则会留着旧尺寸）
        key = (self._mode, self._zoom, self._canvas_width)
        if key != getattr(self, '_flow_key', None):
            self._flow_key = key
            for ids in self._flow_items.values():
                for item_id in ids:
                    self.canvas.delete(item_id)
            self._flow_items = {}
            self._flow_photos = {}

        items, total_h = self._flow_geometry()
        self._flow_layout = items
        self._flow_total_h = total_h
        content_w = max([item['w'] for item in items] or [0]) + FLOW_MARGIN * 2
        self.canvas.configure(scrollregion=(0, 0, content_w,
                                           max(total_h, self._canvas_height)))
        # 只有内容比画布宽时才需要横向滚动（手动放大到超出宽度才有）
        if content_w > self._canvas_width:
            self.h_scroll.grid()
        else:
            self.h_scroll.grid_remove()

        # 视口附近的页才渲染：视口上下各多留一屏，
        # 滚动时提前画好，就不会露出空白
        top = self.canvas.canvasy(0)
        bottom = self.canvas.canvasy(self._canvas_height)
        margin = max(self._canvas_height, 400)
        visible = set()
        for item in items:
            if item['y'] + item['h'] >= top - margin \
                    and item['y'] <= bottom + margin:
                visible.add(item['page'])

        # 清掉离开视口的图
        for page in list(self._flow_photos):
            if page not in visible:
                for item_id in self._flow_items.pop(page, ()):
                    self.canvas.delete(item_id)
                del self._flow_photos[page]

        for item in items:
            page = item['page']
            if page not in visible:
                continue
            if page in self._flow_items:
                continue
            photo = self._flow_photo(doc, page, item)
            if photo is None:
                continue
            x = max((self._canvas_width - item['w']) // 2, FLOW_MARGIN)
            # 纸白压着灰台面，描一道细边才看得出页与页的分界
            frame = self.canvas.create_rectangle(
                x - 1, item['y'] - 1, x + item['w'] + 1,
                item['y'] + item['h'] + 1, outline=LINE, fill='')
            image = self.canvas.create_image(x, item['y'], anchor='nw',
                                            image=photo, tags='flow')
            self._flow_items[page] = (frame, image)
            self._flow_photos[page] = photo

        self._update_page_info(self._last_page)
        self._update_zoom_label()

    def _flow_photo(self, doc, page, item):
        """渲染一页。"""
        from PIL import Image, ImageTk
        try:
            page_w = doc.get_page_size(page)[0] or 595.0
            pix = doc.get_page_at_zoom(page, item['w'] / page_w)
            img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        except Exception:
            return None
        return ImageTk.PhotoImage(img)

    def _update_page_info(self, page_num):
        total = self._last_doc.page_count if self._last_doc else 0
        self.counter.configure(text='{:02d} / {:02d}'.format(page_num + 1, total))
        self._sync_page_entry()
        self.prev_button.configure_state(page_num > 0)
        self.next_button.configure_state(page_num + 1 < total)

    def set_history(self, can_undo, can_redo):
        if getattr(self, 'undo_button', None) is not None:
            self.undo_button.configure_state(can_undo)
        if getattr(self, 'redo_button', None) is not None:
            self.redo_button.configure_state(can_redo)

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def pack_forget(self):
        self.frame.pack_forget()
