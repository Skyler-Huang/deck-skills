#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_pptx — static readability / layout audit for a .pptx deck.

Checks, per slide:
  font        any run below --hard-min (error); long body text below --body-min (warn)
  overflow    text height/width vs its box, measured with real font metrics
  overlap     collisions between the *ink* rectangles of text, not their frames
  edge        text ink closer than --edge px to the slide edge; shapes off-canvas
  contrast    estimated WCAG ratio of run colour vs the fill behind it
  emoji       emoji in slide text
  motion      entrance-effect count and estimated duration
  flat        a picture covering most of the slide (not editable)
  notes       missing speaker notes (info)

Why ink rectangles: PowerPoint text boxes are usually much taller than their text,
so frame-vs-frame overlap reports collisions that do not exist on screen. This
script estimates the painted area from font metrics, alignment and vertical anchor.

Usage:
  python audit_pptx.py deck.pptx
  python audit_pptx.py deck.pptx --json report.json --out report.txt
  python audit_pptx.py deck.pptx --min-body 18 --hard-min 13

Exit code 1 when at least one error-level issue is found, else 0.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from collections import Counter

from PIL import ImageFont
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.oxml.ns import qn

EMU_PX = 9525.0
DEFAULT_SIZE = 18.0
DEFAULT_FONT = "微软雅黑"

# family -> candidate file names (first hit wins)
FONT_FILENAMES = {
    "幼圆": ["SIMYOU.TTF", "YouYuan.ttf", "youyuan.ttf"],
    "YouYuan": ["SIMYOU.TTF", "YouYuan.ttf"],
    "微软雅黑": ["msyh.ttc", "msyh.ttf", "MicrosoftYaHei.ttf"],
    "Microsoft YaHei": ["msyh.ttc", "msyh.ttf"],
    "Microsoft YaHei UI": ["msyh.ttc", "msyh.ttf"],
    "宋体": ["simsun.ttc", "simsun.ttf"],
    "SimSun": ["simsun.ttc", "simsun.ttf"],
    "等线": ["Deng.ttf", "DengXian.ttf"],
    "DengXian": ["Deng.ttf"],
    "楷体": ["simkai.ttf"],
    "KaiTi": ["simkai.ttf"],
    "Consolas": ["consola.ttf", "Consolas.ttf"],
    "Georgia": ["georgia.ttf", "Georgia.ttf"],
    "Arial": ["arial.ttf", "Arial.ttf"],
    "Times New Roman": ["times.ttf", "Times New Roman.ttf"],
    "PingFang SC": ["PingFang.ttc"],
    "Noto Sans CJK SC": ["NotoSansCJK-Regular.ttc", "NotoSansCJKsc-Regular.otf"],
    "Source Han Sans SC": ["SourceHanSansSC-Regular.otf", "SourceHanSansCN-Regular.otf"],
}
FALLBACK_FAMILIES = ["微软雅黑", "Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", "Arial"]
# pictographic only: arrows (2190-21FF) and symbols such as ✓ are legitimate in a deck
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U0001F000-\U0001F0FF\U0001F900-\U0001F9FF\uFE0F]"
)

EXTRA_FONT_DIRS = []
MISSING_FONTS = set()
_font_cache = {}
_path_cache = {}


