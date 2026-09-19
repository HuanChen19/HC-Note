# -*- coding: utf-8 -*-
"""HC-Note LOGO 处理：去除纯白背景，重建 alpha 通道，导出多尺寸图标。

输入为 1254x1254 的正方形图标源图（JPEG，纯白背景）。
策略：
1. 以纯白为基准做颜色距离判定，生成前景遮罩；
2. 距离落在过渡带的像素按比例给 alpha，保留原图的抗锯齿边缘；
3. 对遮罩做轻微羽化并清理低 alpha 噪点；
4. 裁到主体外接框后补成正方形画布，导出 logo.png 与多尺寸图标 + app.ico。

历史说明：更早版本处理的是 154x139 的截图（四角色偏不一致），
那版改用边缘泛洪判定背景。本版本源图背景是规整纯白，颜色距离法足够。
"""

import os
import sys

from PIL import Image, ImageFilter


SRC = (r"C:\Users\HuanChen\.workbuddy\clipboard-images"
       r"\clipboard-2026-09-19T15-21-13-349Z-8bf0fd37.jpg")
ROOT = r"E:\1My_Files\.Project\HC-Note"
OUT_ICONS = os.path.join(ROOT, "assets", "icons")

# 背景为纯白，阈值可以放得比较宽松：
# 距离 < NEAR 判定为背景；距离 > FAR 判定为前景；之间按比例给 alpha。
NEAR = 18.0        # 与白色的距离小于此值 -> 完全透明
FAR = 52.0         # 与白色的距离大于此值 -> 完全不透明
FEATHER = 0.6      # 羽化半径
MIN_ALPHA = 10     # 低于该 alpha 直接归零，清掉 JPEG 压缩噪点


def clear_corner_haze(image, threshold=8):
    """清除小尺寸缩放后圆角外侧的极淡残影。

    Lanczos 降采样会在圆角边界外留下 alpha 极低的像素（例如 1-7），
    在深色背景下会呈现为一层几乎不可见但确实存在的灰雾。
    这里把低于阈值的 alpha 直接归零。
    """
    px = image.load()
    w, h = image.size
    cleared = 0
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if 0 < a < threshold:
                px[x, y] = (r, g, b, 0)
                cleared += 1
    return image


def main():
    if not os.path.isfile(SRC):
        print("SRC NOT FOUND: " + SRC)
        return 1

    if not os.path.isdir(OUT_ICONS):
        os.makedirs(OUT_ICONS)

    img = Image.open(SRC).convert("RGBA")
    w, h = img.size
    print("source: %dx%d" % (w, h))

    px = img.load()

    # 构建遮罩：距离白色越远越不透明
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y][:3]
            d = ((255 - r) ** 2 + (255 - g) ** 2 + (255 - b) ** 2) ** 0.5
            if d <= NEAR:
                mp[x, y] = 0
            elif d >= FAR:
                mp[x, y] = 255
            else:
                mp[x, y] = int(255.0 * (d - NEAR) / (FAR - NEAR))

    mask = mask.filter(ImageFilter.GaussianBlur(FEATHER))

    # 清理低 alpha 噪点
    mp = mask.load()
    cleared = 0
    for y in range(h):
        for x in range(w):
            if 0 < mp[x, y] < MIN_ALPHA:
                mp[x, y] = 0
                cleared += 1
    print("cleared low-alpha noise pixels: %d" % cleared)

    out = img.copy()
    out.putalpha(mask)

    bbox = mask.getbbox()
    print("foreground bbox: %s" % (bbox,))
    if bbox:
        cropped = out.crop(bbox)
    else:
        cropped = out
    cw, ch = cropped.size
    print("cropped: %dx%d" % (cw, ch))

    # 补成正方形画布，主体居中，留少量呼吸边距
    side = max(cw, ch)
    pad = int(side * 0.02)
    canvas_side = side + pad * 2
    canvas = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    canvas.paste(cropped, ((canvas_side - cw) // 2, (canvas_side - ch) // 2), cropped)
    print("canvas: %dx%d" % (canvas_side, canvas_side))

    logo_path = os.path.join(OUT_ICONS, "logo.png")
    canvas.save(logo_path, "PNG")
    print("saved: " + logo_path)

    # 小尺寸专用画布：不留呼吸边距，让主体尽量填满，提升 16/32px 下的辨识度
    small_canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    small_canvas.paste(cropped, ((side - cw) // 2, (side - ch) // 2), cropped)

    sizes = [256, 128, 64, 48, 32, 16]
    frames = []
    for s in sizes:
        # 极小尺寸下额外内缩留白会明显削弱辨识度，用小尺寸专用画布放大主体
        src = small_canvas if s <= 32 else canvas
        im = src.resize((s, s), Image.LANCZOS)
        im = clear_corner_haze(im)
        p = os.path.join(OUT_ICONS, "icon_%d.png" % s)
        im.save(p, "PNG")
        frames.append(im)
        print("saved: " + p)

    # 高分辨率版本，供文档与展示使用
    hero_path = os.path.join(OUT_ICONS, "logo_512.png")
    canvas.resize((512, 512), Image.LANCZOS).save(hero_path, "PNG")
    print("saved: " + hero_path)

    ico_path = os.path.join(OUT_ICONS, "app.ico")
    frames[0].save(ico_path, format="ICO", sizes=[(s, s) for s in sizes])
    print("saved: " + ico_path)

    tray_path = os.path.join(OUT_ICONS, "tray.png")
    tray = clear_corner_haze(canvas.resize((64, 64), Image.LANCZOS))
    tray.save(tray_path, "PNG")
    print("saved: " + tray_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
