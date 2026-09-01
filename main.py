#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.main_window import MainWindow


def main():
    app = MainWindow()
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if os.path.isfile(filepath):
            app.open_file(filepath)
    app.run()


if __name__ == '__main__':
    main()