def font_dirs():
    dirs = []
    env = os.environ.get("DECK_FONT_DIRS", "")
    if env:
        dirs.extend(p for p in env.split(os.pathsep) if p)
    if sys.platform.startswith("win"):
        dirs.append(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"))
    elif sys.platform == "darwin":
        dirs.extend(["/System/Library/Fonts", "/Library/Fonts",
                     os.path.expanduser("~/Library/Fonts")])
    else:
        dirs.extend(["/usr/share/fonts", "/usr/local/share/fonts",
                     os.path.expanduser("~/.fonts"),
                     os.path.expanduser("~/.local/share/fonts")])
    dirs.extend(EXTRA_FONT_DIRS)
    return [d for d in dict.fromkeys(dirs) if os.path.isdir(d)]


def find_font_file(family):
    if family in _path_cache:
        return _path_cache[family]
    names = FONT_FILENAMES.get(family or "", [])
    found = None
    for d in font_dirs():
        for fn in names:
            p = os.path.join(d, fn)
            if os.path.isfile(p):
                found = p
                break
        if found:
            break
    if not found and names:
        for d in font_dirs():
            for root, _dirs, files in os.walk(d):
                hit = next((f for f in files if f in names), None)
                if hit:
                    found = os.path.join(root, hit)
                    break
            if found:
                break
    _path_cache[family] = found
    return found


def fallback_file():
    for fam in FALLBACK_FAMILIES:
        p = find_font_file(fam)
        if p:
            return p
    return None


def font_for(name, px_size):
    key = (name or "", int(round(px_size)))
    if key in _font_cache:
        return _font_cache[key]
    path = find_font_file(name)
    if path is None:
        MISSING_FONTS.add(name or "(default)")
        path = fallback_file()
    if path is None:
        f = ImageFont.load_default()
    else:
        try:
            f = ImageFont.truetype(path, max(1, int(round(px_size))), index=0)
        except Exception:
            f = ImageFont.load_default()
    _font_cache[key] = f
    return f


def px(v):
    return None if v is None else float(v) / EMU_PX


def hex_of(color_format):
    try:
        if color_format is not None and color_format.type is not None:
            rgb = color_format.rgb
            if rgb is not None:
                return "#" + str(rgb)
    except Exception:
        return None
    return None


def luminance(hex_color):
    h = (hex_color or "").lstrip("#")
    if len(h) != 6:
        return None
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return None
    ch = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (r, g, b)]
    return 0.2126 * ch[0] + 0.7152 * ch[1] + 0.0722 * ch[2]


def contrast_ratio(a, b):
    la, lb = luminance(a), luminance(b)
    if la is None or lb is None:
        return None
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def blend(fg, bg, alpha):
    if alpha >= 0.999 or not fg or not bg:
        return fg or bg
    try:
        fa = [int(fg[i:i + 2], 16) for i in (1, 3, 5)]
        ba = [int(bg[i:i + 2], 16) for i in (1, 3, 5)]
    except ValueError:
        return fg
    out = [round(alpha * f + (1 - alpha) * b) for f, b in zip(fa, ba)]
    return "#%02X%02X%02X" % tuple(out)


def fill_of(shape):
    """(hex, alpha) of a solid or gradient fill straight from spPr."""
    spPr = shape._element.find(qn("p:spPr"))
    if spPr is None:
        return None, 1.0
    solid = spPr.find(qn("a:solidFill"))
    if solid is not None:
        srgb = solid.find(qn("a:srgbClr"))
        if srgb is None:
            return None, 1.0
        alpha = 1.0
        a = srgb.find(qn("a:alpha"))
        if a is not None:
            alpha = int(a.get("val")) / 100000.0
        return "#" + srgb.get("val"), alpha
    grad = spPr.find(qn("a:gradFill"))
    if grad is not None:
        gs = grad.find(qn("a:gsLst"))
        if gs is not None:
            first = gs.find(qn("a:gs"))
            if first is not None:
                srgb = first.find(qn("a:srgbClr"))
                if srgb is not None:
                    return "#" + srgb.get("val"), 1.0
    return None, 1.0


def iter_shapes(shapes, ox=0.0, oy=0.0):
    for sh in shapes:
        try:
            is_group = sh.shape_type == MSO_SHAPE_TYPE.GROUP
        except Exception:
            is_group = False
        if is_group:
            try:
                for sub in iter_shapes(sh.shapes, ox + (sh.left or 0), oy + (sh.top or 0)):
                    yield sub
            except Exception:
                continue
        else:
            yield sh, ox, oy


# ---------------------------------------------------------------- text metric


def para_runs(para, default_font=None, default_size=None):
    runs = []
    for r in para.runs:
        if not r.text:
            continue
        size = r.font.size.pt if r.font.size else (para.font.size.pt if para.font.size else None)
        runs.append({
            "text": r.text,
            "size": size or default_size or DEFAULT_SIZE,
            "font": r.font.name or para.font.name or default_font or DEFAULT_FONT,
            "color": hex_of(r.font.color) or hex_of(para.font.color),
            "bold": bool(r.font.bold),
        })
    return runs


