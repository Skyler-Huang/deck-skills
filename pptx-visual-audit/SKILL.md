---
name: pptx-visual-audit
description: Static audit for .pptx decks — finds text below the legibility floor, text that overflows its box, colliding text, edge violations, low contrast, emoji, over-long animations and image-only slides, using real font metrics and ink rectangles instead of frame geometry. Run before delivering any deck.
whenToUse: After building or editing a .pptx and before showing it to anyone; when the user says the deck looks cramped, small or "AI-made"; as a CI gate in a deck-building script.
---

# PPTX visual audit

A deck can pass "it opens" and still be unreadable: 9pt labels, text spilling out of boxes, two paragraphs painted on top of each other, white text on a light card. This skill checks those mechanically, then you look at the rendered pages.

## Quick start

```bash
python scripts/audit_pptx.py deck.pptx
python scripts/audit_pptx.py deck.pptx --json report.json --out report.txt
python scripts/audit_pptx.py deck.pptx --hard-min 13 --body-min 18 --min-contrast 4.5
```

Exit code 1 when any error-level finding exists (usable as a build gate). Errors block delivery; warnings need a judgement call; infos are context (e.g. missing notes).

## What it checks

| Check | Finds | Default threshold | Fix |
|---|---|---|---|
| `font` | runs below the legibility floor, and long body text below 18pt | error < 13pt; warn < 18pt for ≥ 8 chars | raise size, cut words, or move detail to notes |
| `overflow` | estimated text wider than a no-wrap box, or taller than its box | +6% height; +2px width | widen the box, shorten the line, lower the size, allow wrap |
| `overlap` | two text *ink* rectangles intersecting, or text straddling a card edge | > 10% of the smaller ink area | move a block, resize the card, reassign the anchor |
| `edge` | text ink within 18px of the slide edge | 18px | restore the margin (72px is the design default) |
| `contrast` | run colour vs the fill actually behind it | 4.5:1 (3:1 if ≥ 24pt) | darken text, lighten fill, or use ink on saturated accents |
| `emoji` | emoji inside slide text | any | replace with a vector shape or remove |
| `motion` | entrance effects over the per-slide budget | 1.5 s estimated | shorten durations, remove per-element cascades |
| `flat` | pictures covering > 80% of the slide | 80% | use editable text/shapes instead of a screenshot page |
| `notes` | no speaker notes | info | add a 30-second script |

Details, examples and remediation: `references/checks.md`.

## The one design decision worth knowing

Overlap is measured on **ink rectangles**, not text-box frames. PowerPoint text boxes are routinely 2–3× taller than the text they hold (a 40px box holding one 20pt line), so frame-vs-frame comparison reports collisions that do not exist and hides the real ones. The script estimates the painted area from font advances (`PIL.ImageFont` on the actual TTF), line count, alignment and vertical anchor.

Consequence: a text box may "spill" its frame without a warning — that is cosmetic unless it collides. A no-wrap width overflow is still an error, because the renderer clips or overlaps it.

## Workflow

1. Build or edit the deck.
2. Run the audit. Fix every `error`; read every `warning` and decide (some are acceptable: a deliberately low-contrast footnote on a hero image, a 1.6 s cascade on the closing page).
3. Render the pages to images (Office render skill) and look at them. The audit cannot see rhythm, cropping, awkward line breaks at the visual level, or a diagram whose labels sit on top of strokes.
4. Re-run after fixes; keep the JSON next to the deck as evidence of what was checked.

Never report "reviewed" on the strength of the audit alone — it is a floor, not a proof of good design.

## Reading the output

```
deck.pptx — 20 slides | 432 errors, 109 warnings, 0 infos

[02] FAIL shapes=36  font=8–11pt anim=0(0.0s)
  X font      8.5pt < 13pt: “教学法与儿童心理学的证据底座”
  ! contrast  4.2:1 < 4.5:1 — #9A6B33 on #F7F4EC: “来源”
```

- `font=8–11pt` is the fastest signal: a slide whose minimum is under 13 is a document, not a slide.
- A cluster of contrast warnings on one colour means the accent is too light for text — change the token, not each label.
- `anim=17(10.7s)` on every slide means the entrance cascade is far over budget.

## Limits

- Metrics are estimates: font substitution (宋体/幼圆/微软雅黑 fallbacks), kerning and PowerPoint's own line breaking differ by a few percent. Leave slack; do not tune to the pixel.
- It cannot judge whether a diagram is understandable, whether a photo is cropped well, or whether the page has the right amount of whitespace.
- It reads the file statically; it does not render. Animation *playback* and font embedding are out of scope.
- Charts and SmartArt text are not traversed (they are not shapes with text frames); check those visually.

## Using it as a gate

```python
import subprocess, sys
r = subprocess.run([sys.executable, "audit_pptx.py", "deck.pptx",
                    "--hard-min", "13", "--quiet", "--json", "audit.json"])
if r.returncode != 0:
    raise SystemExit("deck fails the legibility floor; see audit.json")
```
