"""Bonsai .ico: the widget's detailed tree for large sizes, a bold simplified one for small sizes.

Usage: make_icon.py [out.ico] [preview.png]   (defaults: widget/bonsai.ico, icon_preview.png)
"""
import importlib.util
import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("bw", os.path.join(ROOT, "widget", "bonsai_widget.pyw"))
bw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bw)

out_ico = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "widget", "bonsai.ico")
out_png = sys.argv[2] if len(sys.argv) > 2 else "icon_preview.png"
G = 0.52
RADIUS = 0.22


def rounded(img):
    S = img.width
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=int(S * RADIUS), fill=255)
    tile = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    tile.paste(img, (0, 0), mask)
    w = max(2, S // 170)
    ImageDraw.Draw(tile).rounded_rectangle([w, w, S - 1 - w, S - 1 - w], radius=int(S * RADIUS),
                                           outline=(255, 255, 255, 30), width=w)
    return tile


def detailed(S=1024):
    xs, ys = [], []
    for x, y, s, *_ in bw.each_leaf(G):
        xs += [x - 5 * s, x + 5 * s]
        ys += [y - 5 * s, y + 5 * s]
    x0, x1, y0, y1 = min(xs + [116]), max(xs + [484]), min(ys), 456
    side = max(x1 - x0, y1 - y0) * 1.12
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    bw.CROP = (cx - side / 2, cy - side / 2, cx + side / 2, cy + side / 2)
    scene = bw.Scene(S)
    return rounded(scene.render(G, 0, []).crop((0, 0, S, S)))


def simple(S=1024):
    img = Image.new("RGBA", (S, S))
    d = ImageDraw.Draw(img)
    a, b = bw.rgb(bw.C["wall"]), bw.rgb(bw.C["wall2"])
    for y in range(S):
        t = y / S
        d.line([(0, y), (S, y)], fill=tuple(int(bw.lerp(a[i], b[i], t)) for i in range(3)))
    u = S / 100
    # pot
    d.polygon([(17 * u, 72 * u), (83 * u, 72 * u), (77 * u, 86 * u), (23 * u, 86 * u)], fill=bw.C["pot"])
    d.rectangle([14 * u, 69 * u, 86 * u, 74 * u], fill=bw.C["potDark"])
    # trunk: thick S-curve with tapering width
    pts = [(50, 70), (44, 60), (54, 50), (47, 40), (52, 31)]
    widths = [11, 9, 7.5, 6, 5]
    for (p, q), w in zip(zip(pts, pts[1:]), widths):
        d.line([(p[0] * u, p[1] * u), (q[0] * u, q[1] * u)], fill=bw.C["bark"], width=int(w * u))
        r = w * u / 2
        d.ellipse([q[0] * u - r, q[1] * u - r, q[0] * u + r, q[1] * u + r], fill=bw.C["bark"])
    # branches to the pads
    for p, q in (((46, 56), (27, 47)), ((52, 46), (72, 40)), ((49, 36), (35, 27))):
        d.line([(p[0] * u, p[1] * u), (q[0] * u, q[1] * u)], fill=bw.C["bark"], width=int(4 * u))
    # canopy pads: shadow then two greens
    dark, light = bw.leaf_color(0.35)[:3], bw.leaf_color(0.05)[:3]
    for cx, cy, rx, ry in ((26, 45, 17, 10), (73, 38, 17, 10), (37, 25, 15, 9), (58, 19, 15, 9)):
        d.ellipse([(cx - rx) * u, (cy - ry) * u, (cx + rx) * u, (cy + ry) * u], fill=dark)
        d.ellipse([(cx - rx * 0.8) * u, (cy - ry - 1.5) * u, (cx + rx * 0.75) * u, (cy + ry * 0.45) * u], fill=light)
    return rounded(img)


big, small = detailed(), simple()
sizes = [256, 128, 64, 48, 32, 24, 16]
frames = [(big if n >= 64 else small).resize((n, n), Image.LANCZOS) for n in sizes]
frames[0].save(out_ico, format="ICO", sizes=[(n, n) for n in sizes], append_images=frames[1:])

W = sum(f.width for f in frames) + 16 * (len(frames) + 1)
prev = Image.new("RGBA", (W, 256 + 32), (32, 32, 32, 255))
x = 16
for f in frames:
    prev.paste(f, (x, 16 + 256 - f.height), f)
    x += f.width + 16
# also show small sizes enlarged 4x (nearest) so their pixels are visible
zoom = Image.new("RGBA", (4 * (48 + 32 + 24 + 16) + 80, 4 * 48 + 32), (32, 32, 32, 255))
x = 16
for f in frames[3:]:
    z = f.resize((f.width * 4, f.height * 4), Image.NEAREST)
    zoom.paste(z, (x, 16 + 4 * 48 - z.height), z)
    x += z.width + 16
sheet = Image.new("RGBA", (max(prev.width, zoom.width), prev.height + zoom.height), (32, 32, 32, 255))
sheet.paste(prev, (0, 0))
sheet.paste(zoom, (0, prev.height))
sheet.save(out_png)
