"""打印前的准备。

打印的是"当前状态"——用户在编辑器里改了还没保存，打印出来的也应该是改后的内容，
所以要把内存里的文档另存一份临时 PDF 交给 CUPS，不能直接打印磁盘上的旧文件。
"""

import os

from . import printers


def snapshot(doc, path=None):
    """把内存中的文档另存一份临时 PDF，返回路径。

    不动文档自己的保存状态（不改 filepath、不清"已修改"标记）。
    """
    if path is None:
        path = printers.temp_pdf_path()
    doc.snapshot(path)
    return path


def cleanup(path):
    """删掉临时文件（CUPS 提交时已经把内容收走了，提交完就能删）。"""
    if not path:
        return
    try:
        os.remove(path)
    except OSError:
        pass
