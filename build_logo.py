# -*- coding: utf-8 -*-
"""HC-Note LOGO 处理 v2：边缘泛洪去背景 + alpha 重建 + 多尺寸图标导出。

v1 用固定四角取样 + 全局颜色距离，因原图四角色偏不一致导致背景残留。
v2 改为从图幅四边向内做广度优先泛洪，只把「与边缘相连且颜色接近局部背景」的
像素判为背景，能正确保留主体内部的浅色区域。
"""

import os
import sys
from collections import deque

from PIL import Image, ImageFilter


SRC = r"C:\Users\HuanChen\AppData\Local\Temp\731e5dbb-28f8-4303-a178-ff5c7c5b4bf1.png"
ROOT = r"E:\1My_Files\.Project\HC-Note"
OUT_ICONS = os.path.join(ROOT, "assets", "icons")

TOLERANCE = 34.0      # 泛洪时相邻像素允许的颜色跳变
FEATHER = 0.7         # 遮罩羽化半径
MIN_ALPHA = 12        # alpha 低于该值直接视为完全透明


def corners_avg(px, w, h):
    pts = [(2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)]
    rs = gs = bs = 0.0
    for x, y in pts:
        r, g, b = px[x, y][:3]
        rs += r
        gs += g
        bs += b
    n = float(len(pts))
    return rs / n, gs / n, bs / n


def flood_background(img):
    """从四边泛洪标记背景区域，返回背景布尔表。"""
    w, h = img.size
    px = img.load()
    is_bg = [[False] * w for _ in range(h)]
    br, bg, bb = corners_avg(px, w, h)

    q = deque()

    def try_push(x, y, cur):
        if x < 0 or y < 0 or x >= w or y >= h:
            return
        if is_bg[y][x]:
            return
        r, g, b = px[x, y][:3]
        d = ((r - cur[0]) ** 2 + (g - cur[1]) ** 2 + (b - cur[2]) ** 2) ** 0.5
        if d <= TOLERANCE:
            is_bg[y][x] = True
            q.append((x, y))

    # 四边作为种子
    for x in range(w):
        for y in (0, h - 1):
            r, g, b = px[x, y][:3]
            d = ((r - br) ** 2 + (g - bg) ** 2 + (b - bb) ** 2) ** 0.5
            if d <= TOLERANCE * 1.8 and not is_bg[y][x]:
                is_bg[y][x] = True
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            r, g, b = px[x, y][:3]
            d = ((r - br) ** 2 + (g - bg) ** 2 + (b - bb) ** 2) ** 0.5
            if d <= TOLERANCE * 1.8 and not is_bg[y][x]:
                is_bg[y][x] = True
                q.append((x, y))

    while q:
        x, y = q.popleft()
        cur = px[x, y][:3]
        try_push(x + 1, y, cur)
        try_push(x - 1, y, cur)
        try_push(x, y + 1, cur)
        try_push(x, y - 1, cur)

    return is_bg


def main():
    if not os.path.isfile(SRC):
        print("SRC NOT FOUND: " + SRC)
        return 1

    if not os.path.isdir(OUT_ICONS):
        os.makedirs(OUT_ICONS)

    img = Image.open(SRC).convert("RGBA")
    w, h = img.size
    print("source: %dx%d" % (w, h))

    is_bg = flood_background(img)
    bg_count = sum(1 for row in is_bg for v in row if v)
    print("background pixels: %d / %d (%.1f%%)" % (bg_count, w * h, 100.0 * bg_count / (w * h)))

    # 构建遮罩：背景 0，前景 255
    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    px = img.load()
    for y in range(h):
        for x in range(w):
            if not is_bg[y][x]:
                mp[x, y] = 255

    mask = mask.filter(ImageFilter.GaussianBlur(FEATHER))

    # 二次阈值清理半透明噪点
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            v = mp[x, y]
            if v < MIN_ALPHA:
                mp[x, y] = 0

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

    side = max(cw, ch)
    pad = int(side * 0.07)
    canvas_side = side + pad * 2
    canvas = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    canvas.paste(cropped, ((canvas_side - cw) // 2, (canvas_side - ch) // 2), cropped)

    logo_path = os.path.join(OUT_ICONS, "logo.png")
    canvas.save(logo_path, "PNG")
    print("saved: " + logo_path)

    sizes = [256, 128, 64, 48, 32, 16]
    frames = []
    for s in sizes:
        im = canvas.resize((s, s), Image.LANCZOS)
        p = os.path.join(OUT_ICONS, "icon_%d.png" % s)
        im.save(p, "PNG")
        frames.append(im)
        print("saved: " + p)

    ico_path = os.path.join(OUT_ICONS, "app.ico")
    frames[0].save(ico_path, format="ICO", sizes=[(s, s) for s in sizes])
    print("saved: " + ico_path)

    tray_path = os.path.join(OUT_ICONS, "tray.png")
    canvas.resize((64, 64), Image.LANCZOS).save(tray_path, "PNG")
    print("saved: " + tray_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
