"""自绘菜单浮层。

Tk 的 `tk.Menu` 只能改颜色：没有圆角、阴影、图标、分区，做出来和系统菜单
没什么区别。这里用 Canvas 自己画一个浮层，所有菜单面（顶栏的「⋯」、页面轨
右键、预览区右键）共用它。
"""

import tkinter as tk

from gui.draw import rounded_rect
from gui.theme import (ACCENT, ACCENT_TINT, DANGER, INK, INK_2, INK_3, LINE,
                        PAPER, font)

ROW_HEIGHT = 30
PADDING_X = 12
ICON_X = 14
LABEL_X = 40
CORNER = 6
SHADOW_TONES = ('#C6CECC', '#D0D7D5', '#D8DEDC')
DANGER_TINT = '#F8E7E3'


#: 当前打开的浮层 + 全局点选调度（只装一次，避免反复 bind/unbind）
_LIVE = []
_dispatch_installed = False


def _ensure_dispatch():
    global _dispatch_installed
    if _dispatch_installed:
        return
    root = tk._default_root
    if root is None:
        return
    for sequence in ('<Button-1>', '<Button-3>', '<Escape>'):
        root.bind_all(sequence, _dispatch, add='+')
    _dispatch_installed = True


def _dispatch(event):
    for popover in list(_LIVE):
        popover._handle_dismiss(event)


class MenuItem:
    """一条菜单项。"""

    def __init__(self, label, command=None, accelerator='', icon='',
                 danger=False, enabled=True, checked=False, kind='item'):
        self.label = label
        self.command = command
        self.accelerator = accelerator
        self.icon = icon
        self.danger = danger
        self.enabled = enabled
        self.checked = checked
        self.kind = kind


