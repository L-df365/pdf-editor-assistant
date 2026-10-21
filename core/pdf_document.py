import os
import shutil
import pymupdf
import tempfile
from .converter import DocumentConverter
from .formats import IMAGE_EXTS


class ChangeHistory:
    """基于快照的撤销/重做。

    页面级操作（插入/删除/移动/旋转）在 PDF 里没有稳定的逆操作，
    统一用「操作前后各存一份快照」实现，代价是每次改动写一次临时文件。
    """

    def __init__(self, limit=5, temp_dir=None):
        self.limit = limit
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix='pdf_hist_')
        self._states = []
        self._index = -1
        self._serial = 0

    def reset(self):
        self._clear_files()
        self._states = []
        self._index = -1

    def _clear_files(self):
        for path in self._states:
            try:
                os.remove(path)
            except OSError:
                pass

    def _write(self, doc):
        self._serial += 1
        path = os.path.join(self.temp_dir, 'state-{}.pdf'.format(self._serial))
        doc.save(path)
        return path

    def capture(self, doc):
        """记录当前状态（打开文档或首次操作时调用）。"""
        if self._index < 0:
            self._states = [self._write(doc)]
            self._index = 0

    def commit(self, doc):
        """提交一次改动，成为新的可回退状态。"""
        self.capture(doc)
        # 丢掉重做分支：快照文件也要一起删，别在临时目录里攒垃圾
        for stale in self._states[self._index + 1:]:
            try:
                os.remove(stale)
            except OSError:
                pass
        del self._states[self._index + 1:]
        self._states.append(self._write(doc))
        self._index = len(self._states) - 1
        while len(self._states) > self.limit + 1:
            stale = self._states.pop(0)
            try:
                os.remove(stale)
            except OSError:
                pass
            self._index -= 1

    @property
    def can_undo(self):
        return self._index > 0

    @property
    def can_redo(self):
        return 0 <= self._index < len(self._states) - 1

    @property
    def undo_steps(self):
        return max(self._index, 0)

    @property
    def redo_steps(self):
        return max(len(self._states) - 1 - self._index, 0)

    def _restore(self, doc, path):
        doc.close()
        return pymupdf.open(path)

    def undo(self, doc):
        if not self.can_undo:
            return None
        self._index -= 1
        return self._restore(doc, self._states[self._index])

    def redo(self, doc):
        if not self.can_redo:
            return None
        self._index += 1
        return self._restore(doc, self._states[self._index])


