# -*- coding: utf-8 -*-
"""deck_kit — small, preset-aware helpers for building decks with python-pptx.

Design space: 1280 x 720 px (13.333 x 7.5 in at 96 dpi). All coordinates are px.

    from deck_kit import Deck
    d = Deck("sticker-kids")
    s = d.new_slide()
    d.bg(s)
    d.card(s, 72, 508, 340, 130)
    d.text(s, 96, 528, 280, 34, "选一篇范文", size=17, bold=True)
    d.save("out.pptx")

Tokens come from ../assets/tokens.json (single source of truth for colors,
radii, shadows, fonts and the type scale).
"""
from __future__ import annotations

import json
import os

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
TOKENS_PATH = os.path.join(os.path.dirname(HERE), "assets", "tokens.json")
with open(TOKENS_PATH, encoding="utf-8") as fh:
    TOKENS = json.load(fh)

SLIDE_W_PX, SLIDE_H_PX = 1280, 720


def C(value: str) -> RGBColor:
    return RGBColor.from_string(value.lstrip("#"))


def P(px: float) -> Inches:
    return Inches(px / 96.0)


def PT(px: float) -> Pt:
    return Pt(px * 0.75)


def _strip_style(shape):
    el = shape._element
    st = el.find(qn("p:style"))
    if st is not None:
        el.remove(st)
    return shape


def _set_alpha(shape, alpha: float):
    srgb = shape.fill._xPr.find(qn("a:solidFill")).find(qn("a:srgbClr"))
    a = etree.SubElement(srgb, qn("a:alpha"))
    a.set("val", str(int(alpha * 100000)))


def hard_shadow(shape, dist_px=5, color="#17384D", alpha=0.16, blur_px=0):
    spPr = shape._element.find(qn("p:spPr"))
    for old in spPr.findall(qn("a:effectLst")):
        spPr.remove(old)
    eff = etree.SubElement(spPr, qn("a:effectLst"))
    sh = etree.SubElement(eff, qn("a:outerShdw"))
    sh.set("blurRad", str(int(blur_px * 12700)))
    sh.set("dist", str(int(dist_px * 9525)))
    sh.set("dir", "5400000")
    sh.set("algn", "tl")
    sh.set("rotWithShape", "0")
    clr = etree.SubElement(sh, qn("a:srgbClr"))
    clr.set("val", color.lstrip("#"))
    a = etree.SubElement(clr, qn("a:alpha"))
    a.set("val", str(int(alpha * 100000)))
    return shape


def text_units(s: str) -> float:
    """Approximate width in em: CJK/full-width = 1, ASCII = 0.55, spaces = 0.3."""
    total = 0.0
    for ch in s:
        o = ord(ch)
        if ch == " ":
            total += 0.3
        elif o < 128:
            total += 0.55
        else:
            total += 1.0
    return total