def measure_paragraph(runs, avail_w, wrap=True, spacing=None):
    """Returns (width_px, height_px, size_pt_max, lines, raw_width)."""
    total_w = 0.0
    max_size = 0.0
    for seg in runs:
        fpx = seg["size"] * 96.0 / 72.0
        font = font_for(seg["font"], fpx)
        total_w += font.getlength(seg["text"])
        max_size = max(max_size, fpx)

    if not wrap:
        lines = 1
        width = total_w
    else:
        lines = 1 if total_w <= avail_w else int(math.ceil(total_w / max(avail_w, 1.0)))
        width = min(total_w, avail_w)
    lh = (spacing or 1.2) * max_size
    return width, lines * lh, max_size * 72.0 / 96.0, lines, total_w


def ink_rect(shape):
    """Estimate the painted text rectangle in px, honouring margins/align/anchor."""
    tf = shape.text_frame
    x0, y0 = px(shape.left), px(shape.top)
    w, h = px(shape.width), px(shape.height)
    if None in (x0, y0, w, h):
        return None
    ml, mt = px(tf.margin_left) or 0, px(tf.margin_top) or 0
    mr, mb = px(tf.margin_right) or 0, px(tf.margin_bottom) or 0
    avail_w = max(1.0, w - ml - mr)

    total_h = 0.0
    ink_w = 0.0
    widest_raw = 0.0
    overflow_x = False
    for para in tf.paragraphs:
        runs = para_runs(para)
        if not runs:
            continue
        width, height, _sz, _lines, raw = measure_paragraph(
            runs, avail_w, wrap=tf.word_wrap is not False, spacing=para.line_spacing)
        total_h += height
        total_h += ((para.space_before.pt if para.space_before else 0) +
                    (para.space_after.pt if para.space_after else 0)) * 96.0 / 72.0
        ink_w = max(ink_w, width)
        widest_raw = max(widest_raw, raw)
        if tf.word_wrap is False and raw > avail_w + 2:
            overflow_x = True

    if total_h <= 0:
        return None
    anchor = tf.vertical_anchor
    if anchor is not None and int(anchor) == 3:      # middle
        top = y0 + (h - total_h) / 2.0
    elif anchor is not None and int(anchor) == 4:    # bottom
        top = y0 + h - mb - total_h
    else:
        top = y0 + mt

    align = tf.paragraphs[0].alignment if tf.paragraphs else None
    if align is not None and int(align) == 2:        # center
        left = x0 + (w - ink_w) / 2.0
    elif align is not None and int(align) == 3:      # right
        left = x0 + w - mr - ink_w
    else:
        left = x0 + ml

    return {
        "box": (left, top, left + ink_w, top + total_h),
        "frame": (x0, y0, x0 + w, y0 + h),
        "width": ink_w, "height": total_h,
        "avail_w": avail_w, "avail_h": h - mt - mb,
        "raw_w": widest_raw, "overflow_x": overflow_x,
    }


def extract(slide):
    items = []
    for order, (sh, ox, oy) in enumerate(iter_shapes(slide.shapes)):
        try:
            x0, y0 = px(sh.left) + px(ox), px(sh.top) + px(oy)
            w, h = px(sh.width), px(sh.height)
        except Exception:
            continue
        if None in (x0, y0, w, h):
            continue
        item = {
            "order": order, "shape": sh, "name": sh.name,
            "frame": (x0, y0, x0 + w, y0 + h),
            "fill": None, "alpha": 1.0, "paras": [], "ink": None,
        }
        has_text = getattr(sh, "has_text_frame", False) and sh.has_text_frame and sh.text_frame.text.strip()
        if has_text:
            try:
                item["ink"] = ink_rect(sh)
            except Exception:
                item["ink"] = None
            item["paras"] = [
                {"text": "".join(r.text for r in p.runs), "runs": para_runs(p)}
                for p in sh.text_frame.paragraphs if "".join(r.text for r in p.runs).strip()
            ]
        item["fill"], item["alpha"] = fill_of(sh)
        items.append(item)
    return items


def slide_bg(slide):
    for sh in slide.shapes:
        if sh.name == "deco_bg":
            c, _ = fill_of(sh)
            if c:
                return c
    return "#FFFFFF"


