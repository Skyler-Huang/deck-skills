#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inject_transitions.py — 注入克制的切换动效，完整保留原稿 p:timing。

铁律：只加「切换」（p:transition），绝不碰「进入动画」（p:timing）。
手写动画 XML 极易让 PowerPoint 提示「需要修复」，因此本脚本：
  * 不生成任何 p:timing 节点；
  * 若原稿已有 p:timing，原样保留其字节；
  * 若原稿已有 p:transition，默认跳过该页（--force 才替换）；
  * p:transition 严格插在 clrMapOvr 之后、timing 之前（CT_Slide 子元素顺序）。

效果基调：全页柔和淡入；仅章节入口页用推近（呼应「放大镜看清楚」的叙事）。
无声音、不改放映方式、不改换片时间。

用法:
  python3 inject_transitions.py deck.pptx --preset gentle --chapter-zoom 3,7,10,14,18
  python3 inject_transitions.py deck.pptx --preset fade
  python3 inject_transitions.py deck.pptx --remove        # 回滚，只删本类 transition
  python3 inject_transitions.py deck.pptx --dry-run
"""
import argparse
import os
import re
import shutil
import sys
import zipfile

from lxml import etree

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
NS = {"p": P}


def q(tag):
    return "{%s}%s" % (P, tag)


def make_transition(kind, speed):
    """kind: fade | zoom | push | wipe | none"""
    tr = etree.Element(q("transition"), nsmap={"p": P})
    tr.set("spd", speed)
    tr.set("advClick", "1")
    if kind == "zoom":
        etree.SubElement(tr, q("zoom")).set("dir", "in")
    elif kind == "wipe":
        etree.SubElement(tr, q("wipe")).set("dir", "d")
    elif kind == "push":
        etree.SubElement(tr, q("push")).set("dir", "u")
    elif kind == "none":
        return None
    else:
        etree.SubElement(tr, q("fade"))
    return tr


def insert_after_clrmapovr(root, node):
    """CT_Slide 顺序: cSld, clrMapOvr?, transition?, timing?, extLst?"""
    for tag in ("clrMapOvr", "cSld"):
        anchor = root.find(q(tag))
        if anchor is not None:
            root.insert(list(root).index(anchor) + 1, node)
            return True
    root.append(node)
    return True


def parse_pages(spec, n):
    if not spec:
        return set()
    out = set()
    for part in re.split(r"[,\s]+", spec.strip()):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return {p for p in out if 1 <= p <= n}


def main():
    ap = argparse.ArgumentParser(description="注入/移除克制的 PPT 切换动效（不改 p:timing）")
    ap.add_argument("pptx", help="输入 .pptx")
    ap.add_argument("--out", help="输出路径；缺省原地更新（自动备份 .orig.pptx）")
    ap.add_argument("--preset", choices=("gentle", "fade", "zoom", "none"),
                    default="gentle", help="gentle=淡入+章节推近；none=不注入")
    ap.add_argument("--chapter-zoom", default="",
                    help="使用推近的页码，如 3,7,10,14,18 或 3-5")
    ap.add_argument("--speed", choices=("slow", "med", "fast"), default="slow")
    ap.add_argument("--force", action="store_true", help="替换已存在的 p:transition")
    ap.add_argument("--remove", action="store_true", help="移除所有 p:transition 后写回")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    if not os.path.isfile(args.pptx):
        sys.exit("找不到文件: " + args.pptx)
    with zipfile.ZipFile(args.pptx) as z:
        # 必须一次性读进内存：原地写回时不能边读边写同一个 zip（会截断源文件）
        infos = z.infolist()
        blobs = {i.filename: z.read(i.filename) for i in infos}
        names = [n for n in blobs
                 if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)]
        names.sort(key=lambda s: int(re.search(r"slide(\d+)", s).group(1)))
    if not names:
        sys.exit("未找到 ppt/slides/slideN.xml")

    zoom_pages = parse_pages(args.chapter_zoom, len(names))
    stats = {"fade": 0, "zoom": 0, "skipped": 0, "removed": 0, "timing_kept": 0}
    changed = {}

    for n in names:
        idx = int(re.search(r"slide(\d+)", n).group(1))
        root = etree.fromstring(blobs[n])
        old = root.find(q("transition"))
        timing_before = etree.tostring(root.find(q("timing"))) if root.find(q("timing")) is not None else None

        if args.remove:
            if old is not None:
                root.remove(old)
                stats["removed"] += 1
                changed[n] = etree.tostring(root, xml_declaration=True,
                                            encoding="UTF-8", standalone=True)
            t_after = etree.tostring(root.find(q("timing"))) if root.find(q("timing")) is not None else None
            if timing_before == t_after:
                stats["timing_kept"] += 1
            continue

        if args.preset == "none":
            continue
        if old is not None and not args.force:
            stats["skipped"] += 1
            continue
        if old is not None:
            root.remove(old)

        kind = "zoom" if (args.preset == "zoom" or idx in zoom_pages) else "fade"
        node = make_transition(kind, args.speed)
        if node is not None:
            insert_after_clrmapovr(root, node)
            stats[kind] += 1
        timing_after = etree.tostring(root.find(q("timing"))) if root.find(q("timing")) is not None else None
        if timing_before == timing_after:
            stats["timing_kept"] += 1
        changed[n] = etree.tostring(root, xml_declaration=True,
                                    encoding="UTF-8", standalone=True)

    print("页数 {} | 淡入 {} | 推近 {} | 跳过(已有transition) {} | 移除 {} | "
          "p:timing 未变 {}".format(len(names), stats["fade"], stats["zoom"],
                                    stats["skipped"], stats["removed"],
                                    stats["timing_kept"]))
    if args.dry_run:
        print("[dry-run] 未写入任何文件")
        return 0
    if not changed:
        print("没有需要写入的改动")
        return 0

    out = args.out or args.pptx
    if os.path.abspath(out) == os.path.abspath(args.pptx) and not args.no_backup:
        stem, ext = os.path.splitext(args.pptx)
        bak = stem + ".orig" + ext
        if not os.path.exists(bak):
            shutil.copy2(args.pptx, bak)
            print("已备份 -> " + bak)

    tmp = out + ".tmp"
    with zipfile.ZipFile(tmp, "w") as zout:
        for info in infos:
            zout.writestr(info, changed.get(info.filename, blobs[info.filename]))
    os.replace(tmp, out)
    print("已写入 " + out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
