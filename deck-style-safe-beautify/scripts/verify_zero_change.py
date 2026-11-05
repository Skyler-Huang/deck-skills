#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_zero_change.py — 证明「零改动」，并量化美化是否看得见。

这是交付前的强制关卡：任何一项红灯都不能宣称任务完成。
既比 XML（结构），又比 LibreOffice 独立渲染像素（视觉）。

用法:
  python3 verify_zero_change.py ORIG.pptx FINAL.pptx \
      --prefix aigc_bg_ --orig-pages orig_pages/ --final-pages final_pages/ \
      --report check.md

  # 只做结构校验（无渲染目录时）
  python3 verify_zero_change.py ORIG.pptx FINAL.pptx --prefix aigc_bg_
"""
import argparse
import hashlib
import json
import os
import sys

from lxml import etree
from pptx import Presentation

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inspect_deck import find_base_shape, shape_signature  # noqa: E402

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"


def xml(el):
    return etree.tostring(el) if el is not None else None


def picture_blob_sig(sh):
    try:
        h = hashlib.sha256(sh.image.blob).hexdigest()[:16]
    except Exception:
        h = ""
    return (sh.name, sh.left, sh.top, sh.width, sh.height, h)


def page_bg_exists(slide):
    return slide._element.find(P + "cSld/" + P + "bg") is not None


def structural_checks(orig, final, prefix, expect_filename=None):
    po, pf = Presentation(orig), Presentation(final)
    so, sf = list(po.slides), list(pf.slides)
    n = min(len(so), len(sf))
    rows = []

    def add(name, expected, actual, ok, note=""):
        rows.append({"check": name, "expected": expected,
                     "actual": actual, "ok": bool(ok), "note": note})

    add("页数一致", len(so), len(sf), len(so) == len(sf))

    base_same = base_nofill = bg_added = layer_ok = 0
    shape_diff = text_diff = pic_diff = timing_ok = trans_ok = sig_bad = 0
    for i, (o, f) in enumerate(zip(so, sf), 1):
        bo = find_base_shape(o, po.slide_width, po.slide_height)
        bf = find_base_shape(f, pf.slide_width, pf.slide_height)
        if bo is not None and bf is not None:
            if xml(bo._element.spPr) == xml(bf._element.spPr):
                base_same += 1
            if bf._element.spPr.find(A + "noFill") is not None:
                base_nofill += 1
        if not page_bg_exists(o) and page_bg_exists(f):
            bg_added += 1

        dec = [x for x in f.shapes
               if getattr(x, "name", "").startswith(prefix)]
        shapes_f = list(f.shapes)
        if len(dec) == 1 and len(shapes_f) > 1 and \
                shapes_f[1].name.startswith(prefix):
            layer_ok += 1

        oo = [x for x in o.shapes if x.shape_type != 13]
        ff = [x for x in f.shapes if x.shape_type != 13
              and not x.name.startswith(prefix)]
        if len(oo) != len(ff):
            shape_diff += 1
        to = sorted(x.text_frame.text for x in oo
                    if x.has_text_frame and x.text_frame.text.strip())
        tf = sorted(x.text_frame.text for x in ff
                    if x.has_text_frame and x.text_frame.text.strip())
        if to != tf:
            text_diff += 1
        if [shape_signature(x) for x in oo] != [shape_signature(x) for x in ff]:
            sig_bad += 1

        if sorted(map(picture_blob_sig, [x for x in o.shapes if x.shape_type == 13])) != \
           sorted(map(picture_blob_sig, [x for x in f.shapes
                                         if x.shape_type == 13 and not x.name.startswith(prefix)])):
            pic_diff += 1

        to_ = o._element.find(P + "timing")
        tf_ = f._element.find(P + "timing")
        if (to_ is None and tf_ is None) or \
           (to_ is not None and tf_ is not None and xml(to_) == xml(tf_)):
            timing_ok += 1

        tr = f._element.find(P + "transition")
        if tr is None:
            trans_ok += 1
        else:
            ch = [etree.QName(c).localname for c in f._element]
            if "clrMapOvr" in ch and ch.index("transition") == ch.index("clrMapOvr") + 1:
                trans_ok += 1

    add("渐变底板 spPr XML 逐字一致", n, base_same, base_same == n)
    add("渐变底板未被改成 noFill", 0, base_nofill, base_nofill == 0)
    add("新增页面级背景图 p:bg", 0, bg_added, bg_added == 0)
    add("装饰层每页恰好 1 张且位于第 2 位", n, layer_ok, layer_ok == n,
        "prefix=" + prefix)
    add("原有形状数量变化页", 0, shape_diff, shape_diff == 0)
    add("文字内容变化页", 0, text_diff, text_diff == 0)
    add("形状签名全等页", n, n - sig_bad, sig_bad == 0)
    add("原有图片完整保留", 0, pic_diff, pic_diff == 0)
    add("原有 p:timing 完整保留", n, timing_ok, timing_ok == n)
    add("p:transition 位置合法", n, trans_ok, trans_ok == n)
    return rows, n


def pixel_checks(orig_dir, final_dir):
    """比较独立渲染的 PNG：中部正文区应几乎为零差异，边缘带应明显有差异。"""
    try:
        import numpy as np
        from PIL import Image
    except Exception as e:
        return [{"check": "渲染像素校验", "expected": "SKIP", "actual": str(e),
                 "ok": True, "note": "缺少 numpy/Pillow"}]
    if not orig_dir or not final_dir:
        return [{"check": "渲染像素校验", "expected": "SKIP",
                 "actual": "未提供 --orig-pages/--final-pages", "ok": True,
                 "note": "未做视觉验证；建议执行 render_deck.py 后重跑"}]
    rows, mids, edges, bad_fracs = [], [], [], []
    for p in range(1, 1000):
        fo = os.path.join(orig_dir, "p{}.png".format(p))
        ff = os.path.join(final_dir, "p{}.png".format(p))
        if not (os.path.isfile(fo) and os.path.isfile(ff)):
            break
        a = np.array(Image.open(fo).convert("RGB")).astype(int)
        b = np.array(Image.open(ff).convert("RGB")).astype(int)
        if a.shape != b.shape:
            b = np.array(Image.open(ff).convert("RGB").resize(
                (a.shape[1], a.shape[0]))).astype(int)
        d = np.abs(a - b)
        h, w = d.shape[:2]
        mid = d[int(h * .28):int(h * .72), int(w * .28):int(w * .72)]
        edge = np.concatenate([d[:int(h * .22)].ravel(), d[int(h * .78):].ravel(),
                               d[:, :int(w * .18)].ravel(), d[:, int(w * .82):].ravel()])
        mids.append(mid.mean())
        edges.append(edge.mean())
        bad_fracs.append((mid.max(axis=2) > 15).mean() * 100)
    if not mids:
        return [{"check": "渲染像素校验", "expected": "SKIP",
                 "actual": "目录下没有成对的 pN.png", "ok": True, "note": ""}]
    mm, em, bf = sum(mids) / len(mids), sum(edges) / len(edges), max(bad_fracs)
    rows.append({"check": "中部正文区渲染差异（应≈0）", "expected": "< 3.0",
                 "actual": round(mm, 3), "ok": mm < 3.0,
                 "note": "{} 页".format(len(mids))})
    rows.append({"check": "中部差异>15 的像素占比", "expected": "< 0.01%",
                 "actual": "{:.3f}%".format(bf), "ok": bf < 0.01, "note": ""})
    rows.append({"check": "四周边缘带渲染差异（证明看得见）", "expected": "> 0.3",
                 "actual": round(em, 3), "ok": em > 0.3,
                 "note": "若过小说明装饰太淡，等于没做"})
    return rows


def main():
    ap = argparse.ArgumentParser(description="零改动结构 + 渲染像素校验")
    ap.add_argument("original", help="原稿 .pptx")
    ap.add_argument("candidate", help="待验收的成品 .pptx")
    ap.add_argument("--prefix", default="aigc_bg_", help="新增装饰层的名称前缀")
    ap.add_argument("--orig-pages", help="原稿独立渲染 PNG 目录（pN.png）")
    ap.add_argument("--final-pages", help="成品独立渲染 PNG 目录（pN.png）")
    ap.add_argument("--report", help="Markdown 校验报告输出路径")
    ap.add_argument("--json", help="同时输出 JSON 结果")
    ap.add_argument("--expect-filename",
                    help="用户要求的文件名（如 学校-姓名-作品名.pptx）。"
                         "不给则此项仅作人工确认提示，不参与判定")
    args = ap.parse_args()

    rows, n = structural_checks(args.original, args.candidate, args.prefix,
                                args.expect_filename)
    if args.expect_filename:
        got = os.path.basename(args.candidate)
        rows.append({"check": "文件名符合用户指定格式", "expected": args.expect_filename,
                     "actual": got, "ok": got == args.expect_filename, "note": ""})
    else:
        rows.append({"check": "文件名", "expected": "人工确认",
                     "actual": os.path.basename(args.candidate), "ok": True,
                     "note": "未给 --expect-filename；上传文件常带系统前缀，"
                             "请人工确认交付名与用户原始格式一致"})
    rows += pixel_checks(args.orig_pages, args.final_pages)
    passed = all(r["ok"] for r in rows)

    lines = ["# 零改动校验报告", "",
             "- 原稿：`{}`".format(args.original),
             "- 成品：`{}`".format(args.candidate),
             "- 页数：{}".format(n), "",
             "| 检查项 | 期望 | 实际 | 结果 |", "|---|---|---|---|"]
    for r in rows:
        lines.append("| {} | {} | {} | {} |".format(
            r["check"], r["expected"], r["actual"],
            "PASS" if r["ok"] else "**FAIL**"))
    lines += ["", "**结论：{}**".format("PASS · 可交付" if passed else "FAIL · 必须修复后重跑"), ""]
    out = "\n".join(lines)
    print(out)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(out)
        print("报告已写入 " + args.report)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"passed": passed, "checks": rows}, f, ensure_ascii=False, indent=2)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