def bg_color_at(slide, x, y):
    """Background colour at a point: interpolates a vertical/linear gradient."""
    import math
    for sh in slide.shapes:
        if sh.name != "deco_bg":
            continue
        spPr = sh._element.find(qn("p:spPr"))
        grad = spPr.find(qn("a:gradFill")) if spPr is not None else None
        if grad is None:
            c, _ = fill_of(sh)
            return c or "#FFFFFF"
        gs = grad.find(qn("a:gsLst"))
        stops = []
        if gs is not None:
            for g in gs.findall(qn("a:gs")):
                srgb = g.find(qn("a:srgbClr"))
                if srgb is not None:
                    stops.append((int(g.get("pos")) / 100000.0, "#" + srgb.get("val")))
        stops.sort()
        if not stops:
            return "#FFFFFF"
        lin = grad.find(qn("a:lin"))
        ang = (int(lin.get("ang")) / 60000.0) if lin is not None else 90.0
        rad = math.radians(ang)
        dx, dy = math.cos(rad), math.sin(rad)
        w, h = px(sh.width) or 1, px(sh.height) or 1
        ox, oy = px(sh.left) or 0, px(sh.top) or 0
        full = abs(w * dx) + abs(h * dy)
        t = ((x - ox) * dx + (y - oy) * dy) / full if full else 0.0
        t = min(1.0, max(0.0, t))
        for i in range(len(stops) - 1):
            p0, c0 = stops[i]
            p1, c1 = stops[i + 1]
            if p0 <= t <= p1:
                k = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
                return blend(c1, c0, k)
        return stops[-1][1]
    return "#FFFFFF"


def anim_stats(slide):
    """(effect count, estimated ms). Sequential afterEffect chains add up; withEffect
    siblings run in parallel and cost nothing extra."""
    xml = slide._element
    effects = xml.findall(".//" + qn("p:animEffect"))
    total = 0
    for ctn in xml.findall(".//" + qn("p:cTn")):
        if ctn.get("presetClass") != "entr":
            continue
        node = ctn.get("nodeType") or ""
        delay = 0
        cond = ctn.find(qn("p:stCondLst") + "/" + qn("p:cond"))
        if cond is not None and (cond.get("delay") or "").isdigit():
            delay = int(cond.get("delay"))
        dur = 0
        for child in ctn.findall(".//" + qn("p:animEffect") + "//" + qn("p:cTn")):
            d = child.get("dur")
            if d and d.isdigit():
                dur = max(dur, int(d))
        total += delay
        if node != "withEffect":
            total += dur
    return len(effects), total


def picture_coverage(slide, slide_area):
    area = 0.0
    for sh in slide.shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.PICTURE and not sh.name.startswith("deco"):
            area += (px(sh.width) or 0) * (px(sh.height) or 0)
    return area / slide_area if slide_area else 0.0


def overlap_area(a, b, pad=3.0):
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    iw = min(ax1, bx1) - max(ax0, bx0) - 2 * pad
    ih = min(ay1, by1) - max(ay0, by0) - 2 * pad
    if iw <= 0 or ih <= 0:
        return 0.0
    return iw * ih


def contains(card, ink, tol=3.0):
    cx0, cy0, cx1, cy1 = card
    x0, y0, x1, y1 = ink
    return (x0 >= cx0 - tol and y0 >= cy0 - tol and
            x1 <= cx1 + tol and y1 <= cy1 + tol)


