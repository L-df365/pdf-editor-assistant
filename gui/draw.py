"""绘图工具：圆角矩形。

Tk 的 Canvas 没有圆角矩形，用 smooth 多边形画出来仍然是方角，
所以这里用「四个角的 pieslice + 中间两段矩形 + 单独描边」拼。
"""

SHADOW_TONES = ('#C6CECC', '#D0D7D5', '#D8DEDC')


def rounded_rect(canvas, x0, y0, x1, y1, r, fill='', outline='',
                 width=1, tags=()):
    """画一个圆角矩形（填充与描边分开处理）。"""
    r = max(2, min(r, (x1 - x0) // 2, (y1 - y0) // 2))
    corners = (
        (x0, y0, 90, 90),                   # 左上
        (x1 - 2 * r, y0, 0, 90),            # 右上
        (x1 - 2 * r, y1 - 2 * r, 270, 90),  # 右下
        (x0, y1 - 2 * r, 180, 90),          # 左下
    )
    if fill:
        for cx, cy, start, extent in corners:
            canvas.create_arc(cx, cy, cx + 2 * r, cy + 2 * r, start=start,
                              extent=extent, style='pieslice', fill=fill,
                              outline='', tags=tags)
        canvas.create_rectangle(x0 + r, y0, x1 - r, y1, fill=fill, outline='',
                                tags=tags)
        canvas.create_rectangle(x0, y0 + r, x1, y1 - r, fill=fill, outline='',
                                tags=tags)
    if outline:
        for cx, cy, start, extent in corners:
            canvas.create_arc(cx, cy, cx + 2 * r, cy + 2 * r, start=start,
                              extent=extent, style='arc', outline=outline,
                              width=width, tags=tags)
        canvas.create_line(x0 + r, y0, x1 - r, y0, fill=outline, width=width,
                           tags=tags)
        canvas.create_line(x0 + r, y1, x1 - r, y1, fill=outline, width=width,
                           tags=tags)
        canvas.create_line(x0, y0 + r, x0, y1 - r, fill=outline, width=width,
                           tags=tags)
        canvas.create_line(x1, y0 + r, x1, y1 - r, fill=outline, width=width,
                           tags=tags)


def drop_shadow(canvas, x0, y0, x1, y1, r, offset=3, tags=()):
    """在圆角矩形下方铺一层柔和投影（要最后再画卡片本体）。"""
    for step, tone in enumerate(reversed(SHADOW_TONES), start=1):
        rounded_rect(canvas, x0 + step, y0 + step + offset - 3,
                     x1 + step, y1 + step + offset - 3, r, fill=tone,
                     tags=tags)
