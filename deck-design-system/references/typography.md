# Typography for projected decks

Sizes are points on a 13.333 × 7.5 in slide. A projector at 8 m makes 18pt read like
11pt on a laptop, which is why document-sized type fails in a lecture room.

## Scale

| Role | Range | Default | Notes |
|---|---|---|---|
| Cover title | 52–64 | 56 | One line if possible; `fit_size` before shrinking |
| Section / claim | 38–44 | 40 | This is the workhorse size |
| Page title | 32–40 | 36 | Two lines maximum |
| Subtitle / lead | 18–22 | 20 | Often the strongest sentence on the page |
| Body | 18–20 | 18 | Never below 18 |
| Label / chip | 13–14 | 13 | Uppercase Latin may go to 12 if tracked |
| Footnote / source | 13 | 13 | Still must be readable |
| Stat number | 44–72 | 48 | Digits set in the numeric font |

Hard floor: **13pt for anything a reader must read**. Below that, delete the text or
move it to the speaker notes.

## CJK + Latin pairing

- Chinese display: 宋体 (classic, editorial) or 幼圆 (round, child-friendly). One per deck.
- Chinese body: 微软雅黑. It survives small sizes better than 幼圆, whose thin strokes fade.
- Latin/numerals: Georgia for an editorial tone; the display face for a product tone.
- Mono: Consolas, for identifiers and code only.
- Do not mix two display faces. A deck has one voice.

## Line height and tracking

- Display 56pt: line height 1.05–1.15, tracking 2–4pt.
- Title 36–40pt: 1.15–1.25.
- Body 18–20pt: 1.45–1.6 (CJK needs more air than Latin).
- Latin uppercase labels: tracking 1.2–2pt; never track lowercase body text.
- Kicker labels: 9–10pt only when they are decorative wayfinding; 13pt when they carry meaning.

## Numerals

- Set numbers in the numeric font for a different texture from body text.
- Keep value and unit together: `515 处`, not `515` then `处` on the next line.
- Ratios: `79 / 79` with thin spaces; avoid `79/79篇有招` as one string.
- One decimal is enough: `0.04 s`, not `0.040 s`.

## Line breaking (Chinese)

- Break between words, not inside a two-character word; PowerPoint does not do this for you.
- Avoid a last line with 1–2 characters: shorten the sentence or widen the box.
- Keep a number with its unit and a name with its title together (use a non-breaking space where possible).

## The substitution problem

A text box sized against one font overflows when another font substitutes — 宋体, 幼圆,
微软雅黑 and their fallbacks have different advance widths, and macOS/Linux renderers
differ from Windows. Consequences:

1. Size boxes with ≥ 15% slack, or let the paragraph wrap and set the box tall enough.
2. Do not rely on auto-fit; PowerPoint's "shrink text on overflow" changes size silently.
3. After export, audit again: the box that fit in the editor may clip in the renderer.
4. Prefer fewer, shorter lines over tighter tracking.

## Quick self-check

- Squint at the page: can you still see the title and the numbers? If not, the hierarchy is wrong.
- Read the smallest text at arm's length on a phone-sized preview; if it is unreadable there, it is unreadable at the back of the room.
- Count fonts: 1 display + 1 body + 1 mono is the ceiling.

## Accessible accent text

Brand accents are tuned for fills and large shapes, not for small text. Measured on white:

| Accent | Brand | On white | Text variant | On white |
|---|---|---|---|---|
| orange | `#FF6B35` | 2.8:1 | `#C25128` | 4.7:1 |
| yellow | `#FFD23F` | 1.4:1 | `#8A7122` | 4.7:1 |
| pink | `#FF5D8F` | 2.9:1 | `#C4486E` | 4.7:1 |
| cyan | `#2EC4E6` | 2.1:1 | `#1E7F96` | 4.6:1 |
| green | `#7BD389` | 1.8:1 | `#4A7F52` | 4.7:1 |
| purple | `#A06CD5` | 3.1:1 | `#8D5FBB` | 4.7:1 |

Rule: **fills use `accents`, text uses `accentsText`** (both live in `assets/tokens.json`).
Exception: a 44pt+ numeral on paper may keep the brand accent if you accept the lower
large-text ratio (3:1); at 2.8:1 it still fails, so darker is the safer choice.
Yellow is never a text colour — it is a highlighter.
