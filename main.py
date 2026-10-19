#!/usr/bin/env python3
import argparse
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.main_window import MainWindow


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description='PDF 内嵌编辑助手')
    parser.add_argument(
        'file', nargs='?',
        help='要打开的 PDF 文件（支持 file:// URI）')
    parser.add_argument(
        '--backend', choices=['auto', 'wps', 'libreoffice'],
        help='文件转换后端：auto/wps(本机 WPS 静默)/libreoffice')
    return parser.parse_args(argv)


def main(argv=None):
    args = _parse_args(argv)
    if args.backend:
        os.environ['PDF_EDIT_BACKEND'] = args.backend

    app = MainWindow()
    if args.file:
        filepath = args.file
        if filepath.startswith('file://'):
            filepath = filepath[7:]
        filepath = urllib.parse.unquote(filepath)
        if os.path.isfile(filepath):
            app.open_file(filepath)
    app.run()


if __name__ == '__main__':
    main()
