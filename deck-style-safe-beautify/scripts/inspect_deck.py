#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""inspect_deck.py — 解析一份 .pptx，输出结构、色板、渐变与文本清单。

这是「风格锁定」的第一步：所有后续绘制都必须从这里提取的色值取值，
禁止凭肉眼猜配色。输出 JSON 可直接被 make_background.py / decor_recipe.py 消费。

用法:
  python3 inspect_deck.py deck.pptx --out inspect.json
  python3 inspect_deck.py deck.pptx --tokens color-tokens.json --pretty
"""
import argparse
import collections
import json
import os
import sys

from lxml import etree
from pptx import Presentation
from pptx.util import Emu

A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"


def emu_in(v):
    return round(Emu(v).inches, 4) if v is not None else None


def find_base_shape(slide, slide_w, slide_h):
    """找出全页尺寸的渐变底板形状；找不到则退回第一个形状。"""
    shapes = list(slide.shapes)
    if not shapes:
        return None
    for sh in shapes:
        try:
            covers = (sh.width >= slide_w * 0.95 and sh.height >= slide_h * 0.95)
        except Exception:
            covers = False
        if covers and sh._element.spPr.find(".//" + A + "gradFill") is not None:
            return sh
    return shapes[0]


def gradient_of(sh):
    """返回 [{'pos':..,'color':'RRGGBB'}, ...] 与角度。"""
    if sh is None:
        return None
    sp = sh._element.spPr
    grad = sp.find(".//" + A + "gradFill")
    if grad is None:
        return None
    stops = []
    for gs in grad.findall(".//" + A + "gs"):
        c = gs.find(A + "srgbClr")
        if c is not None:
            stops.append({"pos": int(gs.get("pos", 0)) / 1000.0,
                          "color": c.get("val")})
        else:
            scheme = gs.find(A + "schemeClr")
            if scheme is not None:
                stops.append({"pos": int(gs.get("pos", 0)) / 1000.0,
                              "color": "scheme:" + str(scheme.get("val"))})
    lin = grad.find(".//" + A + "lin")
    return {"stops": stops,
            "angle_deg": (int(lin.get("ang", 0)) / 60000.0) if lin is not None else None,
            "scaled": lin.get("scaled") if lin is not None else None}


def shape_signature(sh):
    """形状签名：位置/尺寸/旋转/渐变/纯色/透明度/文字。用于零改动比对。"""
    try:
        rot = round(sh.rotation, 3)
    except Exception:
        rot = 0
    sp = sh._element.spPr
    grad = [e.get("val") for e in sp.findall(".//" + A + "gradFill//" + A + "srgbClr")]
    solid = sp.find(".//" + A + "solidFill/" + A + "srgbClr")
    alpha = sp.find(".//" + A + "solidFill/" + A + "srgbClr/" + A + "alpha")
    ln = sp.find(".//" + A + "ln/" + A + "solidFill/" + A + "srgbClr")
    xfrm = sp.find(A + "xfrm")
    return {
        "left": emu_in(sh.left), "top": emu_in(sh.top),
        "width": emu_in(sh.width), "height": emu_in(sh.height),
        "rotation": rot,
        "flipH": xfrm.get("flipH") if xfrm is not None else None,
        "flipV": xfrm.get("flipV") if xfrm is not None else None,
        "gradient": grad,
        "solid": solid.get("val") if solid is not None else None,
        "alpha": alpha.get("val") if alpha is not None else None,
        "line": ln.get("val") if ln is not None else None,
        "text": sh.text_frame.text if sh.has_text_frame else "",
    }


def inspect(path):
    prs = Presentation(path)
    sw, sh_ = prs.slide_width, prs.slide_height
    palette = collections.Counter()
    slides = []
    timing_pages, transition_pages = [], []

    for i, slide in enumerate(prs.slides, 1):
        sx = slide._element
        if sx.find(P + "timing") is not None:
            timing_pages.append(i)
        if sx.find(P + "transition") is not None:
            transition_pages.append(i)

        for e in sx.iter():
            if etree.QName(e).localname == "srgbClr" and e.get("val"):
                palette[e.get("val").upper()] += 1

        texts, pics = [], []
        for s in slide.shapes:
            if s.has_text_frame and s.text_frame.text.strip():
                texts.append(s.text_frame.text.strip().replace("\n", " / "))
            if s.shape_type == 13:  # PICTURE
                pics.append({"name": s.name,
                             "left": emu_in(s.left), "top": emu_in(s.top),
                             "width": emu_in(s.width), "height": emu_in(s.height),
                             "size_px": list(s.image.size) if s.image else None})

        slides.append({
            "index": i,
            "shape_count": len(slide.shapes),
            "texts": texts,
            "pictures": pics,
            "has_page_bg": sx.find(P + "cSld/" + P + "bg") is not None,
        })

    base = find_base_shape(prs.slides[0], sw, sh_)
    grad = gradient_of(base)
    top_colors = [{"color": c, "count": n} for c, n in palette.most_common(24)]

    return {
        "source": os.path.abspath(path),
        "filename": os.path.basename(path),
        "slide_count": len(slides),
        "slide_size_in": {"w": emu_in(sw), "h": emu_in(sh_)},
        "base_shape": {"name": base.name if base is not None else None,
                       "gradient": grad} if base is not None else None,
        "palette": top_colors,
        "timing_pages": timing_pages,
        "transition_pages": transition_pages,
        "slides": slides,
    }


def build_tokens(data):
    """从解析结果生成色板令牌，供绘制脚本使用。

    accents 的排序很关键：按「出现频次」排会把墨蓝/深灰顶到前面，
    直接用会把四角星画成暗色。这里把已知的品牌亮色（黄/粉/青/绿/橙）
    按固定顺序提前，其余按色度补充，并剔除底色与 ink。
    """
    import colorsys
    grad = (data.get("base_shape") or {}).get("gradient") or {}
    stops = [s for s in grad.get("stops", []) if not str(s["color"]).startswith("scheme:")]
    bg_top = stops[0]["color"] if stops else "BFE9FF"
    bg_bottom = stops[-1]["color"] if len(stops) > 1 else "FFFDF0"
    palette = [x["color"] for x in data.get("palette", [])]
    ink = next((c for c in palette if c.upper() in
                {"17384D", "3F6478", "1B3A4B"}), "17384D")
    exclude = {bg_top.upper(), bg_bottom.upper(), "FFFFFF", "000000", ink.upper()}

    def chroma(c):
        r, g, b = (int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        _h, s, v = colorsys.rgb_to_hsv(r, g, b)
        return s * min(v, 1.0) * (0.6 + 0.4 * v)

    brand = ["FFD23F", "FF5D8F", "2EC4E6", "7BD389", "FF6B35", "A06CD5", "FFB703"]
    present = {c.upper() for c in palette}
    accents = [c for c in brand if c in present]
    rest = sorted((c for c in palette if c.upper() not in exclude
                   and c.upper() not in {x.upper() for x in accents}),
                  key=lambda c: -chroma(c))
    accents = (accents + [c for c in rest if chroma(c) > 0.12])[:6]
    return {
        "background": {"type": "linear-gradient", "top": bg_top, "bottom": bg_bottom,
                       "angle_deg": grad.get("angle_deg")},
        "ink": ink,
        "accents": accents or ["FFD23F", "FF5D8F", "2EC4E6", "7BD389"],
        "source_palette": palette,
        "note": "Generated by inspect_deck.py. accents are ordered for decoration "
                "(brand bright colors first). Review before use; do not invent new colors.",
    }


def main():
    ap = argparse.ArgumentParser(description="解析 PPTX 并输出结构/色板/渐变 JSON")
    ap.add_argument("pptx", help="输入 .pptx 路径")
    ap.add_argument("--out", help="完整解析结果 JSON 输出路径")
    ap.add_argument("--tokens", help="额外输出色板令牌 JSON（供 make_background.py 使用）")
    ap.add_argument("--pretty", action="store_true", help="缩进输出")
    args = ap.parse_args()

    if not os.path.isfile(args.pptx):
        print("找不到文件: " + args.pptx, file=sys.stderr)
        return 2
    data = inspect(args.pptx)
    kw = {"ensure_ascii": False, "indent": 2 if args.pretty else None}
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(data, f, **kw)
        print("已写入 " + args.out)
    if args.tokens:
        tok = build_tokens(data)
        with open(args.tokens, "w", encoding="utf-8") as f:
            json.dump(tok, f, **kw)
        print("已写入 " + args.tokens)
    if not args.out and not args.tokens:
        print(json.dumps(data, **kw))
    print("页数 {} | 尺寸 {}in | 渐变 {} | 已有动画页 {}/{}".format(
        data["slide_count"], data["slide_size_in"],
        (data.get("base_shape") or {}).get("gradient", {}).get("stops"),
        len(data["timing_pages"]), data["slide_count"]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