class Deck:
    """One presentation + one active preset. Coordinates are px in 1280x720 space."""

    def __init__(self, preset="sticker-kids", width_px=SLIDE_W_PX, height_px=SLIDE_H_PX,
                 pattern_path=None):
        self.preset_name = preset
        self.t = TOKENS["presets"][preset]
        self.type_scale = TOKENS["typeScale"]
        self.grid = TOKENS["grid"]
        self.prs = Presentation()
        self.prs.slide_width = P(width_px)
        self.prs.slide_height = P(height_px)
        self.w, self.h = width_px, height_px
        self.blank = self.prs.slide_layouts[6]
        self.slide = None
        self.pattern = pattern_path

    # ---------------------------------------------------------------- slides
    def new_slide(self):
        self.slide = self.prs.slides.add_slide(self.blank)
        return self.slide

    def save(self, path):
        self.prs.core_properties.title = os.path.splitext(os.path.basename(path))[0]
        self.prs.save(path)
        return path

    # ---------------------------------------------------------------- shapes
    def bg(self, slide=None):
        slide = slide or self.slide
        s = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0,
                                   P(self.w), P(self.h))
        _strip_style(s)
        s.line.fill.background()
        s.shadow.inherit = False
        bgspec = self.t["background"]
        if bgspec["type"] == "gradient" or bgspec["type"] == "linear":
            f = s.fill
            f.gradient()
            f.gradient_angle = (360 - bgspec.get("angle", 90)) % 360
            stops = f.gradient_stops
            stops[0].color.rgb = C(bgspec["stops"][0][0])
            stops[0].position = float(bgspec["stops"][0][1])
            stops[1].color.rgb = C(bgspec["stops"][1][0])
            stops[1].position = float(bgspec["stops"][1][1])
        else:
            s.fill.solid()
            s.fill.fore_color.rgb = C(bgspec["color"])
        s.name = "deco_bg"
        if self.pattern and os.path.isfile(self.pattern):
            pic = slide.shapes.add_picture(self.pattern, 0, 0, width=P(self.w), height=P(self.h))
            pic.name = "deco_pattern"
        return s

    def card(self, x, y, w, h, slide=None, fill=None, radius_px=None,
             line=None, line_pt=1.0, shadow=True, name=None):
        slide = slide or self.slide
        r = self.t["radiusPx"]["lg"] if radius_px is None else radius_px
        kind = MSO_SHAPE.ROUNDED_RECTANGLE if r else MSO_SHAPE.RECTANGLE
        s = slide.shapes.add_shape(kind, P(x), P(y), P(w), P(h))
        _strip_style(s)
        if r:
            s.adjustments[0] = min(0.5, r / float(min(w, h)))
        s.fill.solid()
        s.fill.fore_color.rgb = C(fill or self.t["surface"])
        if line:
            s.line.color.rgb = C(line)
            s.line.width = Pt(line_pt)
        else:
            s.line.fill.background()
        s.shadow.inherit = False
        if shadow and self.t["shadow"]["alpha"] > 0:
            sh = self.t["shadow"]
            hard_shadow(s, sh["y"], sh["color"], sh["alpha"], sh["blur"])
        if name:
            s.name = name
        return s

    def pill(self, x, y, w, h, label, slide=None, fill=None, color=None,
             size=13, bold=False, border=None):
        slide = slide or self.slide
        s = self.card(x, y, w, h, slide=slide, fill=fill or self.t["surface"],
                      radius_px=h / 2.0, line=border, shadow=False)
        self._fill_text(s, label, size, color or self.t["ink"], bold, MSO_ANCHOR.MIDDLE,
                        PP_ALIGN.CENTER, margin_px=10)
        s.text_frame.margin_top = 0
        s.text_frame.margin_bottom = 0
        return s

    def pill_auto(self, x, y, label, size=13, slide=None, fill=None, color=None,
                  border=None, pad_px=44, height=38):
        """Pill sized from its label (CJK = 1em, ASCII = 0.55em)."""
        w = pad_px + text_units(label) * size * 96.0 / 72.0 * 1.15
        return self.pill(x, y, w, height, label, slide=slide, fill=fill,
                         color=color, size=size, border=border)

    def star(self, x, y, d, color, slide=None, alpha=1.0, rot=0):
        slide = slide or self.slide
        s = slide.shapes.add_shape(MSO_SHAPE.STAR_4_POINT, P(x), P(y), P(d), P(d))
        _strip_style(s)
        s.fill.solid()
        s.fill.fore_color.rgb = C(color)
        if alpha < 1.0:
            _set_alpha(s, alpha)
        s.line.fill.background()
        s.shadow.inherit = False
        s.rotation = rot
        return s

    def dot(self, x, y, d, color, slide=None, alpha=1.0):
        slide = slide or self.slide
        s = slide.shapes.add_shape(MSO_SHAPE.OVAL, P(x), P(y), P(d), P(d))
        _strip_style(s)
        s.fill.solid()
        s.fill.fore_color.rgb = C(color)
        if alpha < 1.0:
            _set_alpha(s, alpha)
        s.line.fill.background()
        s.shadow.inherit = False
        return s

    # ---------------------------------------------------------------- text
    def _fill_text(self, shape, lines, size, color, bold, anchor, align,
                   margin_px=0, spacing=1.35):
        tf = shape.text_frame
        tf.word_wrap = True
        tf.margin_left = P(margin_px)
        tf.margin_right = P(margin_px)
        tf.margin_top = P(margin_px)
        tf.margin_bottom = P(margin_px)
        tf.vertical_anchor = anchor
        lines = lines if isinstance(lines, (list, tuple)) else [lines]
        for i, ln in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.line_spacing = spacing
            r = p.add_run()
            r.text = ln
            self._font(r, self.t["fonts"]["display"], size, bold, color)

    def _font(self, run, name, size_pt, bold=False, color="#000000", spc=0):
        f = run.font
        f.name = name
        f.size = Pt(size_pt)
        f.bold = bold
        f.color.rgb = C(color)
        rPr = run._r.get_or_add_rPr()
        latin = rPr.find(qn("a:latin"))
        for tag in ("a:ea", "a:cs"):
            old = rPr.find(qn(tag))
            if old is not None:
                rPr.remove(old)
        ea = etree.SubElement(rPr, qn("a:ea"))
        ea.set("typeface", name)
        cs = etree.SubElement(rPr, qn("a:cs"))
        cs.set("typeface", name)
        if latin is not None:
            latin.addnext(ea)
        ea.addnext(cs)
        if spc:
            rPr.set("spc", str(int(spc * 100)))

    def text(self, x, y, w, h, lines, size=18, color=None, bold=False,
             slide=None, font=None, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
             spacing=1.4, spc=0, name=None):
        slide = slide or self.slide
        lines = lines if isinstance(lines, (list, tuple)) else [lines]
        # grow the frame so the estimated text never spills its box
        import math as _math
        need = 0.0
        for _ln in lines:
            _txt = _ln if isinstance(_ln, str) else str(_ln)
            _pxw = text_units(_txt) * size * 96.0 / 72.0
            _n = max(1, _math.ceil(_pxw / max(w, 1.0)))
            need += _n * size * spacing * 96.0 / 72.0
        h = max(h, need + 2)
        tb = slide.shapes.add_textbox(P(x), P(y), P(w), P(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = 0
        tf.margin_right = 0
        tf.margin_top = 0
        tf.margin_bottom = 0
        tf.vertical_anchor = anchor
        lines = lines if isinstance(lines, (list, tuple)) else [lines]
        for i, ln in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.line_spacing = spacing
            r = p.add_run()
            r.text = ln
            self._font(r, font or self.t["fonts"]["body"], size, bold,
                       color or self.t["ink"], spc)
        if name:
            tb.name = name
        return tb

    def stat(self, x, y, w, value, unit, caption, color=None, slide=None,
             value_pt=46, cap_pt=13):
        """Number + unit chip + one-line caption. Returns the caption shape.

        Budget ~ (value_pt * 2.6 + 60) px of card height, e.g. 44pt needs ~175px
        plus padding; use a 210–260px card.
        """
        slide = slide or self.slide
        col = color or self.t["accents"]["primary"]
        vh = value_pt * 1.45
        self.text(x, y, w, vh, value, size=value_pt, color=col,
                  bold=True, font=self.t["fonts"]["numeric"], slide=slide, spacing=1.0)
        cy = y + vh
        if unit:
            cw = max(96, min(w, 24 + text_units(unit) * 14))
            self.pill(x, cy, cw, 32, unit, slide=slide,
                      fill=self.t["paper"], color=self.t["ink"], size=13)
            cy += 46
        return self.text(x, cy, w, 56, caption,
                         size=cap_pt, color=self.t["inkSoft"], slide=slide, spacing=1.5)

    def accent_text(self, name="primary"):
        """Text-safe accent colour (contrast >= 4.5:1 on surface and paper)."""
        return self.t.get("accentsText", self.t["accents"]).get(name, self.t["accents"]["primary"])

    # ---------------------------------------------------------------- fitting
    def fit_size(self, s, width_px, base_pt, min_pt=20, font_em=1.0):
        """Largest pt (<= base) whose single-line width fits width_px."""
        w_em = text_units(s) * font_em
        if w_em <= 0:
            return base_pt
        per_pt_px = (96.0 / 72.0) * w_em
        return max(min_pt, min(base_pt, width_px / per_pt_px))

    def title(self, s, x=72, y=110, w=None, size=40, color=None, bold=True):
        w = w or (self.w - 2 * self.grid["marginPx"])
        size = self.fit_size(s, w, size, min_pt=24)
        return self.text(x, y, w, size * 1.55, s, size=size, bold=bold,
                         color=color, font=self.t["fonts"]["display"], spacing=1.15)

    def footer(self, page, total=None, label="", color=None):
        c = color or self.t["inkSoft"]
        s = f"{page:02d}" + (f" / {total:02d}" if total else "")
        self.text(self.grid["marginPx"], self.h - 44, 400, 24,
                  (label + "　" if label else "") + s, size=13, color=c)
