"""绘图工具：抗锯齿圆角矩形。

Tk 的 Canvas 只能画硬边圆角（pieslice 拼出来的边缘有明显锯齿），
所以圆角统一用 PIL 渲染成图片再贴到画布上：
按设备像素比超采样画完再缩回来，边缘才是平滑的。
"""


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
