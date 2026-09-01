import tkinter as tk
from tkinter import ttk


class ThumbnailPanel:
    """左侧缩略图面板，支持拖拽排序和右键菜单。"""

    THUMB_HEIGHT = 190
    PADDING = 8

    def __init__(self, parent, on_select=None, on_reorder=None,
                 on_delete=None, on_rotate=None, on_insert_after=None):
        self.frame = ttk.Frame(parent)
        self.on_select = on_select
        self.on_reorder = on_reorder
        self.on_delete = on_delete
        self.on_rotate = on_rotate
        self.on_insert_after = on_insert_after

        self.doc = None
        self.thumbnails = []
        self.labels = []
        self.selected = None
        self._drag_data = {'index': None, 'start_y': None}

        canvas_frame = ttk.Frame(self.frame)
        canvas_frame.pack(fill='both', expand=True)

        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0,
                                bg='#f0f0f0')
        self.scrollbar = ttk.Scrollbar(canvas_frame, orient='vertical',
                                       command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg='#f0f0f0')

        self.inner.bind('<Configure>',
                        lambda e: self.canvas.configure(
                            scrollregion=self.canvas.bbox('all')))
        self.canvas.create_window((0, 0), window=self.inner, anchor='nw',
                                  tags='inner')
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side='left', fill='both', expand=True)
        self.scrollbar.pack(side='right', fill='y')

        self.canvas.bind('<Configure>', self._on_canvas_resize)

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def _on_canvas_resize(self, event):
        self.canvas.itemconfig('inner', width=event.width)

    def _bind_mousewheel(self, widget):
        widget.bind('<Button-4>',
                    lambda e: self.canvas.yview_scroll(-1, 'units'))
        widget.bind('<Button-5>',
                    lambda e: self.canvas.yview_scroll(1, 'units'))

    def load_document(self, pdf_doc):
        self.doc = pdf_doc
        self._build_thumbnails()

    def _build_thumbnails(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.thumbnails.clear()
        self.labels.clear()
        self.selected = None

        if not self.doc or self.doc.page_count == 0:
            return

        for i in range(self.doc.page_count):
            self._add_thumb(i)

    def _add_thumb(self, page_num):
        from PIL import Image, ImageTk
        pix = self.doc.get_page_pixmap(page_num, zoom=0.35)
        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        photo = ImageTk.PhotoImage(img)
        self.thumbnails.append(photo)

        frame = tk.Frame(self.inner, relief='solid', borderwidth=1,
                         bg='#ffffff')
        frame.pack(padx=self.PADDING, pady=4, fill='x')

        lbl = tk.Label(frame, image=photo, cursor='hand2', bg='#ffffff')
        lbl.pack(padx=2, pady=2)
        lbl.image = photo

        info = tk.Label(frame, text=f'第 {page_num + 1} 页',
                        font=('', 9), anchor='center', bg='#ffffff')
        info.pack(fill='x', pady=(0, 2))

        def make_handler(p):
            def on_press(event):
                self._drag_data['index'] = p
                self._drag_data['start_y'] = event.y_root
                self._drag_data['moved'] = False

            def on_motion(event):
                if self._drag_data.get('index') == p:
                    dy = abs(event.y_root - self._drag_data.get('start_y', event.y_root))
                    if dy > 5:
                        self._drag_data['moved'] = True

            def on_release(event):
                if self._drag_data.get('moved'):
                    self._end_drag(event, p)
                else:
                    self._on_click(p)
                self._drag_data['index'] = None
                self._drag_data['start_y'] = None
                self._drag_data['moved'] = False

            lbl.bind('<ButtonPress-1>', on_press)
            lbl.bind('<B1-Motion>', on_motion)
            lbl.bind('<ButtonRelease-1>', on_release)

        make_handler(page_num)
        lbl.bind('<Button-3>', lambda e, p=page_num: self._show_menu(e, p))

        self._bind_mousewheel(frame)
        self._bind_mousewheel(lbl)

        self.labels.append((frame, lbl, info))

    def _on_click(self, page_num):
        self.select_page(page_num, callback=True)

    def select_page(self, page_num, callback=False):
        if self.selected is not None and self.selected < len(self.labels):
            frame, _, _ = self.labels[self.selected]
            frame.configure(relief='solid', bg='#ffffff')
            for child in frame.winfo_children():
                child.configure(bg='#ffffff')
        self.selected = page_num
        if page_num < len(self.labels):
            frame, _, _ = self.labels[page_num]
            frame.configure(relief='raised', borderwidth=2, bg='#e0e0ff')
            for child in frame.winfo_children():
                child.configure(bg='#e0e0ff')
        if callback and self.on_select:
            self.on_select(page_num)

    def refresh(self):
        self._build_thumbnails()

    def refresh_page(self, page_num):
        if page_num < len(self.labels):
            from PIL import Image, ImageTk
            _, lbl, _ = self.labels[page_num]
            pix = self.doc.get_page_pixmap(page_num, zoom=0.35)
            img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
            photo = ImageTk.PhotoImage(img)
            self.thumbnails[page_num] = photo
            lbl.configure(image=photo)
            lbl.image = photo

    def _end_drag(self, event, page_num):
        start = self._drag_data.get('index')
        start_y = self._drag_data.get('start_y')
        self._drag_data['index'] = None
        self._drag_data['start_y'] = None

        if start is None or start_y is None:
            return

        delta = event.y_root - start_y
        if abs(delta) < 20:
            return

        page_height = self.THUMB_HEIGHT + self.PADDING * 2
        shift = round(delta / page_height)
        if shift == 0:
            return

        target = max(0, min(self.doc.page_count - 1, start + shift))
        if self.on_reorder:
            self.on_reorder(start, target)

    def _show_menu(self, event, page_num):
        menu = tk.Menu(self.frame, tearoff=0)
        menu.add_command(
            label=f'在第 {page_num + 1} 页后插入文件',
            command=lambda: self._do_insert_after(page_num))
        menu.add_separator()
        menu.add_command(
            label=f'旋转第 {page_num + 1} 页',
            command=lambda: self._do_rotate(page_num))
        menu.add_command(
            label=f'删除第 {page_num + 1} 页',
            command=lambda: self._do_delete(page_num))
        menu.tk_popup(event.x_root, event.y_root)

    def _do_insert_after(self, page_num):
        if self.on_insert_after:
            self.on_insert_after(page_num)

    def _do_rotate(self, page_num):
        if self.on_rotate:
            self.on_rotate(page_num)

    def _do_delete(self, page_num):
        if self.on_delete:
            self.on_delete(page_num)