class MenuPopover:
    """浮层菜单：纸白底、1px 细线、柔和阴影、图标、快捷键提示。"""

    def __init__(self, parent, items, on_close=None):
        self.parent = parent
        self.items = items
        self.on_close = on_close
        self.active = -1
        self._win = None
        self._canvas = None
        self._rows = []
        self._dismiss_func = None
        self._dismiss_binding = ()

    # -- 显示 ----------------------------------------------------------

    def set_items(self, items):
        self.items = items
        if self._win is not None:
            self.hide()

    def show(self, x, y):
        self._build()
        self._win.update_idletasks()
        width = self._win.winfo_reqwidth()
        height = self._win.winfo_reqheight()
        screen_w = self._win.winfo_screenwidth()
        screen_h = self._win.winfo_screenheight()
        if x + width > screen_w - 8:
            x = max(8, x - width)
        if y + height > screen_h - 8:
            y = max(8, y - height)
        self._win.geometry('+{}+{}'.format(x, y))
        self._win.deiconify()
        self._win.focus_set()
        self._install_dismiss_handler()

    def _install_dismiss_handler(self):
        """全局点一下菜单外面就消失（由统一的调度器处理）。"""
        _ensure_dispatch()
        if self not in _LIVE:
            _LIVE.append(self)

    def _remove_dismiss_handler(self):
        if self in _LIVE:
            _LIVE.remove(self)

    def _handle_dismiss(self, event):
        if self._win is None:
            return
        if event.type == '<Escape>':
            self.hide()
            return
        x = getattr(event, 'x_root', 0)
        y = getattr(event, 'y_root', 0)
        left = self._win.winfo_rootx()
        top = self._win.winfo_rooty()
        inside = (left <= x <= left + self._win.winfo_width()
                  and top <= y <= top + self._win.winfo_height())
        if not inside:
            self.hide()

    def hide(self):
        self._remove_dismiss_handler()
        if self._win is not None:
            try:
                self._win.grab_release()
            except tk.TclError:
                pass
            self._win.destroy()
        self._win = None
        if self.on_close:
            self.on_close()

    def _build(self):
        self._win = tk.Toplevel(self.parent)
        self._win.overrideredirect(True)
        self._win.withdraw()
        try:
            self._win.attributes('-topmost', True)
        except tk.TclError:
            pass
        self._canvas = tk.Canvas(self._win, highlightthickness=0, bg=PAPER)
        self._canvas.pack(fill='both', expand=True)

        rows = []
        for item in self.items:
            if item.kind == 'separator':
                rows.append(('separator', item, 9))
            elif item.kind == 'label':
                rows.append(('label', item, 24))
            else:
                rows.append(('item', item, ROW_HEIGHT))
        total = sum(size for _, _, size in rows)
        width = 236

        for offset, tone in enumerate(reversed(SHADOW_TONES), start=1):
            rounded_rect(self._canvas, offset, offset, width + offset,
                     total + offset, CORNER, fill=tone)

        rounded_rect(self._canvas, 0, 0, width, total, CORNER, fill=PAPER,
                 outline=LINE, width=1)

        has_icon = any(getattr(item, 'icon', '') for item in self.items)
        self._label_x = LABEL_X if has_icon else PADDING_X + 2

        y = 0
        self._rows = []
        for kind, item, size in rows:
            if kind == 'separator':
                self._canvas.create_line(PADDING_X, y + 4, width - PADDING_X,
                                         y + 4, fill=LINE)
            elif kind == 'label':
                self._canvas.create_text(
                    PADDING_X, y + size / 2, text=item.label, anchor='w',
                    fill=INK_3, font=font('meta'))
            else:
                self._draw_item(item, y, width, size)
                self._rows.append((item, y, size))
            y += size

        # 明确画布尺寸：否则浮层窗口会比菜单大一圈，露出白底
        self._canvas.configure(width=width + 4, height=total + 4)
        self._win.update_idletasks()
        self._win.geometry('{}x{}'.format(width + 4, total + 4))

        self._canvas.bind('<Motion>', self._on_motion)
        self._canvas.bind('<Button-1>', self._on_click)
        self._canvas.bind('<Button-3>', lambda e: self.hide())
        self._win.bind('<Escape>', lambda e: self.hide())
        self._win.bind('<Key>', self._on_key)

    def _draw_item(self, item, y, width, size):
        color = DANGER if item.danger else INK
        if not item.enabled:
            color = INK_3
        if item.icon:
            self._canvas.create_text(
                ICON_X, y + size / 2, text=item.icon, anchor='w',
                fill=ACCENT if item.checked else (INK_3 if not item.enabled
                                                 else INK_2),
                font=font('body'))
        self._canvas.create_text(
            self._label_x, y + size / 2, text=item.label, anchor='w',
            fill=color, font=font('body'))
        if item.accelerator:
            self._canvas.create_text(
                width - PADDING_X, y + size / 2, text=item.accelerator,
                anchor='e', fill=INK_3, font=font('num'))

    # -- 交互 ----------------------------------------------------------

    def _row_at(self, y):
        for index, (item, top, size) in enumerate(self._rows):
            if top <= y < top + size:
                return index
        return -1

    def _on_motion(self, event):
        index = self._row_at(event.y)
        if index == self.active:
            return
        self.active = index
        self._canvas.delete('hover')
        if index < 0:
            return
        item, top, size = self._rows[index]
        if not item.enabled:
            self.active = -1
            return
        tint = DANGER_TINT if item.danger else ACCENT_TINT
        rounded_rect(self._canvas, 3, top + 1, self._canvas.winfo_width() - 3,
                 top + size - 1, 4, fill=tint, tags='hover')

    def _on_click(self, event):
        if self._win is not None:
            self._win.update_idletasks()
        index = self._row_at(event.y)
        if index < 0:
            self.hide()
            return
        item = self._rows[index][0]
        if not item.enabled:
            return
        command = item.command
        self.hide()
        if command:
            command()

    def _on_key(self, event):
        if not self._rows:
            return
        if event.keysym == 'Down':
            self.active = min(self.active + 1, len(self._rows) - 1)
        elif event.keysym == 'Up':
            self.active = max(self.active - 1, 0)
        elif event.keysym == 'Return':
            if 0 <= self.active < len(self._rows):
                item = self._rows[self.active][0]
                if item.enabled and item.command:
                    command = item.command
                    self.hide()
                    command()
            return
        else:
            return
        self._highlight_active()

    def _highlight_active(self):
        self._canvas.delete('hover')
        if not (0 <= self.active < len(self._rows)):
            return
        item, top, size = self._rows[self.active]
        if not item.enabled:
            return
        tint = DANGER_TINT if item.danger else ACCENT_TINT
        rounded_rect(self._canvas, 3, top + 1, self._canvas.winfo_width() - 3,
                 top + size - 1, 4, fill=tint, tags='hover')


def build(items):
    """items: [(label, command, accelerator, icon, danger, enabled), ...]"""
    result = []
    for entry in items:
        if entry is None:
            result.append(MenuItem('', kind='separator'))
            continue
        label, command = entry[0], entry[1]
        accelerator = entry[2] if len(entry) > 2 else ''
        icon = entry[3] if len(entry) > 3 else ''
        danger = entry[4] if len(entry) > 4 else False
        enabled = entry[5] if len(entry) > 5 else True
        result.append(MenuItem(label, command, accelerator, icon, danger,
                               enabled))
    return result
