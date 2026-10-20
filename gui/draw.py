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


# --------------------------------------------------------------------------
# 抗锯齿圆角（PIL 渲染）
# --------------------------------------------------------------------------

def rounded_image(width, height, radius, fill=None, outline=None,
                  outline_width=1, shadow=False, root=None, pad=0):
    """渲染一张抗锯齿的圆角矩形。

    Canvas 的 pieslice 画出来是硬边（锯齿明显），
    这里用 PIL 超采样后缩回来，得到平滑的圆角。
    """
    from PIL import Image, ImageDraw, ImageFilter

    # 按设备像素比渲染：高分屏上圆角才是干净的。
    # winfo_fpixels('1i') 是每英寸像素数，72 是逻辑 DPI，两者相除才是缩放比。
    scale = 3
    if root is not None:
        try:
            dpi = root.winfo_fpixels('1i')
            scale = max(int(round(dpi / 72.0)), 1) * 2
        except Exception:
            scale = 3
    # pad 是投影需要的留白：卡片本体画在图的 (pad, pad) 处，
    # 调用方要按这个偏移摆放内容，否则圆角和内容会错位。
    pad = max(int(pad), 0)
    w = max(int(width) + pad * 2, 1)
    h = max(int(height) + pad * 2, 1)
    img = Image.new('RGBA', (w * scale, h * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    box = [pad * scale, pad * scale,
            (pad + width) * scale - 1, (pad + height) * scale - 1]
    radius_px = max(int(radius) * scale, 1)

    if shadow:
        layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        layer_draw = ImageDraw.Draw(layer)
        layer_draw.rounded_rectangle(box, radius=radius_px,
                                     fill=(20, 30, 28, 90))
        layer = layer.filter(ImageFilter.GaussianBlur(radius=2.4 * scale))
        img = Image.alpha_composite(img, layer)
        draw = ImageDraw.Draw(img)

    if fill:
        draw.rounded_rectangle(box, radius=radius_px, fill=fill)
    if outline:
        draw.rounded_rectangle(box, radius=radius_px, outline=outline,
                               width=max(int(outline_width) * scale, 1))
    return img.resize((w, h), Image.LANCZOS)


def rounded_photo(width, height, radius, fill=None, outline=None,
                  outline_width=1, shadow=False, root=None, pad=0):
    """rounded_image 的 Tk 版本（返回 PhotoImage）。

    带 shadow 时图像比卡片大 pad*2，卡片位于 (pad, pad)。
    """
    from PIL import ImageTk

    image = rounded_image(width, height, radius, fill, outline,
                          outline_width, shadow, root, pad)
    return ImageTk.PhotoImage(image)
