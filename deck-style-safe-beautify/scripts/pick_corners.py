#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pick_corners.py — 从原稿真实渲染图逐页计算「四角拥挤度」，挑最空的角落放装饰。

教训：固定角落必然翻车。有的页左下角有页码和线稿，有的页横跨整页的标题框
用 bbox 会被误判成"满"。只有基于真实渲染像素、按页计算才可靠。

原理：用每行左右边缘 / 每列上下边缘的中位色拟合背景渐变，逐像素求与背景
的色差；色差大的像素视为「已有卡片或文字」。再统计四角候选区里这类像素
的占比，占比最低者最空。

用法:
  python3 pick_corners.py --pages orig_pages/ --out corners.json
  python3 pick_corners.py --pages orig_pages/ --avoid bl --report corners.md
"""
import argparse
import glob
import json
import os
import re
import sys

import numpy as np
from PIL import Image

CORNERS = ("tl", "tr", "bl", "br")
LABEL = {"tl": "左上", "tr": "右上", "bl": "左下", "br": "右下"}


def content_mask(path, threshold=30):
    im = np.array(Image.open(path).convert("RGB")).astype(np.int16)
    h, w = im.shape[:2]
    band = max(2, int(min(h, w) * 0.03))
    row_bg = np.median(np.concatenate([im[:, :band], im[:, -band:]], axis=1),
                       axis=1)                                  # (h,3)
    col_bg = np.median(np.concatenate([im[:band, :], im[-band:, :]], axis=0),
                       axis=0)                                  # (w,3)
    bg = (row_bg[:, None, :] + col_bg[None, :, :]) / 2.0
    diff = np.abs(im - bg).max(axis=2)
    return diff > threshold


def corner_scores(mask, fw=0.28, fh=0.32):
    h, w = mask.shape[:2]
    cw, ch = int(w * fw), int(h * fh)
    boxes = {
        "tl": (0, 0, cw, ch),
        "tr": (w - cw, 0, w, ch),
        "bl": (0, h - ch, cw, h),
        "br": (w - cw, h - ch, w, h),
    }
    return {k: round(float(mask[y0:y1, x0:x1].mean()), 5)
            for k, (x0, y0, x1, y1) in boxes.items()}


def page_number(path):
    m = re.search(r"p(\d+)\.png$", os.path.basename(path))
    return int(m.group(1)) if m else 0


def main():
    ap = argparse.ArgumentParser(description="按渲染像素拥挤度逐页挑选最空角落")
    ap.add_argument("--pages", required=True, help="原稿渲染 PNG 目录（pN.png）")
    ap.add_argument("--out", help="结果 JSON 输出路径")
    ap.add_argument("--report", help="人类可读 Markdown 报告")
    ap.add_argument("--avoid", default="", help="禁止使用的角落，逗号分隔，如 bl,br")
    ap.add_argument("--threshold", type=int, default=30, help="背景色差阈值（默认 30）")
    ap.add_argument("--fw", type=float, default=0.28, help="角落候选区宽度占比")
    ap.add_argument("--fh", type=float, default=0.32, help="角落候选区高度占比")
    args = ap.parse_args()

    files = sorted((f for f in glob.glob(os.path.join(args.pages, "p*.png"))
                    if page_number(f) > 0), key=page_number)
    if not files:
        print("目录下没有 pN.png: " + args.pages, file=sys.stderr)
        return 2
    avoid = {x.strip() for x in args.avoid.split(",") if x.strip() in CORNERS}

    results, winners = [], []
    for f in files:
        mask = content_mask(f, args.threshold)
        scores = corner_scores(mask, args.fw, args.fh)
        cands = [k for k in CORNERS if k not in avoid]
        best = min(cands, key=lambda k: scores[k])
        results.append({"page": page_number(f), "scores": scores, "best": best,
                        "runner_up": sorted(cands, key=lambda k: scores[k])[1]})
        winners.append(best)

    counts = {k: winners.count(k) for k in CORNERS}
    summary = {"pages": len(results),
               "global_emptiest": max(CORNERS, key=lambda k: counts[k]),
               "winner_counts": counts,
               "avoid": sorted(avoid),
               "results": results}
    text = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print("已写入 " + args.out)
    else:
        print(text)

    if args.report:
        lines = ["# 角落拥挤度报告", "",
                 "数值越小表示该角落已有卡片/文字越少，越适合放装饰。", "",
                 "| 页 | 左上 | 右上 | 左下 | 右下 | 推荐 |", "|---|---|---|---|---|---|"]
        for r in results:
            s = r["scores"]
            lines.append("| {} | {:.4f} | {:.4f} | {:.4f} | {:.4f} | **{}** |".format(
                r["page"], s["tl"], s["tr"], s["bl"], s["br"], LABEL[r["best"]]))
        lines += ["", "全稿统计：{}；最常最空的角落：**{}**".format(
            "，".join("{}={}".format(LABEL[k], counts[k]) for k in CORNERS),
            LABEL[summary["global_emptiest"]]), ""]
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        print("报告已写入 " + args.report)
    print("共 {} 页；最常最空角落 {}；统计 {}".format(
        len(results), LABEL[summary["global_emptiest"]], counts), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