class PDFDocument:
    """PDF 文档操作封装。"""

    def __init__(self):
        self.doc = None
        self.filepath = None
        self.converter = DocumentConverter()
        self._temp_dir = tempfile.mkdtemp(prefix='pdf_edit_')
        self._modified = False
        self.history = ChangeHistory(limit=5, temp_dir=self._temp_dir)

    @property
    def page_count(self):
        return self.doc.page_count if self.doc is not None else 0

    @property
    def is_modified(self):
        return self._modified

    def open(self, filepath):
        self.close()
        doc = pymupdf.open(filepath)
        self.doc = doc
        self.filepath = filepath
        self._modified = False
        self.history.reset()
        self.history.capture(self.doc)

    def close(self):
        # 注意：不能写 `if self.doc:` —— 已关闭的文档 bool() 会抛
        # ValueError(document closed)，这里一律用 `is not None` 判断。
        if self.doc is not None:
            try:
                self.doc.close()
            except Exception:
                pass
            self.doc = None
            self.filepath = None

    def dispose(self):
        """退出时清理临时文件（历史快照、转换出来的 PDF）。"""
        self.close()
        shutil.rmtree(self._temp_dir, ignore_errors=True)

    def thumbnail_for_width(self, page_num, target_width):
        """按目标像素宽度渲染缩略图（避免固定缩放导致裁切）。"""
        page = self.doc.load_page(page_num)
        rect = page.rect
        zoom = target_width / rect.width if rect.width else 0.2
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
        inserted = 0
        for filepath in filepaths:
            before = self.page_count
            try:
                self.insert_file(filepath, offset, record=False)
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
            inserted += 1
            results.append({
                'path': filepath,
                'ok': True,
                'error': '',
                'pages': added,
            })
        # 一个都没插进去时不要记撤销：否则撤销一次看到的还是原样
        if inserted:
            self.commit_change()
        return results

    def insert_file(self, filepath, position, record=True):
        ext = os.path.splitext(filepath)[1].lower()

        if ext == '.pdf':
            src_doc = pymupdf.open(filepath)
            try:
                self.doc.insert_pdf(src_doc, start_at=position)
            finally:
                src_doc.close()
        elif ext in IMAGE_EXTS:
            self._insert_image(filepath, position)
        else:
            pdf_path = self.converter.convert_to_pdf(
                filepath, output_dir=self._temp_dir
            )
            src_doc = pymupdf.open(pdf_path)
            try:
                self.doc.insert_pdf(src_doc, start_at=position)
            finally:
                src_doc.close()

        if record:
            self.commit_change()

    def _insert_image(self, image_path, position):
        from PIL import Image
        img = Image.open(image_path)
        w, h = img.size
        img.close()

        if self.page_count == 0:
            raise ValueError('文档里还没有页面，无法确定图片尺寸')

        ref_page = self.doc.load_page(0)
        page_w = ref_page.rect.width
        page_h = ref_page.rect.height

        new_doc = pymupdf.open()
        try:
            new_page = new_doc.new_page(width=page_w, height=page_h)

            scale = min(page_w / w, page_h / h) * 0.9
            new_w = w * scale
            new_h = h * scale
            x = (page_w - new_w) / 2
            y = (page_h - new_h) / 2

            rect = pymupdf.Rect(x, y, x + new_w, y + new_h)
            new_page.insert_image(rect, filename=image_path)

            self.doc.insert_pdf(new_doc, start_at=position)
        finally:
            new_doc.close()

    def commit_change(self):
        """把当前状态记入撤销历史。"""
        if self.doc is None:
            return
        self.history.commit(self.doc)
        self._modified = True

    def undo(self):
        if self.doc is None:
            return False
        restored = self.history.undo(self.doc)
        if restored is None:
            return False
        self.doc = restored
        self._modified = True
        return True

    def redo(self):
        if self.doc is None:
            return False
        restored = self.history.redo(self.doc)
        if restored is None:
            return False
        self.doc = restored
        self._modified = True
        return True

    def _select_pages(self, order):
        """重排页面，同时保住 PDF 大纲（书签）。

        PyMuPDF 的 select() 会把大纲清空 —— 用户的书签不该因为
        删了一页就消失，所以先取出来、按新顺序重算页码再写回去。
        """
        toc = self.doc.get_toc() or []
        self.doc.select(order)
        if not toc:
            return
        old_to_new = {}
        for new_index, old_index in enumerate(order):
            old_to_new[old_index + 1] = new_index + 1
        count = len(order)
        remapped = []
        for entry in toc:
            level, title, page = entry[0], entry[1], entry[2]
            new_page = old_to_new.get(page)
            if new_page is None:
                new_page = min(max(page, 1), count)
            remapped.append([level, title, new_page])
        try:
            self.doc.set_toc(remapped)
        except Exception:
            pass

    def delete_page(self, page_num):
        if self.page_count <= 1:
            return
        if not 0 <= page_num < self.page_count:
            return
        new_order = [
            i for i in range(self.page_count) if i != page_num
        ]
        self._select_pages(new_order)
        self.commit_change()

    def move_page(self, from_pos, to_pos):
        if from_pos == to_pos:
            return
        if not 0 <= from_pos < self.page_count:
            return
        pages = list(range(self.page_count))
        page = pages.pop(from_pos)
        pages.insert(max(0, min(to_pos, len(pages))), page)
        self._select_pages(pages)
        self.commit_change()

    def rotate_page(self, page_num, angle=90):
        if not 0 <= page_num < self.page_count:
            return
        page = self.doc.load_page(page_num)
        current = page.rotation
        page.set_rotation((current + angle) % 360)
        self.commit_change()

    def save(self, filepath=None):
        if filepath is None:
            filepath = self.filepath
        if not filepath:
            raise ValueError('没有指定保存路径，请先「另存为」')

        if filepath == self.filepath:
            # 覆盖保存：先写临时文件再换名，中途失败不会把原文件写坏
            tmp = filepath + '.tmp'
            try:
                self.doc.save(tmp, garbage=4, deflate=True)
                self.doc.close()
                shutil.move(tmp, filepath)
            except Exception:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
                # 文档可能已经被关掉了，重新打开一份保证还能继续用
                if self.doc is not None:
                    try:
                        if self.doc.is_closed:
                            self.doc = pymupdf.open(filepath)
                    except Exception:
                        self.doc = None
                raise
            self.doc = pymupdf.open(filepath)
        else:
            self.doc.save(filepath, garbage=4, deflate=True)

        self.filepath = filepath
        self._modified = False

    def snapshot(self, path):
        """把当前内存状态另存一份（打印用）。

        不碰文档自己的保存状态：不改 filepath，也不清"已修改"标记。
        """
        self.doc.save(path, garbage=4, deflate=True)
        return path

    def export_page_image(self, page_num, path, dpi=150):
        """把某一页导出为图片。"""
        page = self.doc.load_page(page_num)
        pix = page.get_pixmap(dpi=dpi)
        pix.save(path)
        return path

    def get_page_at_zoom(self, page_num, zoom):
        """按指定缩放比渲染页面（1.0 ≈ 72dpi）。"""
        page = self.doc.load_page(page_num)
        mat = pymupdf.Matrix(zoom, zoom)
        return page.get_pixmap(matrix=mat, alpha=False)

    def get_page_image(self, page_num, max_width=800, max_height=600,
                        fit_width=False):
        page = self.doc.load_page(page_num)
        rect = page.rect
        if not rect.width or not rect.height:
            raise ValueError('页面尺寸异常')
        if fit_width:
            zoom = max_width / rect.width
        else:
            zoom = min(max_width / rect.width, max_height / rect.height)
        mat = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        return pix, zoom
