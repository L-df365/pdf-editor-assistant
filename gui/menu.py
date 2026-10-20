"""自绘菜单浮层。

Tk 的 `tk.Menu` 只能改颜色：没有圆角、阴影、图标、分区，做出来和系统菜单
没什么区别。这里用 Canvas 自己画一个浮层，所有菜单面（顶栏的「⋯」、页面轨
右键、预览区右键）共用它。
"""

import tkinter as tk

from gui.draw import rounded_photo
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

    def show(self, x, y):
        # 浮层只建一次：每次重建都会重绘带模糊投影的卡片图（很贵），开菜单明显发顿。
        # 卡片图按尺寸缓存，行内容每次重画（否则命令/可用状态会变旧）。
        self._ensure_built()
        self._render()
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

    def _ensure_built(self):
        if self._win is not None:
            return
        self._build()

    def _install_dismiss_handler(self):
        """全局点一下菜单外面就消失（由统一的调度器处理）。"""
        _ensure_dispatch()
        if self not in _LIVE:
            _LIVE.append(self)

    def _remove_dismiss_handler(self):
        if self in _LIVE:
            _LIVE.remove(self)

    def _handle_dismiss(self, event):
        if self._win is None or not self._win.winfo_ismapped():
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
        """收起浮层，但保留窗口实例（下次打开更快）。"""
        self._remove_dismiss_handler()
        if self._win is not None:
            try:
                self._win.grab_release()
            except tk.TclError:
                pass
            try:
                self._win.withdraw()
            except tk.TclError:
                pass
        self.active = -1
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

        self._canvas.bind('<Motion>', self._on_motion)
        self._canvas.bind('<Button-1>', self._on_click)
        self._canvas.bind('<Button-3>', lambda e: self.hide())
        self._win.bind('<Escape>', lambda e: self.hide())
        self._win.bind('<Key>', self._on_key)

    def _render(self):
        """按当前条目重画菜单内容（卡片图按尺寸缓存，不重画阴影）。"""
        rows = []
        for item in self.items:
            if item.kind == 'separator':
                rows.append(('separator', item, 9))
            elif item.kind == 'label':
                rows.append(('label', item, 24))
            else:
                rows.append(('item', item, ROW_HEIGHT))
        total = sum(size for _, _, size in rows)
        width = self._width = 236

        # 卡片背景：抗锯齿圆角 + 柔和投影（Canvas 的 pieslice 是硬边）
        # pad 是投影留白：卡片本体在 (pad, pad)，菜单内容跟着偏移 pad
        pad = self._pad = 6
        self._canvas.configure(width=width + pad * 2, height=total + pad * 2)
        key = (width, total)
        if getattr(self, '_card_key', None) != key:
            self._card_key = key
            self._card_photo = rounded_photo(
                width, total, CORNER, PAPER, LINE, 1, shadow=True,
                root=self.parent, pad=pad)
        self._canvas.delete('card')
        self._canvas.delete('text')
        self._canvas.delete('hover')
        self._canvas.create_image(0, 0, image=self._card_photo,
                                  anchor='nw', tags='card')

        has_icon = any(getattr(item, 'icon', '') for item in self.items)
        self._label_x = LABEL_X if has_icon else PADDING_X + 2

        # 内容相对卡片左边缘偏移 pad（卡片本体在图里的 (pad, pad)）
        self._ox = pad
        y = pad
        self._rows = []
        for kind, item, size in rows:
            if kind == 'separator':
                self._canvas.create_line(PADDING_X + pad, y + 4,
                                         width - PADDING_X + pad,
                                         y + 4, fill=LINE, tags='text')
            elif kind == 'label':
                self._canvas.create_text(
                    PADDING_X + pad, y + size / 2, text=item.label,
                    anchor='w', fill=INK_3, font=font('meta'), tags='text')
            else:
                self._draw_item(item, y, width, size)
                self._rows.append((item, y, size))
            y += size

        # 明确画布尺寸：否则浮层窗口会比菜单大一圈，露出白底
        self._win.update_idletasks()
        self._win.geometry('{}x{}'.format(width + pad * 2, total + pad * 2))

    def _draw_item(self, item, y, width, size):
        color = DANGER if item.danger else INK
        if not item.enabled:
            color = INK_3
        ox = getattr(self, '_ox', 0)
        if item.icon:
            self._canvas.create_text(
                ICON_X + ox, y + size / 2, text=item.icon, anchor='w',
                fill=ACCENT if item.checked else (INK_3 if not item.enabled
                                                 else INK_2),
                font=font('body'), tags='text')
        self._canvas.create_text(
            self._label_x + ox, y + size / 2, text=item.label, anchor='w',
            fill=color, font=font('body'), tags='text')
        if item.accelerator:
            self._canvas.create_text(
                width - PADDING_X + ox, y + size / 2, text=item.accelerator,
                anchor='e', fill=INK_3, font=font('num'), tags='text')

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
        pad = getattr(self, '_pad', 6)
        self._hover_photo = rounded_photo(
            max(self._width - 6, 8), size - 2, 5, tint, root=self.parent)
        self._canvas.create_image(pad + 3, top + 1, image=self._hover_photo,
                                  anchor='nw', tags='hover')
        self._canvas.tag_lower('hover', 'text')
        # 悬停底色必须压在文字下面，否则文字会被盖掉
        self._canvas.tag_lower('hover', 'text')

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
        pad = getattr(self, '_pad', 6)
        self._hover_photo = rounded_photo(
            max(self._width - 6, 8), size - 2, 5, tint, root=self.parent)
        self._canvas.create_image(pad + 3, top + 1, image=self._hover_photo,
                                  anchor='nw', tags='hover')
        self._canvas.tag_lower('hover', 'text')
        # 悬停底色必须压在文字下面，否则文字会被盖掉
        self._canvas.tag_lower('hover', 'text')


def accel_label(spec):
    """把 'Ctrl+Shift+Z' 规整成显示用的顺序。"""
    if not spec:
        return ''
    parts = spec.split('+')
    order = ('Ctrl', 'Alt', 'Shift')
    mods = [p for p in order if p in parts]
    key = parts[-1] if parts else spec
    return '+'.join(mods + [key]) if mods else key


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
