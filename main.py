#!/usr/bin/env python3
"""PDF 内嵌编辑助手 —— 入口。

两种启动方式：
- pdf-editor 文件.pdf        打开编辑器
- pdf-editor --print         直接开批量打印窗口（不加载页面管理，启动更快）
"""
import argparse
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='PDF 内嵌编辑助手')
    parser.add_argument(
        'file', nargs='?',
        help='要打开的 PDF 文件（支持 file:// URI）')
    parser.add_argument(
        '--backend', choices=['auto', 'wps', 'libreoffice'],
        help='文件转换后端：auto/wps(本机 WPS 静默)/libreoffice')
    parser.add_argument(
        '--print', action='store_true',
        help='直接打开批量打印窗口（不启动页面管理）')
    return parser.parse_args(argv)


def _to_path(arg):
    """命令行参数可以是路径，也可以是 file:// URI。"""
    if not arg.startswith('file://'):
        return arg
    parsed = urllib.parse.urlparse(arg)
    # file://host/path 里的 host 只能是空或 localhost
    if parsed.netloc not in ('', 'localhost'):
        return arg
    return urllib.request.url2pathname(parsed.path)


def _run_batch_print():
    """独立批量打印：不加载页面管理那一套（也就用不到 PyMuPDF）。"""
    from gui.batch_print_window import BatchPrintWindow
    window = BatchPrintWindow()
    window.run()


def main(argv=None):
    args = _parse_args(argv)
    if args.backend:
        os.environ['PDF_EDIT_BACKEND'] = args.backend

    if args.print:
        _run_batch_print()
        return

    from gui.main_window import MainWindow
    from gui.feedback import toast

    app = MainWindow()
    if args.file:
        filepath = _to_path(args.file)
        if os.path.isfile(filepath):
            app.open_file(filepath)
        else:
            toast(app.root, '打不开这个文件：{}'.format(
                os.path.basename(filepath)), 'warn')
    app.run()


if __name__ == '__main__':
    main()
