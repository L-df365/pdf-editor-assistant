import tkinter as tk
from tkinter import ttk


class PreviewPanel:
    """右侧预览面板，显示当前选中页面的大图。"""

    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.current_photo = None
        self.zoom = 1.0
        self._fit_width = True
        self._last_doc = None
        self._last_page = 0

        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill='x', padx=5, pady=3)

        self.btn_fit = ttk.Button(toolbar, text='适应窗口',
                                  command=self._fit_to_window)
        self.btn_fit.pack(side='left', padx=2)
        self.btn_100 = ttk.Button(toolbar, text='100%',
                                  command=self._zoom_100)
        self.btn_100.pack(side='left', padx=2)

        self.page_label = ttk.Label(toolbar, text='', font=('', 10, 'bold'))
        self.page_label.pack(side='right', padx=10)

        sep = ttk.Separator(self.frame, orient='horizontal')
        sep.pack(fill='x')

        canvas_frame = ttk.Frame(self.frame)
        canvas_frame.pack(fill='both', expand=True)

        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0,
                                bg='#808080')
        self.h_scroll = ttk.Scrollbar(canvas_frame, orient='horizontal',
                                      command=self.canvas.xview)
        self.v_scroll = ttk.Scrollbar(canvas_frame, orient='vertical',
                                      command=self.canvas.yview)
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

        self.canvas.bind('<Configure>', self._on_canvas_resize)
        self._canvas_width = 800
        self._canvas_height = 600

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def _on_canvas_resize(self, event):
        self._canvas_width = event.width
        self._canvas_height = event.height
        if self.current_photo:
            self._render_preview()

    def show_page(self, pdf_doc, page_num):
        if not pdf_doc or not pdf_doc.doc:
            return
        from PIL import Image, ImageTk
        self.page_label.configure(text=f'第 {page_num + 1} 页')

        max_w = max(self._canvas_width - 40, 200)
        max_h = max(self._canvas_height - 40, 200)
        pix, zoom = pdf_doc.get_page_image(page_num,
                                            max_width=max_w,
                                            max_height=max_h,
                                            fit_width=self._fit_width)
        self.zoom = zoom

        img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
        self.current_photo = ImageTk.PhotoImage(img)

        x = max((self._canvas_width - pix.width) // 2, 10)
        self.canvas.delete('all')
        self.canvas.create_image(x, 10, anchor='nw',
                                 image=self.current_photo, tags='preview')
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _fit_to_window(self):
        self._fit_width = True
        self._render_preview()

    def _zoom_100(self):
        self._fit_width = False
        self._render_preview()

    def _render_preview(self):
        if self._last_doc and self._last_doc.doc:
            self.show_page(self._last_doc, self._last_page)

    def set_last(self, doc, page_num):
        self._last_doc = doc
        self._last_page = page_num
