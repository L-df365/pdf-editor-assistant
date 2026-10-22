import tkinter as tk
from tkinter import ttk

from gui.feedback import attach_tooltip
from gui.menu import MenuPopover, build
from gui.widgets import FlatButton, RoundedCard, ZoomSlider
from gui.theme import (ACCENT, ACCENT_TINT, BG, INK_2, INK_3, LINE, MARKER,
                        PAPER, SURFACE, font)


class ThumbnailPanel:
    """左侧页面轨：等宽页码列 + 缩略图，支持拖拽排序和右键菜单。

    布局规则：**列宽摊满可用宽度，列数由摊出来的宽度反推**。
    以前是"宽度到某个档位就排 N 列"+"缩略图高度卡住"，两个限制叠在一起，
    列只能往左挤，右边空一大块。现在列永远刚好排满，缩略图随宽度变大。
    """

    CARD_TARGET = 150     # 一列的理想宽度（像素），列数按它反推
    CARD_MIN = 110        # 一列的最小宽度：再窄缩略图就看不清了
    CARD_MAX_COLS = 4     # 最多排四列
    CARD_GAP = 10
    CARD_MARGIN = 8       # 卡片区左右留白
    INDEX_WIDTH = 30      # 页码列宽
    THUMB_MAX_HEIGHT = 230  # 缩略图最大高度（再高就没法一屏看几页了）

    #: 轨道缩放条的范围（100% = 自适应的大小）
    RAIL_ZOOM_MIN = 30
    RAIL_ZOOM_MAX = 250
    RAIL_ZOOM_STEP = 10


    def __init__(self, parent, on_select=None, on_reorder=None,
                 on_delete=None, on_rotate=None, on_insert_after=None):
        self.frame = ttk.Frame(parent, style='Surface.TFrame')
        self.on_select = on_select
        self.on_reorder = on_reorder
        self.on_delete = on_delete
        self.on_rotate = on_rotate
        self.on_insert_after = on_insert_after

        self.doc = None
        self.cards = []          # [{'frame','marker','index','image','page'}]
        self.selected = None
        self._drag_data = {'index': None, 'start_y': None, 'moved': False,
                           'target': None}
        self._drop_line = None
        self._cols = 1
        self._sizes = {}
        self._relayout_job = None
        self._auto = True      # 自适应：缩略图跟着窗口宽度走
        self._zoom = 1.0       # 手动缩放倍率

        canvas_frame = ttk.Frame(self.frame, style='Surface.TFrame')
        canvas_frame.pack(fill='both', expand=True)

        # 画布必须给一个小的 width/height：Tk 画布默认申请 396px 宽，
        # 几何管理器只按申请尺寸分配，画布会把右侧 14px 的滚动条位置挤没。
        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0,
                                bg=SURFACE, highlightbackground=SURFACE,
                                width=120, height=120)
        self.scrollbar = ttk.Scrollbar(
            canvas_frame, orient='vertical', command=self.canvas.yview,
            )
        # 横向滚动条：手动放大缩略图时内容会宽过轨道，得能拖着看
        self.hscrollbar = ttk.Scrollbar(
            canvas_frame, orient='horizontal', command=self.canvas.xview,
            )
        self.inner = tk.Frame(self.canvas, bg=SURFACE)
        # 空轨提示：直接挂在画布上并居中，不要跟着内容滚动
        self.hint = tk.Label(self.canvas, text='打开文档后\n这里显示页样',
                             bg=SURFACE, fg=INK_3, font=font('meta'),
                             justify='center')

        self.inner.bind('<Configure>', self._on_inner_configure)
        self.canvas.create_window((0, 0), window=self.inner, anchor='nw',
                                  tags='inner')
        self.canvas.configure(yscrollcommand=self.scrollbar.set,
                              xscrollcommand=self.hscrollbar.set)

        # 用 grid：滚动条的位置是确定的，反复显示/隐藏才不会把画布挤歪
        self.canvas.grid(row=0, column=0, sticky='nsew')
        self.scrollbar.grid(row=0, column=1, sticky='ns')
        self.hscrollbar.grid(row=1, column=0, sticky='ew')
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        self._context_menu = MenuPopover(self.frame, [])
        self._build_zoom_bar()
        self.canvas.bind('<Configure>', self._on_canvas_resize)
        self.canvas.bind('<Button-1>', self._on_canvas_click)
        self.canvas.bind('<Button-4>',
                         lambda e: self.canvas.yview_scroll(-1, 'units'))
        self.canvas.bind('<Button-5>',
                         lambda e: self.canvas.yview_scroll(1, 'units'))
        self.canvas.bind('<Prior>', lambda e: self.canvas.yview_scroll(
            -1, 'pages'))
        self.canvas.bind('<Next>', lambda e: self.canvas.yview_scroll(
            1, 'pages'))
        self.canvas.bind('<Up>', lambda e: self._move_selection(-1))
        self.canvas.bind('<Down>', lambda e: self._move_selection(1))
        self.canvas.focus_set()

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def _on_inner_configure(self, event):
        self._center_inner()
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        self._sync_scrollbar()

    def _sync_scrollbar(self):
        """内容超出时显示滚动条；滚轮在卡片上也能滚。

        注意 pack 顺序：画布先 pack 会把宽度全占光，滚动条被挤成 0 宽
        （看上去就是"滚动条没了"）。所以用 before= 把滚动条排在画布前面。
        """
        needed = self.inner.winfo_reqheight() > self.canvas.winfo_height() + 4
        if needed:
            if not self.scrollbar.winfo_ismapped():
                self.scrollbar.pack(side='right', fill='y',
                                   before=self.canvas)
        elif self.scrollbar.winfo_ismapped():
            self.scrollbar.pack_forget()
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

    def _on_canvas_resize(self, event):
        self._schedule_relayout()

    def _schedule_relayout(self):
        if self._relayout_job:
            try:
                self.canvas.after_cancel(self._relayout_job)
            except tk.TclError:
                pass
        self._relayout_job = self.canvas.after(120, self._relayout)

    def _build_zoom_bar(self):
        """轨道自己的缩放条：自适应（默认，跟着窗口宽度）+ 手动倍率。"""
        bar = tk.Frame(self.frame, bg=SURFACE)
        bar.pack(fill='x', side='bottom')
        ttk.Separator(self.frame, orient='horizontal').pack(fill='x',
                                                            side='bottom')
        self.auto_button = FlatButton(bar, '自适应', command=self._set_auto,
                                      variant='segment-on', bg=SURFACE,
                                      width=46)
        self.auto_button.pack(side='left', padx=(6, 2), pady=4)
        # 轨道太窄，百分比就不显示了（悬停滑块能看到）
        self.zoom_slider = ZoomSlider(
            bar, from_=self.RAIL_ZOOM_MIN, to=self.RAIL_ZOOM_MAX, value=100,
            step=self.RAIL_ZOOM_STEP, bg=SURFACE, length=64, width=18,
            show_value=False, command=self._on_zoom)
        self.zoom_slider.pack(side='left', padx=(0, 4))
        self._zoom_tip = attach_tooltip(
            self.zoom_slider.scale, '缩略图缩放：{}/{}（自适应=100%）'.format(
                self.RAIL_ZOOM_MIN, self.RAIL_ZOOM_MAX))

    def _set_auto(self):
        """回到自适应：缩略图按窗口宽度自动排。"""
        self._auto = True
        self.auto_button.set_variant('segment-on')
        self.zoom_slider.set_value(100, notify=False)
        self._schedule_relayout()

    def _on_zoom(self, value):
        """手动缩放缩略图。"""
        self._auto = False
        self.auto_button.set_variant('segment')
        self._zoom = (max(self.RAIL_ZOOM_MIN,
                         min(self.RAIL_ZOOM_MAX, value)) / 100.0)
        self._schedule_relayout()

    def _column_count(self, width):
        """按可用宽度算能排几列（自适应模式下用）。

        不是"到某个档位就 N 列"：那样档位之间会空出一大块。
        这里按理想列宽反推，取最接近的那个列数（1~4 列），
        列宽再由可用宽度平均摊开 —— 右边不会剩空白。
        """
        usable = width
        if usable <= 0:
            return 1
        count = int(round((usable + self.CARD_GAP) /
                          float(self.CARD_TARGET + self.CARD_GAP)))
        # 别排得太挤：一列至少要 CARD_MIN 宽，否则缩略图看不清
        while count > 1 and usable < count * (self.CARD_MIN + self.CARD_GAP):
            count -= 1
        return max(1, min(count, self.CARD_MAX_COLS))

    def _sync_hscrollbar(self):
        """放大到内容比轨道宽时，显示横向滚动条。"""
        if getattr(self, '_need_hscroll', False):
            self.hscrollbar.grid()
        else:
            self.hscrollbar.grid_remove()

    def _relayout(self):
        self._relayout_job = None
        if not self.doc or not self.doc.doc:
            return
        width = self.canvas.winfo_width()
        if width < 120:
            # 画布还没布局好，等下一次 <Configure> 再排
            return
        usable = width - self.CARD_MARGIN * 2
        # 先算"自适应"的样子（一列的理想宽度摊开后的缩略图大小）——
        # 手动缩放的 100% 就是它，来回切换才连续
        auto_cols = self._column_count(usable)
        auto_gutter = self.CARD_GAP * (auto_cols - 1)
        auto_available = (usable - auto_gutter) / auto_cols
        base_size = max(auto_available - self.INDEX_WIDTH - 12, 48)
        if self._auto:
            cols = auto_cols
            available = auto_available
        else:
            # 手动缩放：缩略图 = 自适应大小 × 倍率
            size = base_size * self._zoom
            card_w = size + self.INDEX_WIDTH + 12
            cols = max(1, int((usable + self.CARD_GAP) //
                              (card_w + self.CARD_GAP)))
            available = card_w
            # 放大到放不下时才需要横向滚动条（按算出来的宽度判断，
            # 不去量控件宽度 —— 那时候布局还没算完，量出来是旧值）
            self._need_hscroll = card_w > usable
        changed = cols != self._cols
        self._cols = cols

        for i, card in enumerate(self.cards):
            page = card['page']
            size = self._thumb_size(page, available, cap=self._auto)
            if changed or self._sizes.get(page) != size:
                self._sizes[page] = size
                self._render_thumb(card, size)
            row, col = divmod(i, cols)
            card['frame'].grid(row=row, column=col, sticky='w',
                               padx=(4 if col == 0 else 0),
                               pady=4)
        self._center_inner()
        self._sync_scrollbar()
        self._sync_hscrollbar()
        # 卡片尺寸是网格算完才定的，等空闲再核一次横向滚动条
        self.canvas.after_idle(self._sync_hscrollbar)

    def _center_inner(self):
        """单列时把整列内容居中：右边空一大块会显得没做完。"""
        if self._cols != 1:
            self.canvas.coords('inner', 0, 0)
            return
        canvas_w = self.canvas.winfo_width()
        inner_w = self.inner.winfo_reqwidth()
        if canvas_w <= 1 or inner_w <= 1:
            return
        self.canvas.coords('inner', max(0, (canvas_w - inner_w) // 2), 0)

    def _thumb_size(self, page, available, cap=True):
        """缩略图尺寸：宽度由列宽决定，高度按页面比例跟着走。

        以前高度被卡死（118px），轨道一宽缩略图也长不大，
        右边就空一块 —— 现在宽度说了算，只留一个高度上限兜底。
        手动缩放时不套这个上限（否则放大两倍只涨一点点）。
        """
        try:
            page_w, page_h = self.doc.get_page_size(page)
        except Exception:
            page_w, page_h = 612.0, 792.0
        if page_w <= 0 or page_h <= 0:
            page_w, page_h = 612.0, 792.0
        # 减掉页码列和卡片内边距，剩下的都给缩略图
        budget = max(available - self.INDEX_WIDTH - 12, 48)
        if not cap:
            return max(40, int(budget))
        by_height = self.THUMB_MAX_HEIGHT * page_w / page_h
        return max(40, int(min(budget, by_height)))

    def _render_thumb(self, card, target_width):
        from PIL import Image, ImageTk
        page = card['page']
        try:
            pix = self.doc.thumbnail_for_width(page, target_width)
            img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
            photo = ImageTk.PhotoImage(img)
        except Exception:
            return
        card['image'].configure(image=photo)
        card['image'].image = photo

    # ------------------------------------------------------------------
    # 内容
    # ------------------------------------------------------------------

    def load_document(self, pdf_doc):
        self.doc = pdf_doc
        self._build_thumbnails()

    def _build_thumbnails(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.cards.clear()
        self._sizes.clear()
        self.selected = None

        if not self.doc or self.doc.page_count == 0:
            # 没有文档时页面轨是空的，给一句居中的提示，别像没做完
            self.hint.place(relx=0.5, rely=0.42, anchor='center')
            self.canvas.configure(scrollregion=self.canvas.bbox('all'))
            return

        self.hint.place_forget()
        for i in range(self.doc.page_count):
            self._add_card(i)
        self._relayout()

    def _add_card(self, page_num):
        # 圆角卡片（抗锯齿）
        frame = RoundedCard(self.inner, radius=5, fill=PAPER, outline=LINE,
                             shadow=False, bg=BG)
        body = frame.body
        marker = tk.Frame(body, width=3, bg=PAPER)
        marker.pack(side='left', fill='y')

        index = tk.Label(body, text='{:02d}'.format(page_num + 1),
                         font=font('num'), anchor='w', bg=PAPER,
                         foreground=INK_2, width=4)
        index.pack(side='left', fill='y', padx=(4, 2))

        image = tk.Label(body, text='', bg=PAPER, cursor='hand2')
        image.pack(side='left', padx=(0, 4), pady=4)

        card = {'frame': frame, 'marker': marker, 'index': index,
                'image': image, 'page': page_num}
        self.cards.append(card)

        for widget in (image, index):
            widget.bind('<Button-4>',
                        lambda e: self.canvas.yview_scroll(-1, 'units'))
            widget.bind('<Button-5>',
                        lambda e: self.canvas.yview_scroll(1, 'units'))
            widget.bind('<ButtonPress-1>',
                        lambda e, p=page_num: self._on_press(e, p))
            widget.bind('<B1-Motion>',
                        lambda e, p=page_num: self._on_motion(e, p))
            widget.bind('<ButtonRelease-1>',
                        lambda e, p=page_num: self._on_release(e, p))
            widget.bind('<Button-3>',
                        lambda e, p=page_num: self._show_menu(e, p))

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------

    def _on_press(self, event, page_num):
        self._drag_data.update(index=page_num, start_y=event.y_root,
                               moved=False, target=None)
        self._clear_drop_line()

    def _on_motion(self, event, page_num):
        data = self._drag_data
        if data.get('index') != page_num:
            return
        start_y = data.get('start_y')
        if start_y is None:
            return
        if abs(event.y_root - start_y) > 5:
            data['moved'] = True
        if data['moved']:
            self._update_drop_indicator(event)

    def _on_release(self, event, page_num):
        data = self._drag_data
        self._clear_drop_line()
        if data.get('moved'):
            target = data.get('target')
            if target is not None and target != page_num:
                if self.on_reorder:
                    self.on_reorder(page_num, target)
        else:
            self._on_click(page_num)
        data.update(index=None, start_y=None, moved=False, target=None)

    def _on_canvas_click(self, event):
        self.canvas.focus_set()

    def _on_click(self, page_num):
        self.select_page(page_num, callback=True)

    def _move_selection(self, delta):
        if not self.cards:
            return
        current = self.selected if self.selected is not None else 0
        target = max(0, min(len(self.cards) - 1, current + delta))
        self.select_page(target, callback=True)
        self.canvas.focus_set()

    # -- 拖拽落点指示 --------------------------------------------------

    def _column_at(self, x):
        """指针落在哪一列（按卡片实际位置判断，不按画布坐标猜）。"""
        best = 0
        best_distance = None
        for card in self.cards:
            col = card['frame'].grid_info().get('column', 0)
            left = card['frame'].winfo_x()
            right = left + card['frame'].winfo_width()
            if left <= x <= right:
                return col
            distance = min(abs(x - left), abs(x - right))
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best = col
        return best

    def _update_drop_indicator(self, event):
        """算出落点：线画在哪、页面插到第几位。

        坐标要换算到"内容坐标系"：事件可能落在卡片、画布、内层框架中的
        任何一个上，event.x/y 是相对那个控件的；画布还会滚动、内容还会
        整列居中。统一用根坐标换算才不会算错列
        （单列时直接用 event.x 会每次都落在第一页）。
        """
        ox, oy = self.canvas.coords('inner')
        view_x = event.x_root - self.canvas.winfo_rootx()
        view_y = event.y_root - self.canvas.winfo_rooty()
        px = self.canvas.canvasx(view_x) - ox
        py = self.canvas.canvasy(view_y) - oy

        col = self._column_at(px)
        column = [card for card in self.cards
                  if card['frame'].grid_info().get('column', 0) == col]
        column.sort(key=lambda card: card['frame'].winfo_y())

        insert_at = 0
        line_y = 0
        line_card = None
        for card in column:
            frame = card['frame']
            top = frame.winfo_y()
            height = frame.winfo_height()
            if py < top + height / 2:
                insert_at = card['page']
                line_y = top
                line_card = frame
                break
        else:
            if column:
                frame = column[-1]['frame']
                insert_at = column[-1]['page'] + 1
                line_y = frame.winfo_y() + frame.winfo_height()
                line_card = frame
            else:
                insert_at, line_y = 0, 0

        # 拖走的那页本身要占位：线在它前面时，实际落点要往前挪一格
        source = self._drag_data.get('index')
        target = insert_at
        if source is not None and source < insert_at:
            target = insert_at - 1

        self._drag_data['target'] = target
        self._draw_drop_line(line_y, line_card, ox, oy)

    def _draw_drop_line(self, y, card, ox, oy):
        """落点线。

        要画在"内容层"里：缩略图是画布上的窗口项（独立的子窗口），
        画在画布上的线会被整块内容盖住，看不见。
        """
        self._clear_drop_line()
        if card is None:
            x = 4
            width = max(self.inner.winfo_width(), 1) - 8
        else:
            x = card.winfo_x()
            width = card.winfo_width()
        line = tk.Frame(self.inner, bg=ACCENT, height=2)
        line.place(x=x, y=max(int(y), 0), width=max(int(width), 1), height=2)
        self._drop_line = line

    def _clear_drop_line(self):
        if self._drop_line is not None:
            try:
                self._drop_line.destroy()
            except tk.TclError:
                pass
            self._drop_line = None

    # ------------------------------------------------------------------
    # 选中
    # ------------------------------------------------------------------

    def select_page(self, page_num, callback=False):
        if self.selected is not None and self.selected < len(self.cards):
            self._paint_card(self.cards[self.selected], False)
        self.selected = page_num
        if 0 <= page_num < len(self.cards):
            self._paint_card(self.cards[page_num], True)
        if callback and self.on_select:
            self.on_select(page_num)

    def scroll_to_page(self, page_num, center=True):
        """把某一页滚到可视区。

        默认居中：跟着右边预览滚动时，当前页的缩略图始终在眼前。
        内容不够一屏时不滚（滚了也没地方去）。
        """
        if not (0 <= page_num < len(self.cards)):
            return
        card = self.cards[page_num]['frame']
        view_h = self.canvas.winfo_height()
        total = self.inner.winfo_reqheight()
        if view_h <= 1 or total <= view_h:
            return                      # 页面不够多，铺不满，不用滚
        y = card.winfo_y()
        h = card.winfo_height()
        if center:
            target = y + h / 2 - view_h / 2
        else:
            target = y - h
        self.canvas.yview_moveto(max(0.0, min(1.0, target / float(total))))

    def _paint_card(self, card, active):
        if active:
            card['frame'].configure(bg=ACCENT_TINT,
                                    highlightbackground=ACCENT)
            card['marker'].configure(bg=MARKER)
            card['index'].configure(foreground=ACCENT,
                                    font=font('num', 'bold'))
            card['image'].configure(bg=ACCENT_TINT)
        else:
            card['frame'].configure(bg=PAPER, highlightbackground=LINE)
            card['marker'].configure(bg=PAPER)
            card['index'].configure(foreground=INK_2, font=font('num'))
            card['image'].configure(bg=PAPER)

    def refresh(self):
        """重建缩略图（文档变了之后调用）。

        重建会清掉选中状态，要先把当前页记下来再恢复，
        否则刷新后当前页的高亮就没了。
        """
        selected = self.selected
        self._build_thumbnails()
        if selected is not None and selected < len(self.cards):
            self.selected = selected
            self._paint_card(self.cards[selected], True)

    def refresh_page(self, page_num):
        for card in self.cards:
            if card['page'] == page_num:
                size = self._sizes.get(page_num)
                if size:
                    self._render_thumb(card, size)
                break

    # ------------------------------------------------------------------
    # 右键菜单
    # ------------------------------------------------------------------

    def _show_menu(self, event, page_num):
        self._context_menu.set_items(build([
            ('在第 {} 页后插入文件…'.format(page_num + 1),
             lambda: self._do_insert_after(page_num)),
            None,
            ('逆时针旋转 90°', lambda: self._do_rotate(page_num, -90)),
            ('顺时针旋转 90°', lambda: self._do_rotate(page_num, 90)),
            None,
            ('删除第 {} 页'.format(page_num + 1),
             lambda: self._do_delete(page_num), '', '', True),
        ]))
        self._context_menu.show(event.x_root, event.y_root)

    def _do_insert_after(self, page_num):
        if self.on_insert_after:
            self.on_insert_after(page_num)

    def _do_rotate(self, page_num, angle):
        if self.on_rotate:
            self.on_rotate(page_num, angle)

    def _do_delete(self, page_num):
        if self.on_delete:
            self.on_delete(page_num)
