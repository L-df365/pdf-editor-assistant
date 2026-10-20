import os
import pymupdf
import tempfile
from .converter import DocumentConverter
from .formats import IMAGE_EXTS


class PDFDocument:
    """PDF 文档操作封装。"""

    def __init__(self):
        self.doc = None
        self.filepath = None
        self.converter = DocumentConverter()
        self._temp_dir = tempfile.mkdtemp(prefix='pdf_edit_')
        self._modified = False

    @property
    def page_count(self):
        return self.doc.page_count if self.doc else 0

    @property
    def is_modified(self):
        return self._modified

    def open(self, filepath):
        if self.doc:
            self.doc.close()
        self.doc = pymupdf.open(filepath)
        self.filepath = filepath
        self._modified = False

    def close(self):
        if self.doc:
            self.doc.close()
            self.doc = None
            self.filepath = None

    def get_page_pixmap(self, page_num, zoom=1.0):
        page = self.doc.load_page(page_num)
        mat = pymupdf.Matrix(zoom, zoom)
        return page.get_pixmap(matrix=mat, alpha=False)

    def get_page_size(self, page_num):
        page = self.doc.load_page(page_num)
        return page.rect.width, page.rect.height

    def insert_files(self, filepaths, position):
        """按给定顺序批量插入文件。

        单个文件失败不会回滚已插入的文件；返回逐个文件的结果摘要。
        """
        results = []
        offset = position
        for filepath in filepaths:
            before = self.page_count
            try:
                self.insert_file(filepath, offset)
            except Exception as exc:
                results.append({
                    'path': filepath,
                    'ok': False,
                    'error': str(exc),
                    'pages': 0,
                })
                continue
            added = self.page_count - before
            offset += added
            results.append({
                'path': filepath,
                'ok': True,
                'error': '',
                'pages': added,
            })
        return results

    def insert_file(self, filepath, position):
        ext = os.path.splitext(filepath)[1].lower()

        if ext == '.pdf':
            src_doc = pymupdf.open(filepath)
            self.doc.insert_pdf(src_doc, start_at=position)
            src_doc.close()
        elif ext in IMAGE_EXTS:
            self._insert_image(filepath, position)
        else:
            pdf_path = self.converter.convert_to_pdf(
                filepath, output_dir=self._temp_dir
            )
            src_doc = pymupdf.open(pdf_path)
            self.doc.insert_pdf(src_doc, start_at=position)
            src_doc.close()

        self._modified = True

    def _insert_image(self, image_path, position):
        from PIL import Image
        img = Image.open(image_path)
        w, h = img.size
        img.close()

        ref_page = self.doc.load_page(0)
        page_w = ref_page.rect.width
        page_h = ref_page.rect.height

        new_doc = pymupdf.open()
        new_page = new_doc.new_page(width=page_w, height=page_h)

        scale = min(page_w / w, page_h / h) * 0.9
        new_w = w * scale
        new_h = h * scale
        x = (page_w - new_w) / 2
        y = (page_h - new_h) / 2

        rect = pymupdf.Rect(x, y, x + new_w, y + new_h)
        new_page.insert_image(rect, filename=image_path)

        self.doc.insert_pdf(new_doc, start_at=position)
        new_doc.close()

    def delete_page(self, page_num):
        if self.page_count <= 1:
            return
        new_order = [
            i for i in range(self.page_count) if i != page_num
        ]
        self.doc.select(new_order)
        self._modified = True

    def move_page(self, from_pos, to_pos):
        if from_pos == to_pos:
            return
        pages = list(range(self.page_count))
        page = pages.pop(from_pos)
        pages.insert(to_pos, page)
        self.doc.select(pages)
        self._modified = True

    def rotate_page(self, page_num, angle=90):
        page = self.doc.load_page(page_num)
        current = page.rotation
        page.set_rotation((current + angle) % 360)
        self._modified = True

    def save(self, filepath=None):
        import shutil
        import tempfile

        if filepath is None:
            filepath = self.filepath

        if filepath == self.filepath:
            tmp = filepath + '.tmp'
            self.doc.save(tmp, garbage=4, deflate=True)
            self.doc.close()
            shutil.move(tmp, filepath)
            self.doc = pymupdf.open(filepath)
        else:
            self.doc.save(filepath, garbage=4, deflate=True)

        self.filepath = filepath
        self._modified = False

    def get_page_image(self, page_num, max_width=800, max_height=600,
                        fit_width=False):
        page = self.doc.load_page(page_num)
        rect = page.rect
        if fit_width:
            zoom = max_width / rect.width
        else:
            zoom = min(max_width / rect.width, max_height / rect.height)
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return pix, zoom
