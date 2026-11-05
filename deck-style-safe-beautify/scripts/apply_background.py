#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""apply_background.py — 从「原始未美化 PPT」重新装配，每页插入一张全页装饰图。

对应 SKILL.md Step 7 的硬性要求：
  * 每页恰好新增 1 张图片，命名为 <prefix><NN>；
  * 该图位于 spTree 中「第一个形状（渐变底板）之后」，即 shapes 序列 index 1；
    这样白底卡片与文字自然盖在装饰之上，装饰只从四角露出；
  * 不设置页面级 p:bg，不修改任何原有形状；
  * 永远从原稿重新装配，绝不在成品上替换 ppt/media/ 里的图片
    （多页可能共用同一个 r:embed，按页替换会连坐其它页）。

用法:
  python3 apply_background.py INPUT.pptx backgrounds/
  python3 apply_background.py INPUT.pptx backgrounds/ --out OUTPUT.pptx
  python3 apply_background.py INPUT.pptx backgrounds/ --dry-run
"""
import argparse
import json
import os
import re
import shutil
import sys

from pptx import Presentation


def collect_backgrounds(folder):
    """返回 {页码: 图片路径}。优先读 make_background.py 产出的 manifest。"""
    mf = os.path.join(folder, "background_manifest.json")
    if os.path.isfile(mf):
        with open(mf, encoding="utf-8") as f:
            data = json.load(f)
        out = {}
        for k, name in (data.get("files") or {}).items():
            p = os.path.join(folder, name)
            if os.path.isfile(p):
                out[int(k)] = p
        if out:
            return out
    out = {}
    pat = re.compile(r"(?:bg|p|page|slide)[_-]?0*(\d+)\.(?:jpg|jpeg|png|webp)$", re.I)
    for name in sorted(os.listdir(folder)):
        m = pat.match(name)
        if m:
            out[int(m.group(1))] = os.path.join(folder, name)
    return out


def set_pic_name(pic, name):
    """给新增图片一个可校验的名字（verify_zero_change.py 按前缀识别装饰层）。"""
    el = pic._element
    try:
        el.nvPicPr.cNvPr.set("name", name)
    except AttributeError:
        nodes = el.xpath("./p:nvPicPr/p:cNvPr")
        if nodes:
            nodes[0].set("name", name)


def move_behind_content(slide, pic):
    """把图片移到「第一个原有形状之后、其余所有形状之前」。"""
    sp_tree = slide.shapes._spTree
    original_shapes = list(slide.shapes)
    first = original_shapes[0]._element          # add_picture 后 [0] 仍是原渐变底板
    idx = list(sp_tree).index(first)
    el = pic._element
    sp_tree.remove(el)
    sp_tree.insert(idx + 1, el)
    return idx + 1


def main():
    ap = argparse.ArgumentParser(
        description="从原稿重新装配：每页插入 1 张全页装饰背景图（内容之下）")
    ap.add_argument("pptx", help="原始未美化的 .pptx")
    ap.add_argument("backgrounds", help="背景图目录（bg_01.jpg… 或含 background_manifest.json）")
    ap.add_argument("--out", help="输出路径；缺省原地更新，并自动保留 .orig.pptx 备份")
    ap.add_argument("--prefix", default="aigc_bg_", help="装饰层名称前缀（校验脚本按此识别）")
    ap.add_argument("--dry-run", action="store_true", help="只报告，不写文件")
    ap.add_argument("--no-backup", action="store_true", help="原地更新时不保留原稿备份")
    ap.add_argument("--allow-missing", action="store_true", help="缺背景图的页跳过而非报错")
    args = ap.parse_args()

    if not os.path.isfile(args.pptx):
        sys.exit("找不到输入 PPTX: " + args.pptx)
    if not os.path.isdir(args.backgrounds):
        sys.exit("找不到背景目录: " + args.backgrounds)
    bgs = collect_backgrounds(args.backgrounds)
    if not bgs:
        sys.exit("背景目录里没有可识别的图片（期望 bg_01.jpg / p1.png / manifest）")

    prs = Presentation(args.pptx)
    n = len(prs.slides)
    missing = [p for p in range(1, n + 1) if p not in bgs]
    if missing and not args.allow_missing:
        sys.exit("缺少这些页的背景图: {}（或用 --allow-missing 跳过）".format(missing))

    # 防重复装配：已有前缀装饰层说明输入是成品而非原稿
    for i, s in enumerate(prs.slides, 1):
        for sh in s.shapes:
            if sh.name.startswith(args.prefix):
                sys.exit("第 {} 页已存在 {} 装饰层。请从原稿重新装配，"
                         "不要在成品上替换 ppt/media/（多页可能共用同一张图）".format(i, args.prefix))

    print("原稿 {} 页 | 背景 {} 张 | 装饰层前缀 {!r}".format(n, len(bgs), args.prefix))
    if args.dry_run:
        for i in range(1, n + 1):
            print("  p{:02d} <- {}".format(i, os.path.basename(bgs.get(i, "<跳过>"))))
        print("[dry-run] 未写入任何文件")
        return 0

    done = 0
    for i, s in enumerate(prs.slides, 1):
        path = bgs.get(i)
        if not path:
            print("  跳过第 {} 页（无背景图）".format(i))
            continue
        pic = s.shapes.add_picture(path, 0, 0,
                                   width=prs.slide_width, height=prs.slide_height)
        set_pic_name(pic, "{}{:02d}".format(args.prefix, i))
        move_behind_content(s, pic)
        done += 1

    out = args.out or args.pptx
    if os.path.abspath(out) == os.path.abspath(args.pptx) and not args.no_backup:
        stem, ext = os.path.splitext(args.pptx)
        bak = stem + ".orig" + ext
        if not os.path.exists(bak):
            shutil.copy2(args.pptx, bak)
            print("已备份原稿 -> " + bak)
    if os.path.basename(out) != os.path.basename(args.pptx):
        print("警告：输出文件名与输入不一致（违反铁律 2）。"
              "交付前应改回 {}".format(os.path.basename(args.pptx)), file=sys.stderr)

    prs.save(out)
    print("完成：{}/{} 页各插入 1 张全页装饰层（shapes index 1）-> {}".format(done, n, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
