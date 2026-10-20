"""菜单语法：所有菜单面（标题栏菜单、右键菜单、溢出菜单）共用。

规则见 docs/design-system.md §3.3：
1. 分组 ≤ 3 组、每组 ≤ 4 项
2. 文案动词开头、带上下文时写明对象
3. 危险动作最后一条、独立成组、危险色
4. 快捷键右对齐
5. 禁用而非隐藏
"""

import tkinter as tk

from gui.theme import DANGER, apply_menu_style


def style_menu(menu):
    return apply_menu_style(menu)


def add_item(menu, label, command=None, accelerator=None, danger=False,
             enabled=True, checked=False):
    """添加一个菜单项，返回其索引。"""
    menu.add_command(
        label=label,
        command=command,
        accelerator=accelerator or '',
        state='normal' if enabled else 'disabled')
    index = menu.index('end')
    if danger:
        menu.entryconfigure(index, foreground=DANGER)
    if checked:
        menu.entryconfigure(index, foreground=DANGER)
    return index


def add_group(menu):
    menu.add_separator()


class ContextMenu:
    """单实例右键菜单：构建一次，打开时刷新文案。

    每次右键都新建 tk.Menu 会造成实例泄漏，也让样式难以统一。
    """

    def __init__(self, parent, on_insert=None, on_rotate=None,
                 on_delete=None, on_zoom=None, on_export=None):
        self.parent = parent
        self.on_insert = on_insert
        self.on_rotate = on_rotate
        self.on_delete = on_delete
        self.on_zoom = on_zoom
        self.on_export = on_export
        self.page_num = 0
        self.menu = style_menu(tk.Menu(parent, tearoff=0))
        self._build()

    def _build(self):
        menu = self.menu
        menu.delete(0, 'end')
        add_item(menu, '在第 1 页后插入文件…', command=self._insert)
        add_group(menu)
        add_item(menu, '逆时针旋转 90°', command=lambda: self._rotate(-90))
        add_item(menu, '顺时针旋转 90°', command=lambda: self._rotate(90))
        add_group(menu)
        add_item(menu, '删除第 1 页', command=self._delete, danger=True)

    def bind_page(self, page_num):
        self.page_num = page_num
        self.menu.entryconfigure(
            0, label='在第 {} 页后插入文件…'.format(page_num + 1))
        self.menu.entryconfigure(
            self.menu.index('end'), label='删除第 {} 页'.format(page_num + 1))

    def popup(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)
        self.menu.bind('<FocusOut>', lambda e: self.menu.unpost())

    # -- 动作 ----------------------------------------------------------

    def _insert(self):
        if self.on_insert:
            self.on_insert(self.page_num)

    def _rotate(self, angle):
        if self.on_rotate:
            self.on_rotate(self.page_num, angle)

    def _delete(self):
        if self.on_delete:
            self.on_delete(self.page_num)


class PreviewMenu:
    """预览区右键菜单：只看不动的一组命令。"""

    def __init__(self, parent, on_zoom=None, on_insert=None,
                 on_export=None):
        self.parent = parent
        self.on_zoom = on_zoom
        self.on_insert = on_insert
        self.on_export = on_export
        self.page_num = 0
        self.menu = style_menu(tk.Menu(parent, tearoff=0))
        add_item(self.menu, '适应页面', command=lambda: self._zoom('fit'))
        add_item(self.menu, '实际大小 100%', command=lambda: self._zoom(1.0))
        add_item(self.menu, '放大 200%', command=lambda: self._zoom(2.0))
        add_group(self.menu)
        add_item(self.menu, '导出当前页为图片…', command=self._export)
        add_item(self.menu, '在第 1 页后插入文件…', command=self._insert)

    def bind_page(self, page_num):
        self.page_num = page_num
        self.menu.entryconfigure(
            self.menu.index('end'),
            label='在第 {} 页后插入文件…'.format(page_num + 1))

    def popup(self, event):
        self.menu.tk_popup(event.x_root, event.y_root)
        self.menu.bind('<FocusOut>', lambda e: self.menu.unpost())

    def _zoom(self, mode):
        if self.on_zoom:
            self.on_zoom(mode)

    def _insert(self):
        if self.on_insert:
            self.on_insert(self.page_num)

    def _export(self):
        if self.on_export:
            self.on_export(self.page_num)
