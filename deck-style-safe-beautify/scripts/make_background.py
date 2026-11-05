#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_background.py — 精确还原原稿渐变底色，再叠「只看得见装饰」的图层。

风格锁定的核心：底色由代码按 inspect_deck.py 提取的色值逐像素生成，
AI 生成图只允许贡献高通后的装饰纹理，绝不让它整张替换背景（色值必漂）。

中部保护：所有装饰在合成前乘以 center-fade 掩码，中部正文区装饰强度为 0，
向外羽化恢复。这从数学上保证「正文零干扰」。

用法:
  # 先拿色板
  python3 inspect_deck.py deck.pptx --tokens color-tokens.json
  # 再生成 20 页背景
  python3 make_background.py --tokens color-tokens.json --pages 20 \
      --plan plan.json --out backgrounds/
  # 允许生图时，叠一层同风格 AI 装饰纹理
  python3 make_background.py --tokens color-tokens.json --pages 20 \
      --overlay ai_bg.png --overlay-strength 0.8 --out backgrounds/
"""
import argparse
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from decor_recipe import Palette, ELEMENTS, place, make_decor_layer  # noqa: E402


def gradient(size, pal):
    """按色板生成精确线性渐变。angle_deg: 90=上到下, 0=左到右。"""
    W, H = size
    top = np.array(pal.bg_top, dtype=float)
    bot = np.array(pal.bg_bottom, dtype=float)
    ang = math.radians((pal.raw.get("background") or {}).get("angle_deg") or 90)
    yy, xx = np.mgrid[0:H, 0:W].astype(float)
    if abs(math.sin(ang)) < 1e-6:      # 水平
        t = xx / max(1, W - 1)
    else:                              # 竖直（含斜向投影）
        dx, dy = math.cos(ang), abs(math.sin(ang))
        denom = W * abs(dx) + H * dy
        t = (xx * abs(dx) + yy * dy) / max(1.0, denom)
        if ang < 0 or ang > math.pi:
            t = 1 - t
    t = np.clip(t, 0, 1)[:, :, None]
    arr = top[None, None, :] * (1 - t) + bot[None, None, :] * t
    return np.clip(arr, 0, 255).astype(np.uint8)


def center_fade(shape, clear=0.22, feather=0.06):
    """中部为 0、边缘为 1 的掩码，用于压制中部装饰。"""
    h, w = shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    x0, x1 = int(w * clear), int(w * (1 - clear))
    y0, y1 = int(h * clear), int(h * (1 - clear))
    dx = np.maximum.reduce([x0 - xx, xx - x1, np.zeros_like(xx)]).astype(float)
    dy = np.maximum.reduce([y0 - yy, yy - y1, np.zeros_like(yy)]).astype(float)
    d = np.maximum(dx, dy)
    return np.clip(d / max(1, int(w * feather)), 0, 1)[:, :, None]


def overlay_delta(path, size, strength=0.8):
    """高通提取 AI 图的装饰纹理，丢弃其整体色调（防止风格漂移）。"""
    im = Image.open(path).convert("RGB").resize(size, Image.LANCZOS)
    arr = np.array(im).astype(float)
    blur = np.array(im.filter(ImageFilter.GaussianBlur(radius=22))).astype(float)
    delta = np.clip(arr - blur, -70, 70)
    return delta * strength


def element_layer(size, pal, spec, seed):
    layer = make_decor_layer(
        size, pal, seed=seed,
        stars=spec.get("stars", 7),
        magnifier_corner=spec.get("magnifier"),
        dot=spec.get("dot", True),
    )
    el, corner = spec.get("element"), spec.get("corner")
    if el and corner and el in ELEMENTS:
        elem = ELEMENTS[el](pal, int(size[0] * .22))
        place(layer, elem, corner, spec.get("size", .20),
              margin=spec.get("margin", .055),
              opacity=spec.get("opacity", .72))
    return layer


def main():
    ap = argparse.ArgumentParser(description="生成精确渐变 + 同风格装饰的逐页背景")
    ap.add_argument("--tokens", required=True, help="色板 JSON（inspect_deck.py --tokens 产出）")
    ap.add_argument("--out", required=True, help="输出目录")
    ap.add_argument("--pages", type=int, default=1, help="要生成的页数")
    ap.add_argument("--size", default="1600x900", help="像素尺寸（保持与原稿相同宽高比）")
    ap.add_argument("--plan", help="逐页装饰 JSON：{\"1\": {\"element\":\"mag\",...}}")
    ap.add_argument("--overlay", help="可选：AI 生成的同风格装饰底图（只取高通纹理）")
    ap.add_argument("--overlay-strength", type=float, default=0.8)
    ap.add_argument("--center-clear", type=float, default=0.22,
                    help="中部保护比例，0 关闭；建议 0.20~0.25")
    ap.add_argument("--seed", type=int, default=137)
    ap.add_argument("--format", choices=("jpg", "png"), default="jpg")
    ap.add_argument("--quality", type=int, default=88)
    args = ap.parse_args()

    pal = Palette.from_file(args.tokens)
    size = tuple(int(v) for v in args.size.lower().split("x"))
    os.makedirs(args.out, exist_ok=True)
    plan = {}
    if args.plan and os.path.isfile(args.plan):
        with open(args.plan, encoding="utf-8") as f:
            plan = json.load(f)

    base = gradient(size, pal).astype(float)
    fade = center_fade(base.shape, args.center_clear) if args.center_clear > 0 else 1.0
    delta = overlay_delta(args.overlay, size, args.overlay_strength) if args.overlay else None

    manifest = {"tokens": os.path.abspath(args.tokens), "size": list(size),
                "pages": args.pages, "center_clear": args.center_clear,
                "overlay": os.path.basename(args.overlay) if args.overlay else None,
                "files": {}}
    for p in range(1, args.pages + 1):
        arr = base.copy()
        if delta is not None:
            arr = arr + delta * fade
        rgb = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGB").convert("RGBA")

        spec = plan.get(str(p), plan.get(p, {}))
        dec = element_layer(size, pal, spec, args.seed * p + p)
        if args.center_clear > 0:
            a = np.array(dec.getchannel("A")).astype(float)
            dec.putalpha(Image.fromarray((a * fade[:, :, 0]).astype("uint8"), "L"))
        rgb.alpha_composite(dec)

        name = "bg_{:02d}.{}".format(p, args.format)
        path = os.path.join(args.out, name)
        out = rgb.convert("RGB")
        if args.format == "jpg":
            out.save(path, quality=args.quality, optimize=True)
        else:
            out.save(path, optimize=True)
        manifest["files"][str(p)] = name

    with open(os.path.join(args.out, "background_manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("已生成 {} 页 -> {} | 渐变 {} -> {} | 中部保护 {}".format(
        args.pages, args.out, pal.bg_top, pal.bg_bottom, args.center_clear))
    return 0


if __name__ == "__main__":
    sys.exit(main())
