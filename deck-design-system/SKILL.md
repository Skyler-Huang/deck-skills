---
name: deck-design-system
description: Design system for building presentation decks with python-pptx — two style presets (sticker-kids for children's products, warm-academic for reviews), a projection-safe type scale, a 12-column grid, twelve page archetypes, and a helper kit. Load before writing any slide-building script.
whenToUse: When creating or restyling a .pptx deck, choosing a visual direction, fixing "too small / too crowded / looks AI-generated" feedback, or when a design must match an existing product's UI.
---

# Deck design system

Two failures make a generated deck look "AI made it": type sized for a document instead of a projector, and hand-placed shapes with no grid. This skill is the antidote — pick a preset, take sizes from the scale, lay out on the grid, proof two sample pages, then build.

## When to use

- Building a new deck, or restyling one after feedback like "字号太小 / 排版粘连 / 风格不对".
- The deck must match a product's existing UI (extract its design tokens first — see "Deriving a preset").
- Choosing between visual directions for a review (professors, judges, investors).

Not for: single-table documents (use a real document), or editing someone's brand template (follow their template instead).

## Workflow

1. **Brief before pixels.** Record: audience, room/projection distance, one-sentence claim per page, content source. Ask rather than guess about screenshots, naming rules, and which pages may merge.
2. **Pick a preset** from `assets/tokens.json`:
   - `sticker-kids` — sky→paper gradient, white cards with a hard shadow (`0 5px 0`), six saturated accents, 幼圆 display / 微软雅黑 body. For children's products and product-launch feel.
   - `warm-academic` — paper background, hairline rules, bronze accent, 宋体 display. For review panels that need calm authority.
3. **Set the type scale** from `assets/tokens.json → typeScale`. Body never below 18pt; nothing visible below 13pt.
4. **Build two sample pages first** (a cover and a data page), render them, show them, and wait for approval. Never build 20 pages before the style is agreed.
5. **Build the rest** with `scripts/deck_kit.py`, one page archetype at a time (`references/page-types.md`).
6. **Gate the result** with the `pptx-visual-audit` skill, then look at the rendered images. Static checks do not prove the page looks right.

## Hard rules

| # | Rule | Why |
|---|---|---|
| 1 | Body ≥ 18pt, labels ≥ 13pt, titles ≥ 32pt, stat numbers ≥ 44pt | A projector at 8 m halves apparent size |
| 2 | One idea per page; ≤ 3 content blocks; ≤ 80 body characters | The reader is listening, not reading |
| 3 | 12-column grid, 72px side margins, ≥ 40px between blocks | Removes the "shapes drifted into each other" look |
| 4 | Every text box has ≥ 16px clearance from other boxes and card edges | Prevents collisions when fonts substitute |
| 5 | Text color on any fill ≥ 4.5:1 contrast (≥ 3:1 for ≥ 24pt) | Legibility in a bright room |
| 6 | No orphan characters: a line must not end with 1–2 characters of a word | Chinese line-breaking makes slides look broken |
| 7 | Motion: entrance only, ≤ 1.2 s per page, no per-character effects | Per-letter animation reads as amateur |
| 8 | Everything stays editable text/shapes — never a full-page screenshot | Judges ask "can you change this?" |

## Page archetypes

`references/page-types.md` defines twelve layouts with ASCII wireframes and content budgets: cover, claim, data row, comparison, process, quote/letter, table, timeline/funnel, diagram (Venn/rings), two-panel, screenshot hero, closing. Pick the archetype before writing coordinates.

## Typography

`references/typography.md` covers CJK font pairing, line-height, tracking, numerals, and the substitution problem (why a box that fits in one renderer overflows in another).

## Helper kit

```python
import sys; sys.path.insert(0, r"<skill>/scripts")
from deck_kit import Deck

d = Deck("sticker-kids")          # or "warm-academic"
s = d.new_slide()
d.bg(s)
d.title("515 处引用，逐字核对通过", y=110)
d.card(72, 258, 340, 218)
d.stat(100, 282, 290, "79/79", "篇有招", "每一篇都拆出了可用的写法")
d.save("out.pptx")
```

`deck_kit` exposes: `bg`, `card`, `pill`, `star`, `dot`, `text`, `stat`, `title`, `footer`, `fit_size` (shrinks a title to fit a width). Coordinates are px in a 1280×720 design space; `P(px)` / `PT(px)` convert.

## Deriving a preset from a product UI

When the deck must match an existing app, do not invent colours — extract them:

1. Fetch the app's CSS bundle (the HTML links one `index-*.css`); read custom properties (`--ink`, `--sky`, `--r-lg`, `--shadow`) and `font-family` stacks.
2. Record: background/gradient, ink + soft ink, 3–6 accents, radius set, shadow spec (blur, offset, alpha), display vs body font, letter-spacing.
3. Add the result as a new preset in `assets/tokens.json` with `useFor` / `avoidFor`; never edit an existing preset in place.

Extracted example (范文放大镜 app): `--sky #BFE9FF`, `--ink #17384D`, `--orange #FF6B35`, `--yellow #FFD23F`, radius 26/14/9, shadow `0 5px 0 rgba(23,56,77,.16)`, font `YouYuan` + `Fredoka`.

## Anti-patterns

- Dark navy + bronze + 宋体 for a children's product; it reads as finance, not school.
- A five-row table at 10.5pt on one slide — that is a document, not a slide.
- Filling every corner with decorations; budget ≤ 5 decorative elements per page.
- Titles that nearly touch the right margin: measure, or use `fit_size`.
- Building the full deck before showing two sample pages.
- Claiming "reviewed" after a static check; render and look at the images.

## Hand-off

After building, run `pptx-visual-audit` (font floor, overflow, overlaps, edge distance, contrast, emoji, animation length, image-only pages), then render every page with the Office render skill and inspect the images. Fix, rebuild, re-audit. Record what changed in the delivery note.
