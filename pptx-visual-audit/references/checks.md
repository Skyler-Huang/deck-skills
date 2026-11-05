# Checks in detail

## font

**Measured:** every run's explicit size. A run without a size inherits the paragraph size, then 18pt.

**Why 13pt is the floor:** at 13pt, a capital-height glyph is about 4.6 mm tall. From 8 m that subtends roughly 2 arc-minutes — the practical limit for comfortable reading. 9–11pt (what document-style decks use) is unreadable past the second row.

**Why 18pt for body:** a 1280px-wide slide shown at 1920px scales 1.5×; 18pt becomes 27px on screen, which matches a comfortable web reading size. Anything below it reads as a caption, so the audience stops reading and starts squinting.

**False positives:** legal footers, source lines under images, and page numbers may sit at 11–13pt by design. Accept those deliberately; do not lower `--hard-min` to silence them.

## overflow

**Measured:** line count from real glyph advances (`PIL.ImageFont.getlength`), times line height, plus paragraph spacing, compared with the box minus its margins. Width is only enforced for `word_wrap = False`, because a wrapping box legitimately reflows.

**Why height spill is a warning, not an error:** a 40px box holding one 20pt line spills, but nothing collides and nothing clips. It matters only when the spill hits another element — which the overlap check catches. A no-wrap width overflow is an error, because the renderer clips it or runs it over the neighbour.

**Common cause:** box height set to the font's nominal size instead of `size × line_spacing × 1.33`. A 20pt paragraph at 1.5 line spacing needs ~40px per line, not 27px.

**Fix order:** shorten the text → widen the box → reduce spacing → reduce size. Never reduce size below 18pt to make it fit.

## overlap

**Measured:** intersection of ink rectangles (painted area), with a 3px pad, divided by the smaller ink area. Above 10% is an error.

**Why ink, not frames:** see the SKILL.md note. A deck built with generous frame heights (300px boxes for 40px lines) produces dozens of frame collisions that are invisible on screen. Ink rectangles remove that noise and expose the real ones.

**Straddle warning:** text that is mostly inside a filled card but crosses its edge by > 10% of the text area. Usually a title positioned 4px too low, or a caption that outgrew its card. Filters skip translucent shapes (background washes), shapes larger than 20× the text area (page backgrounds), and shapes without text (cards) only.

**Fix:** move the text block inside the card's padding, or extend the card. Do not "fix" it by shrinking the text until it fits a card that was too small.

## edge

Text ink within 18px of the canvas edge, or any non-`deco` shape outside the canvas.

A 72px margin is the design default; 18px is the hard floor. Footers placed at 28–36px from the bottom are normal and pass. A title that ends 6px from the right edge is a defect even though the audit only warns.

## contrast

**Measured:** WCAG 2.1 contrast of the run colour against the topmost filled shape behind the text's centre, blended with the declared alpha; falls back to the slide background, then white.

**Thresholds:** 4.5:1 for text under 24pt, 3:1 at or above 24pt. Large type earns the lower ratio because stroke thickness compensates.

**Saturated accents are the usual trap.** White on `#FF6B35` is 2.8:1; white on `#2EC4E6` is 2.1:1. On these fills put **ink** (`#17384D`, ~8:1) instead of white, or darken the fill. Yellow `#FFD23F` always wants ink.

**Bronze on cream** (`#9A6B33` on `#F7F4EC`) is 4.2:1 — fine at 24pt+, short at 13pt. That is why editorial decks put bronze on kickers (tracked, uppercase) and ink on body.

**False positives:** text over photographs, gradients with strong spatial variation, and outlined text. The audit samples one colour; check those visually.

## emoji

Pictographic emoji only (arrows → and check marks ✓ are allowed, they are typography). Emoji render differently per machine and read as decoration; replace with a drawn shape or delete.

## motion

**Measured:** number of `p:animEffect` elements and the sum of their durations plus non-zero delays as an upper bound on the slide's entrance sequence.

**Budget:** 1.5 s per slide. A 7-element cascade at 250 ms each already exceeds it. Stagger two or three groups, not every line: fast decks feel confident, slow ones feel like a screensaver.

**Not measured:** per-character builds (they appear as one effect), exit animations, and transition duration. Check those in the file if they matter.

## flat

Pictures covering more than 80% of a slide. One image-based page is a stylistic choice; a whole deck of them is not editable, cannot be updated, and usually means the design was generated as pixels. Keep text and shapes live.

## notes

Info only. A missing speaker script is not a visual defect, but a 20-page deck without notes usually means the presenter is improvising.
