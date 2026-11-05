#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decor_recipe.py — 代码渲染的装饰原语库（可 import，也可单独自检）。

项目规范明确写「画面由排版、SVG 与 CSS 生成，不是 AI 生成」时，装饰必须
走代码渲染。本库提供与「暖白纸 + 墨蓝粗描边 + 实心墨蓝投影 + 黄/粉/青/绿
点缀」这套视觉语言一致的图形原语，颜色全部来自 --tokens 色板，不发明新色。

作为库使用:
  from decor_recipe import Palette, make_decor_layer
  pal = Palette.from_file("color-tokens.json")
  layer = make_decor_layer((1600, 900), pal, seed=5,
                           stars=8, magnifier="br", element="letter:br")
  layer.save("decor.png")

命令行自检:
  python3 decor_recipe.py --tokens assets/color-tokens.example.json \
      --out preview.png --stars 10 --magnifier br --element letter:br
"""
import argparse
import json
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter

DEFAULT_TOKENS = {
    "background": {"top": "BFE9FF", "bottom": "FFFDF0", "angle_deg": 90},
    "ink": "17384D",
    "accents": ["FFD23F", "FF5D8F", "2EC4E6", "7BD389"],
}


def rgb(h):
    h = str(h).lstrip("#").upper()
    if h.startswith("SCHEME:"):
        return (23, 56, 77)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Palette:
    def __init__(self, tokens=None):
        t = dict(DEFAULT_TOKENS)
        if tokens:
            t.update(tokens)
        self.raw = t
        self.bg_top = rgb(t["background"]["top"])
        self.bg_bottom = rgb(t["background"]["bottom"])
        self.ink = rgb(t.get("ink", "17384D"))
        self.soft = tuple(min(255, int(c * 1.22 + 24)) for c in self.ink)
        self.paper = (255, 253, 240)
        self.accents = [rgb(c) for c in t.get("accents", DEFAULT_TOKENS["accents"])]
        self.yellow = self.accents[0] if self.accents else (255, 210, 63)
        self.pink = self.accents[1] if len(self.accents) > 1 else (255, 93, 143)
        self.cyan = self.accents[2] if len(self.accents) > 2 else (46, 196, 230)
        self.green = self.accents[3] if len(self.accents) > 3 else (123, 211, 137)
        self.orange = (255, 107, 53)

    @classmethod
    def from_file(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    def accent(self, i):
        return self.accents[i % len(self.accents)] if self.accents else self.yellow


def _layer(size):
    return Image.new("RGBA", size, (0, 0, 0, 0))


def star(d, x, y, r, color, alpha=180, squash=1.0):
    """细长凹形四角星（twinkle）——这套风格最标志性的元素。"""
    pts = []
    for k in range(8):
        ang = math.pi / 4 * k - math.pi / 2
        rad = r if k % 2 == 0 else r * 0.24
        pts.append((x + math.cos(ang) * rad,
                    y + math.sin(ang) * rad * squash))
    d.polygon(pts, fill=color + (alpha,))


def dot_grid(size, pal, spacing=26, alpha=14):
    """app.css 里「让大片天蓝有材质」的极淡 1px 圆点网格。"""
    im = _layer(size)
    d = ImageDraw.Draw(im)
    c = pal.ink + (alpha,)
    for y in range(spacing // 2, size[1], spacing):
        for x in range(spacing // 2, size[0], spacing):
            d.ellipse((x, y, x + 1, y + 1), fill=c)
    return im


def highlighter(d, x0, y0, x1, y1, color, width=18, alpha=48):
    """半透明黄色荧光笔笔触。"""
    d.line((x0, y0, x1, y1), fill=color + (alpha,), width=width)
    d.line((x0, y0 + width // 2, x1, y1 + width // 2),
           fill=color + (max(0, alpha - 20),), width=2)


def ruled_lines(d, x, y, w, n, gap, color, alpha=30):
    for k in range(n):
        yy = y + k * gap
        d.line((x, yy, x + w, yy), fill=color + (alpha,), width=2)


def magnifier(size, pal, alpha=150):
    """项目 Magnifier.jsx 风格：双圈墨蓝镜片 + 橙色柄 + 实心偏移投影。"""
    im = _layer((size, size))
    d = ImageDraw.Draw(im)
    r = size * 0.31
    cx = cy = size * 0.42
    sw = max(3, int(size * 0.022))
    shadow = tuple(int(c * 0.65) for c in pal.ink) + (int(alpha * 0.5),)
    off = size * 0.022
    d.ellipse((cx - r + off, cy - r + off, cx + r + off, cy + r + off),
              outline=shadow, width=sw)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=pal.ink + (alpha,), width=sw)
    d.ellipse((cx - r + sw * 2, cy - r + sw * 2,
               cx + r - sw * 2, cy + r - sw * 2),
              outline=pal.ink + (int(alpha * 0.55),), width=max(2, sw // 2))
    # 柄
    a = math.radians(45)
    hx, hy = cx + r * math.cos(a) * 0.86, cy + r * math.sin(a) * 0.86
    ex, ey = hx + size * 0.24 * math.cos(a), hy + size * 0.24 * math.sin(a)
    d.line((hx + off, hy + off, ex + off, ey + off), fill=shadow, width=sw * 3)
    d.line((hx, hy, ex, ey), fill=pal.orange + (alpha,), width=sw * 3)
    # 镜片内高亮
    d.line((cx - r * .48, cy + r * .16, cx + r * .42, cy + r * .16),
           fill=pal.yellow + (int(alpha * .75),), width=max(3, int(size * .035)))
    return im


def sticker(w, h, pal, fill=None, alpha=150, rotation=0):
    """StickerLayer 胶囊贴纸：彩色填充 + 墨蓝描边 + 实心投影。"""
    pad = 12
    im = _layer((w + pad * 2, h + pad * 2))
    d = ImageDraw.Draw(im)
    f = fill or pal.yellow
    box = (pad, pad, pad + w, pad + h)
    d.rounded_rectangle((box[0] + 5, box[1] + 6, box[2] + 5, box[3] + 6),
                        radius=h // 2, fill=pal.ink + (int(alpha * .45),))
    d.rounded_rectangle(box, radius=h // 2, fill=f + (alpha,),
                        outline=pal.ink + (alpha,), width=3)
    if rotation:
        im = im.rotate(rotation, expand=True, resample=Image.BICUBIC)
    return im


def card_stack(w, h, pal, n=3, alpha=210):
    """一叠白底墨蓝描边的卡片（招式卡 / 教学设计卡 / 索引卡）。"""
    im = _layer((int(w * 1.25), int(h * 1.35)))
    d = ImageDraw.Draw(im)
    for k in range(n):
        x = int(w * .05 * k + 10)
        y = int(h * .12 * (n - 1 - k) + 10)
        box = (x, y, x + w, y + h)
        d.rounded_rectangle((x + 7, y + 8, x + w + 7, y + h + 8), radius=12,
                            fill=pal.ink + (int(alpha * .35),))
        d.rounded_rectangle(box, radius=12, fill=pal.paper + (alpha,),
                            outline=pal.ink + (alpha,), width=4)
        if k == n - 1:
            for j in range(3):
                yy = y + h * .3 + j * h * .17
                d.line((x + w * .14, yy, x + w * (.72 - j * .1), yy),
                       fill=pal.soft + (int(alpha * .8),), width=3)
            d.rounded_rectangle((x + w * .14, y + h * .74,
                                 x + w * .52, y + h * .82), radius=3,
                                fill=pal.yellow + (int(alpha * .8),))
    return im


def letter(w, h, pal, alpha=210):
    """信纸 + 信封（读者回信语义元素）。"""
    im = _layer((int(w * 1.15), int(h * 1.25)))
    d = ImageDraw.Draw(im)
    x, y = 8, int(h * .20)
    d.rounded_rectangle((x + 6, y + 7, x + w + 6, y + h + 7), radius=10,
                        fill=pal.ink + (int(alpha * .35),))
    d.rounded_rectangle((x, y, x + w, y + h), radius=10, fill=pal.paper + (alpha,),
                        outline=pal.ink + (alpha,), width=4)
    for j in range(4):
        yy = y + h * .24 + j * h * .15
        d.line((x + w * .12, yy, x + w * (.82 - j * .09), yy),
               fill=pal.soft + (int(alpha * .75),), width=3)
    # 下方信封
    ey = y + h * .72
    d.polygon([(x, ey), (x + w, ey), (x + w, ey + h * .30),
               (x, ey + h * .30)], fill=pal.paper + (alpha,))
    d.rectangle((x, ey, x + w, ey + h * .30), outline=pal.ink + (alpha,), width=4)
    d.line((x, ey, x + w * .5, ey + h * .19, x + w, ey),
           fill=pal.ink + (alpha,), width=3)
    star(d, x + w * .5, ey + h * .19, 9, pal.yellow, int(alpha * .9))
    return im


def badge(w, h, pal, alpha=200):
    """可收集徽章（79/79、59/59 这类数据页）。"""
    im = _layer((w, h))
    d = ImageDraw.Draw(im)
    c = (w // 2, h // 2)
    r = min(w, h) * .40
    d.ellipse((c[0] - r + 6, c[1] - r + 7, c[0] + r + 6, c[1] + r + 7),
              fill=pal.ink + (int(alpha * .35),))
    d.ellipse((c[0] - r, c[1] - r, c[0] + r, c[1] + r),
              fill=pal.yellow + (alpha,), outline=pal.ink + (alpha,), width=5)
    star(d, c[0], c[1], int(r * .62), pal.paper, int(alpha * .95))
    return im


def quote_card(w, h, pal, alpha=205):
    """黄色高亮引用卡（逐字标注 / 提示词约束页）。"""
    im = card_stack(w, h, pal, n=2, alpha=alpha)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((int(w * .14), int(h * .52), int(w * .80), int(h * .62)),
                        radius=3, fill=pal.yellow + (int(alpha * .85),))
    return im


ELEMENTS = {
    "mag": lambda pal, s: magnifier(s, pal),
    "magnifier": lambda pal, s: magnifier(s, pal),
    "cards": lambda pal, s: card_stack(int(s * .82), int(s * .56), pal, n=3),
    "cards3": lambda pal, s: card_stack(int(s * .82), int(s * .56), pal, n=3),
    "cards5": lambda pal, s: card_stack(int(s * .82), int(s * .56), pal, n=5),
    "letter": lambda pal, s: letter(int(s * .86), int(s * .62), pal),
    "badge": lambda pal, s: badge(int(s * .56), int(s * .56), pal),
    "badges": lambda pal, s: badge(int(s * .56), int(s * .56), pal),
    "sticker": lambda pal, s: sticker(int(s * .72), int(s * .20), pal),
    "quote": lambda pal, s: quote_card(int(s * .80), int(s * .54), pal),
}


def place(base, elem, corner, size, margin=0.055, opacity=0.72):
    """把一个透明元素放到指定角落，自动缩放并留出页边。"""
    W, H = base.size
    target = int(W * size)
    ratio = target / max(1, elem.width)
    eh = max(1, int(elem.height * ratio))
    elem = elem.resize((target, eh), Image.LANCZOS)
    if opacity < 1.0:
        a = elem.getchannel("A").point(lambda v: int(v * opacity))
        elem.putalpha(a)
    mx, my = int(W * margin), int(H * margin)
    pos = {
        "tl": (mx, my),
        "tr": (W - target - mx, my),
        "bl": (mx, H - eh - my),
        "br": (W - target - mx, H - eh - my),
    }
    x, y = pos.get(corner, pos["tr"])
    base.alpha_composite(elem, (max(0, x), max(0, y)))


def make_decor_layer(size, pal, seed=0, stars=8, magnifier_corner=None,
                     element=None, dot=True, center_clear=0.0):
    """组合出一张透明装饰层。center_clear>0 时把中部区域装饰渐隐，保证正文零干扰。"""
    rnd = random.Random(seed)
    base = _layer(size)
    W, H = size
    if dot:
        base = Image.alpha_composite(base, dot_grid(size, pal))
    d = ImageDraw.Draw(base)

    # 四角星只落在边缘带
    for _ in range(stars):
        for _t in range(40):
            x, y = rnd.randint(30, W - 30), rnd.randint(30, H - 30)
            if min(x / W, 1 - x / W, y / H, 1 - y / H) < 0.205:
                break
        r = rnd.randint(9, 24)
        star(d, x, y, r, rnd.choice(pal.accents),
             rnd.randint(80, 155), rnd.uniform(.9, 1.1))

    if magnifier_corner:
        m = magnifier(int(W * .24), pal, alpha=110)
        place(base, m, magnifier_corner, .20, margin=.03, opacity=.55)

    if element:
        name, _, corner = element.partition(":")
        if name in ELEMENTS and corner in ("tl", "tr", "bl", "br"):
            place(base, ELEMENTS[name](pal, int(W * .22)), corner, .20)

    if center_clear > 0:
        # 中部正文区 alpha -> 0，向外羽化恢复。这样装饰只可能出现在四周边缘。
        import numpy as np
        a = np.array(base.getchannel("A")).astype(float)
        h, w = a.shape
        yy, xx = np.mgrid[0:h, 0:w]
        cx0, cx1 = int(W * center_clear), int(W * (1 - center_clear))
        cy0, cy1 = int(H * center_clear), int(H * (1 - center_clear))
        dx = np.maximum.reduce([cx0 - xx, xx - cx1, np.zeros_like(xx)]).astype(float)
        dy = np.maximum.reduce([cy0 - yy, yy - cy1, np.zeros_like(yy)]).astype(float)
        dist = np.maximum(dx, dy)
        fade = np.clip(dist / max(1, int(W * .06)), 0, 1)
        base.putalpha(Image.fromarray((a * fade).astype("uint8"), "L"))
    return base


def main():
    ap = argparse.ArgumentParser(description="生成一张装饰层预览（自检/取素材）")
    ap.add_argument("--tokens", help="色板 JSON；不给则用内置示例色板")
    ap.add_argument("--out", default="decor_preview.png")
    ap.add_argument("--size", default="1600x900")
    ap.add_argument("--seed", type=int, default=5)
    ap.add_argument("--stars", type=int, default=8)
    ap.add_argument("--magnifier", choices=("tl", "tr", "bl", "br"))
    ap.add_argument("--element", help="元素:角落，如 letter:br / cards3:tr")
    ap.add_argument("--center-clear", type=float, default=0.0)
    args = ap.parse_args()
    pal = Palette.from_file(args.tokens) if args.tokens else Palette()
    W, H = (int(v) for v in args.size.lower().split("x"))
    im = make_decor_layer((W, H), pal, args.seed, args.stars,
                          args.magnifier, args.element,
                          center_clear=args.center_clear)
    bg = Image.new("RGBA", (W, H), pal.bg_top + (255,))
    bg.alpha_composite(im)
    bg.convert("RGB").save(args.out)
    print("已写入 {} | 元素 {}".format(args.out, sorted(ELEMENTS)))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