def audit(path, args):
    prs = Presentation(path)
    SW, SH = px(prs.slide_width), px(prs.slide_height)
    slide_area = SW * SH
    report = {"file": os.path.basename(path), "slides": [],
              "errors": 0, "warnings": 0, "infos": 0}

    for idx, slide in enumerate(prs.slides, 1):
        issues = []
        bg = slide_bg(slide)
        items = extract(slide)
        texts = [i for i in items if i["paras"] and i["ink"]]

        # ---------------------------------------------------------- font floor
        for item in texts:
            for para in item["paras"]:
                for run in para["runs"]:
                    size = run["size"]
                    shown = run["text"].strip()
                    if not shown:
                        continue
                    if size < args.hard_min:
                        issues.append(("error", "font",
                                       f"{size:g}pt < {args.hard_min:g}pt: “{shown[:26]}” in {item['name']}"))
                    elif len(shown) >= 8 and args.body_min > size >= 14:
                        issues.append(("warn", "font",
                                       f"body-like {size:g}pt (< {args.body_min:g}pt): “{shown[:26]}”"))

        # ---------------------------------------------------------- overflow
        for item in texts:
            ink = item["ink"]
            if ink["overflow_x"]:
                issues.append(("error", "overflow",
                               f"no-wrap text {ink['raw_w']:.0f}px > box {ink['avail_w']:.0f}px: "
                               f"“{item['paras'][0]['text'][:24]}”"))
            if ink["avail_h"] > 4 and ink["height"] > ink["avail_h"] * 1.06 + 3:
                issues.append(("warn", "overflow",
                               f"text spills its box (~{ink['height']:.0f}px vs {ink['avail_h']:.0f}px): "
                               f"“{item['paras'][0]['text'][:24]}” in {item['name']}"))

        # ---------------------------------------------------------- overlap (ink)
        for a_i, a in enumerate(texts):
            for b in texts[a_i + 1:]:
                inter = overlap_area(a["ink"]["box"], b["ink"]["box"])
                if inter <= 0:
                    continue
                amin = min(a["ink"]["width"] * a["ink"]["height"],
                           b["ink"]["width"] * b["ink"]["height"])
                ratio = inter / max(amin, 1.0)
                if ratio > 0.10:
                    issues.append(("error", "overlap",
                                   f"text ink overlaps {ratio:.0%}: "
                                   f"“{a['paras'][0]['text'][:18]}” × “{b['paras'][0]['text'][:18]}”"))

        # text ink straddling a filled card behind it
        for item in texts:
            ink = item["ink"]["box"]
            area = max(1.0, (ink[2] - ink[0]) * (ink[3] - ink[1]))
            for card in items:
                if card["order"] >= item["order"] or card["fill"] is None:
                    continue
                if card["name"].startswith("deco") or card["paras"]:
                    continue
                if card["alpha"] < 0.9:
                    continue
                cbox = card["frame"]
                carea = (cbox[2] - cbox[0]) * (cbox[3] - cbox[1])
                if carea < area * 0.8 or carea > area * 20:
                    continue
                cx, cy = (ink[0] + ink[2]) / 2, (ink[1] + ink[3]) / 2
                if not (cbox[0] <= cx <= cbox[2] and cbox[1] <= cy <= cbox[3]):
                    continue
                if contains(cbox, ink):
                    continue
                inter = overlap_area(cbox, ink, pad=0)
                if inter / area > 0.10:
                    issues.append(("warn", "overlap",
                                   f"text straddles a card edge ({inter / area:.0%} inside): "
                                   f"“{item['paras'][0]['text'][:22]}”"))
                    break

        # ---------------------------------------------------------- edges
        for item in texts:
            x0, y0, x1, y1 = item["ink"]["box"]
            if x0 < args.edge or x1 > SW - args.edge or y0 < args.edge or y1 > SH - args.edge:
                issues.append(("warn", "edge",
                               f"text ink within {args.edge:g}px of the slide edge: "
                               f"“{item['paras'][0]['text'][:22]}”"))
        for item in items:
            x0, y0, x1, y1 = item["frame"]
            if x0 < -8 or y0 < -8 or x1 > SW + 8 or y1 > SH + 8:
                if not item["name"].startswith("deco"):
                    issues.append(("info", "edge", f"shape extends past the canvas: {item['name']}"))

        # ---------------------------------------------------------- contrast
        for item in texts:
            x0, y0, x1, y1 = item["ink"]["box"]
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            behind = None
            for s in items:
                if s["order"] >= item["order"] or s["fill"] is None or s["paras"]:
                    continue
                if s["name"] == "deco_bg":
                    continue
                bx0, by0, bx1, by1 = s["frame"]
                if bx0 <= cx <= bx1 and by0 <= cy <= by1:
                    behind = s
            if item["fill"]:
                base = blend(item["fill"], bg, item["alpha"])
            else:
                base = bg_color_at(slide, cx, cy) if behind is None else blend(behind["fill"], bg_color_at(slide, cx, cy), behind["alpha"])
            for para in item["paras"]:
                for run in para["runs"]:
                    if not run["color"]:
                        continue
                    ratio = contrast_ratio(run["color"], base)
                    if ratio is None:
                        continue
                    need = 3.0 if run["size"] >= 24 else args.contrast
                    if ratio < need:
                        issues.append(("warn", "contrast",
                                       f"{ratio:.1f}:1 < {need:.1f}:1 — {run['color']} on {base}: "
                                       f"“{run['text'][:20]}”"))

        # ---------------------------------------------------------- emoji
        all_text = " ".join(p["text"] for i in texts for p in i["paras"])
        em = EMOJI_RE.findall(all_text)
        if em:
            issues.append(("warn", "emoji", f"{len(em)} emoji in slide text: {' '.join(em[:6])}"))

        # ---------------------------------------------------------- motion
        n_eff, total_ms = anim_stats(slide)
        if n_eff and total_ms > args.max_motion_ms:
            issues.append(("warn", "motion",
                           f"{n_eff} effects, ~{total_ms / 1000:.1f}s (budget {args.max_motion_ms / 1000:.1f}s)"))
        if n_eff > 60:
            issues.append(("warn", "motion", f"{n_eff} effects on one slide — too many to read"))

        # ---------------------------------------------------------- flat image
        cov = picture_coverage(slide, slide_area)
        if cov > 0.8:
            issues.append(("warn", "flat", f"pictures cover {cov:.0%} of the slide — not editable text"))

        # ---------------------------------------------------------- title floor
        sizes = [r["size"] for i in texts for p in i["paras"] for r in p["runs"] if r["text"].strip()]
        if sizes and max(sizes) < 28:
            issues.append(("warn", "font", f"largest text is {max(sizes):g}pt — no title-level text"))

        # ---------------------------------------------------------- notes
        notes = slide.notes_slide.notes_text_frame.text.strip() if slide.has_notes_slide else ""
        if not notes:
            issues.append(("info", "notes", "no speaker notes"))

        counts = Counter(s for s, _, _ in issues)
        report["slides"].append({
            "index": idx,
            "shape_count": len(items),
            "min_font": min(sizes) if sizes else None,
            "max_font": max(sizes) if sizes else None,
            "animations": n_eff,
            "motion_ms": total_ms,
            "errors": counts.get("error", 0),
            "warnings": counts.get("warn", 0),
            "infos": counts.get("info", 0),
            "issues": [{"level": s, "kind": k, "detail": d} for s, k, d in issues],
        })
        report["errors"] += counts.get("error", 0)
        report["warnings"] += counts.get("warn", 0)
        report["infos"] += counts.get("info", 0)

    report["missing_fonts"] = sorted(MISSING_FONTS)
    lines = [f"{report['file']} — {len(report['slides'])} slides | "
             f"{report['errors']} errors, {report['warnings']} warnings, {report['infos']} infos"]
    for s in report["slides"]:
        flag = "FAIL" if s["errors"] else ("warn" if s["warnings"] else "ok  ")
        lines.append(f"[{s['index']:02d}] {flag} shapes={s['shape_count']:<3} "
                     f"font={s['min_font']}–{s['max_font']}pt anim={s['animations']}"
                     f"({s['motion_ms'] / 1000:.1f}s)")
        for it in s["issues"]:
            if it["level"] == "info":
                continue
            mark = "  X" if it["level"] == "error" else "  !"
            lines.append(f"{mark} {it['kind']:<9} {it['detail']}")
    if report.get("missing_fonts"):
        lines.append("Fonts not found: " + ", ".join(report["missing_fonts"]) +
                     " — these runs were measured with a fallback face, expect a few percent error.")
    if report["errors"]:
        lines.append("Errors must be fixed before delivery. Warnings need a judgement call.")
    else:
        lines.append("No blocking issues. Still render the pages and look at them.")
    text = "\n".join(lines)

    if args.json:
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    if not args.quiet:
        print(text)

    return 1 if report["errors"] else 0


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Static readability audit for .pptx decks")
    ap.add_argument("deck")
    ap.add_argument("--json", help="write a JSON report here")
    ap.add_argument("--out", help="write the text report here (UTF-8)")
    ap.add_argument("--hard-min", type=float, default=13.0, help="error below this pt size")
    ap.add_argument("--body-min", type=float, default=18.0, help="warn for long text below this")
    ap.add_argument("--edge", type=float, default=18.0, help="min px from slide edge for text")
    ap.add_argument("--contrast", type=float, default=4.5, help="WCAG ratio for small text")
    ap.add_argument("--max-motion-ms", type=int, default=1500, help="per-slide animation budget")
    ap.add_argument("--font-dir", action="append", default=[],
                    help="extra font directory (repeatable); DECK_FONT_DIRS env is also read")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    EXTRA_FONT_DIRS.extend(args.font_dir)
    return audit(args.deck, args)


if __name__ == "__main__":
    sys.exit(main())
