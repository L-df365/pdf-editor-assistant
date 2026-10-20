import tkinter as tk
from tkinter import ttk

from gui.menu import ContextMenu
from gui.theme import (ACCENT, ACCENT_TINT, INK_2, LINE, MARKER, PAPER,
                        SURFACE, font)


class ThumbnailPanel:
    """左侧页面轨：等宽页码列 + 缩略图，支持拖拽排序和右键菜单。

    列数随宽度自适应，缩略图按可用宽度渲染（不再被裁切）。
    """

    THUMB_HEIGHT = 118     # 目标高度（像素）
    CARD_GAP = 10
    INDEX_WIDTH = 30       # 页码列宽
    TWO_COL_MIN = 250      # 达到此宽度显示两列
    THREE_COL_MIN = 430

    def __init__(self, parent, on_select=None, on_reorder=None,
                 on_delete=None, on_rotate=None, on_insert_after=None):
        self.frame = ttk.Frame(parent, style='Surface.TFrame')
        self.on_select = on_select
        self.on_reorder = on_reorder
        self.on_delete = on_delete
        self.on_rotate = on_rotate
        self.on_insert_after = on_insert_after

        self.doc = None
        self.thumbnails = []
        self.cards = []          # [{'frame','marker','index','image','page'}]
        self.selected = None
        self._drag_data = {'index': None, 'start_y': None, 'moved': False,
                           'target': None}
        self._drop_line = None
        self._cols = 1
        self._sizes = {}
        self._relayout_job = None

        canvas_frame = ttk.Frame(self.frame, style='Surface.TFrame')
        canvas_frame.pack(fill='both', expand=True)

        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0,
                                bg=SURFACE, highlightbackground=SURFACE)
        self.scrollbar = ttk.Scrollbar(canvas_frame, orient='vertical',
                                       command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=SURFACE)

        self.inner.bind('<Configure>', self._on_inner_configure)
        self.canvas.create_window((0, 0), window=self.inner, anchor='nw',
                                  tags='inner')
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side='left', fill='both', expand=True)
        self.scrollbar.pack(side='right', fill='y')

        self._context_menu = ContextMenu(
            self.frame,
            on_insert=lambda page: self._do_insert_after(page),
            on_rotate=lambda page, angle: self._do_rotate(page, angle),
            on_delete=lambda page: self._do_delete(page))

        self.canvas.bind('<Configure>', self._on_canvas_resize)
        self.canvas.bind('<Button-1>', self._on_canvas_click)
        self.canvas.bind('<Up>', lambda e: self._move_selection(-1))
        self.canvas.bind('<Down>', lambda e: self._move_selection(1))
        self.canvas.focus_set()

    # ------------------------------------------------------------------
    # 布局
    # ------------------------------------------------------------------

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def _on_inner_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        self._sync_scrollbar()

    def _sync_scrollbar(self):
        needed = self.inner.winfo_reqheight() > self.canvas.winfo_height() + 4
        if needed and not self.scrollbar.winfo_ismapped():
            self.scrollbar.pack(side='right', fill='y')
        elif not needed and self.scrollbar.winfo_ismapped():
            self.scrollbar.pack_forget()

    def _on_canvas_resize(self, event):
        self._schedule_relayout()

    def _schedule_relayout(self):
        if self._relayout_job:
            try:
                self.canvas.after_cancel(self._relayout_job)
            except tk.TclError:
                pass
        self._relayout_job = self.canvas.after(120, self._relayout)

    def _column_count(self, width):
        if width >= self.THREE_COL_MIN:
            return 3
        if width >= self.TWO_COL_MIN:
            return 2
        return 1

    def _relayout(self):
        self._relayout_job = None
        if not self.doc or not self.doc.doc:
            return
        width = self.canvas.winfo_width()
        if width < 120:
            # 画布还没布局好，等下一次 <Configure> 再排
            return
        cols = self._column_count(width)
        gutter = self.CARD_GAP * (cols - 1)
        available = (width - gutter - 8) / cols
        changed = cols != self._cols
        self._cols = cols

        for i, card in enumerate(self.cards):
            page = card['page']
            size = self._thumb_size(page, available)
            if changed or self._sizes.get(page) != size:
                self._sizes[page] = size
                self._render_thumb(card, size)
            row, col = divmod(i, cols)
            card['frame'].grid(row=row, column=col, sticky='w',
                               padx=(4 if col == 0 else 0),
                               pady=4)
        self._sync_scrollbar()

    def _thumb_size(self, page, available):
        """按可用宽度与目标高度共同决定缩略图尺寸（保持比例）。"""
        try:
            page_w, page_h = self.doc.get_page_size(page)
        except Exception:
            page_w, page_h = 612.0, 792.0
        if page_w <= 0 or page_h <= 0:
            page_w, page_h = 612.0, 792.0
        budget = max(available - self.INDEX_WIDTH - 12, 48)
        by_width = budget
        by_height = self.THUMB_HEIGHT * page_w / page_h
        return max(40, int(min(by_width, by_height)))

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
        self.thumbnails.clear()
        self.cards.clear()
        self._sizes.clear()
        self.selected = None

        if not self.doc or self.doc.page_count == 0:
            return

        for i in range(self.doc.page_count):
            self._add_card(i)
        self._relayout()

    def _add_card(self, page_num):
        frame = tk.Frame(self.inner, relief='flat', borderwidth=0,
                         bg=PAPER, highlightbackground=LINE,
                         highlightthickness=1)
        marker = tk.Frame(frame, width=3, bg=PAPER)
        marker.pack(side='left', fill='y')

        index = tk.Label(frame, text='{:02d}'.format(page_num + 1),
                         font=font('num'), anchor='w', bg=PAPER,
                         foreground=INK_2, width=4)
        index.pack(side='left', fill='y', padx=(4, 2))

        image = tk.Label(frame, text='', bg=PAPER, cursor='hand2')
        image.pack(side='left', padx=(0, 4), pady=4)

        card = {'frame': frame, 'marker': marker, 'index': index,
                'image': image, 'page': page_num}
        self.cards.append(card)

        for widget in (image, index):
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

    def _canvas_offset(self):
        top = self.canvas.yview()[0]
        return -top * self.inner.winfo_height()

    def _update_drop_indicator(self, event):
        cy = event.y + self._canvas_offset()
        cx = event.x
        inner_w = max(self.inner.winfo_width(), 1)
        col = 0 if cx < inner_w / 2 else 1

        candidates = []
        for card in self.cards:
            if card['frame'].grid_info().get('column', 0) != col:
                continue
            top = card['frame'].winfo_y()
            height = card['frame'].winfo_height()
            candidates.append((top, height, card['page']))
        candidates.sort()

        target = None
        line_y = None
        for top, height, page in candidates:
            if cy < top + height / 2:
                target = page
                line_y = top
                break
        if target is None:
            if candidates:
                top, height, page = candidates[-1]
                target = page + 1
                line_y = top + height
            else:
                target = 0
                line_y = 0

        self._drag_data['target'] = target
        self._draw_drop_line(line_y, col)

    def _draw_drop_line(self, y, col):
        self._clear_drop_line()
        inner_w = max(self.inner.winfo_width(), 1)
        x0 = 4
        x1 = inner_w // 2 - 4 if col == 0 else inner_w - 4
        if col == 1:
            x0 = inner_w // 2 + 4
        self._drop_line = self.canvas.create_line(
            x0, y, x1, y, fill=ACCENT, width=2, tags='drop')

    def _clear_drop_line(self):
        if self._drop_line is not None:
            self.canvas.delete(self._drop_line)
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
        self._build_thumbnails()
        if self.selected is not None and self.selected < len(self.cards):
            self._paint_card(self.cards[self.selected], True)

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
        self._context_menu.bind_page(page_num)
        self._context_menu.popup(event)

    def _do_insert_after(self, page_num):
        if self.on_insert_after:
            self.on_insert_after(page_num)

    def _do_rotate(self, page_num, angle):
        if self.on_rotate:
            self.on_rotate(page_num, angle)

    def _do_delete(self, page_num):
        if self.on_delete:
            self.on_delete(page_num)
