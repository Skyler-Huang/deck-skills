#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""strip_watermark.py — 处理生图产物：去右下角水印 + 把「假透明」RGB 图抠成干净 alpha。

两个实测踩过的坑：
  1) 生图工具默认在右下角压「AI生成 / 产品名」水印，贴进 PPT 就是一块脏字；
  2) 申请 transparent 背景时常返回 RGB + 浅灰白棋盘底，直接贴会出现「补丁方块」。
     必须从四边做连通域 flood-fill 抠背景，并做边缘羽化。

用法:
  # 透明元素：去水印 + 抠透明
  python3 strip_watermark.py assets/*.png --out-dir cleaned/ --cutout
  # 整张背景图：只去水印，用上方渐变像素无缝补齐（不制造透明洞）
  python3 strip_watermark.py ai_bg.png --out-dir cleaned/
  # 自检：输出右下角对比度拉伸图，人工确认残留
  python3 strip_watermark.py ai_bg.png --out-dir cleaned/ --audit
"""
import argparse
import glob
import os
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageFilter

DEFAULT_WM = (0.86, 0.91)   # 右下角水印区域起点（宽/高比例）


def fill_watermark_opaque(arr, x0, y0):
    """不透明底图：用区域上方一行的渐变像素按列向下拉伸填补，保持渐变连续。"""
    h, w = arr.shape[:2]
    x0 = max(0, min(int(w * x0), w - 1))
    y0 = max(0, min(int(h * y0), h - 1))
    if y0 == 0:
        return arr
    src = arr[y0 - 1:y0, x0:w, :].astype(float)          # 1×W×3
    arr[y0:h, x0:w, :] = np.repeat(src, h - y0, axis=0)
    return arr


def flood_fill_alpha(arr, tol=38, feather=1.0, denoise=True):
    """从四边对「接近背景色」的像素做连通域 flood-fill，输出柔化 alpha。

    只删与边缘连通的背景，主体内部的浅色区域（如白纸卡片）会被保留。
    """
    h, w = arr.shape[:2]
    corners = np.array([arr[1, 1], arr[1, w - 2], arr[h - 2, 1],
                        arr[h - 2, w - 2], arr[1, w // 2], arr[h // 2, 1]], float)
    bg = np.median(corners, axis=0)
    dist = np.linalg.norm(arr.astype(float) - bg, axis=2)
    cand = dist < tol

    visited = np.zeros((h, w), dtype=bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if cand[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if cand[y, x] and not visited[y, x]:
                visited[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and cand[ny, nx]:
                visited[ny, nx] = True
                q.append((ny, nx))

    # 越接近背景色越透明，柔化纸纹/抗锯齿过渡
    soft = np.clip((dist - tol * 0.45) / (tol * 0.7), 0, 1)
    a = np.where(visited, 0.0, 1.0) * (0.25 + 0.75 * soft)
    alpha = Image.fromarray((np.clip(a, 0, 1) * 255).astype("uint8"), "L")
    if denoise:
        # 开运算：去掉孤立白噪点，再轻微羽化
        alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
    if feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(feather))
    return alpha


def process(path, out_dir, args):
    im = Image.open(path).convert("RGB")
    arr = np.array(im).astype(np.uint8)
    h, w = arr.shape[:2]
    name = os.path.splitext(os.path.basename(path))[0]
    wm_x, wm_y = (float(v) for v in args.wm.split(","))

    if args.audit:
        strip = arr[int(h * wm_y):, int(w * wm_x):, :].astype(float)
        lo, hi = strip.min(), strip.max()
        boosted = ((strip - lo) / max(1.0, hi - lo) * 255).astype("uint8")
        ap = os.path.join(out_dir, "_audit")
        os.makedirs(ap, exist_ok=True)
        ap = os.path.join(ap, name + ".audit.png")
        Image.fromarray(boosted).resize(
            (max(1, boosted.shape[1] * 2), max(1, boosted.shape[0] * 2)),
            Image.LANCZOS).save(ap)
        print("  audit -> " + ap)

    if not args.no_wm:
        if args.cutout:
            pass                      # alpha 阶段统一清透明
        else:
            arr = fill_watermark_opaque(arr, wm_x, wm_y)

    if args.cutout:
        alpha = flood_fill_alpha(arr, args.tol, args.feather, not args.no_denoise)
        if not args.no_wm:
            # 右下角水印整块清透明（装饰主体一般不在此角落）
            a = np.array(alpha)
            a[int(h * wm_y):, int(w * wm_x):] = 0
            alpha = Image.fromarray(a, "L")
        rgba = np.dstack([arr, np.array(alpha)])
        out = Image.fromarray(rgba, "RGBA")
        bbox = alpha.point(lambda v: 255 if v > 12 else 0).getbbox()
        if bbox and not args.keep_canvas:
            out = out.crop(bbox)
        dst = os.path.join(out_dir, name + ".png")
        out.save(dst, optimize=True)
    else:
        out = Image.fromarray(arr, "RGB")
        if args.format == "jpg":
            dst = os.path.join(out_dir, name + ".jpg")
            out.save(dst, quality=args.quality, optimize=True)
        else:
            dst = os.path.join(out_dir, name + ".png")
            out.save(dst, optimize=True)
    return dst


def main():
    ap = argparse.ArgumentParser(description="生图产物后处理：去水印 + flood-fill 抠透明")
    ap.add_argument("inputs", nargs="+", help="图片文件或目录或 glob")
    ap.add_argument("--out-dir", required=True, help="输出目录")
    ap.add_argument("--cutout", action="store_true", help="抠成透明 PNG（用于贴片元素）")
    ap.add_argument("--tol", type=float, default=38, help="背景色距离阈值")
    ap.add_argument("--feather", type=float, default=1.0, help="alpha 羽化半径")
    ap.add_argument("--no-denoise", action="store_true", help="关闭孤立噪点清理")
    ap.add_argument("--keep-canvas", action="store_true", help="抠图后不裁剪到主体包围盒")
    ap.add_argument("--no-wm", action="store_true", help="不做水印处理")
    ap.add_argument("--wm", default="{},{}".format(*DEFAULT_WM),
                    help="右下角水印区域起点比例，默认 0.86,0.91")
    ap.add_argument("--format", choices=("png", "jpg"), default="png",
                    help="不抠透明时的输出格式")
    ap.add_argument("--quality", type=int, default=88)
    ap.add_argument("--audit", action="store_true",
                    help="额外输出右下角对比度拉伸自检图（正常观看不可见的残痕会显形）")
    args = ap.parse_args()

    files = []
    for raw in args.inputs:
        if os.path.isdir(raw):
            files += [os.path.join(raw, f) for f in sorted(os.listdir(raw))
                      if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
        else:
            files += sorted(glob.glob(raw))
    files = [f for f in dict.fromkeys(files) if os.path.isfile(f)]
    if not files:
        sys.exit("没有找到输入图片")
    os.makedirs(args.out_dir, exist_ok=True)

    for f in files:
        try:
            dst = process(f, args.out_dir, args)
            print("  {} -> {}".format(os.path.basename(f), dst))
        except Exception as e:
            print("  跳过 {} : {}".format(os.path.basename(f), e), file=sys.stderr)
    print("完成 {} 张 | cutout={} | 水印区={}".format(len(files), args.cutout, args.wm))
    return 0


if __name__ == "__main__":
    sys.exit(main())
