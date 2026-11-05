# 生图 Prompt 模板（仅当用户允许生图）

> 前提：先用 `inspect_deck.py` 拿到色板，**把色值逐字写进 prompt**。生图只允许贡献「装饰」，底色必须由 `make_background.py` 用代码精确还原 —— 让生图整张替换背景，色值一定漂。

---

## 一、风格锁的三条硬规则

1. **色值写死**：把 `background.top` / `background.bottom` 的十六进制原样写进 prompt，并明确写「绝对不要米黄 / 牛皮纸色 / 整体偏黄」。
2. **中部留白写死**：明确「central 70–75% 完全干净、为空、留给文字」，并要求装饰只在四角与边缘带。
3. **负面词写全**：`no text, no letters, no words, no numbers, no watermark, no people, no cards, no frames, no 3D`。

生成后必须跑 `strip_watermark.py`，并处理「假透明」问题（见第四节）。

---

## 二、模板 A · 全页背景（柔光版）

把 `{{TOP}}` / `{{BOTTOM}}` / 强调色替换为 tokens 里的值。

```
A clean, elegant presentation background, 16:9 wide. The dominant color is a
fresh pale SKY BLUE #{{TOP}} at the top, smoothly vertical-gradient to warm
off-white #{{BOTTOM}} at the bottom — exactly these two colors. Overall
impression is crisp light blue and airy; absolutely NOT beige, NOT kraft paper,
NOT yellow overall. Only around the four corners and outer edges: very soft
out-of-focus glowing bokeh light spots in pale cyan, soft pink and pale yellow
(heavy blur, low opacity), a subtle fine 1px dot-grid texture, a few tiny
four-point sparkle stars, and gentle soft light washes. The central 70 percent
of the canvas is completely clean, empty, calm space reserved for text. Flat
editorial design, delicate, premium children-education stationery aesthetic,
extremely soft low contrast. No text, no letters, no words, no numbers, no
watermark, no people, no objects, no cards, no frames.
```

参数：`size=1536x1024`, `quality=high`, `background=opaque`。

---

## 三、模板 B · 全页背景（扁平矢量版）

```
Flat vector editorial presentation background, 16:9 wide. Smooth vertical
gradient from pale sky blue #{{TOP}} at the top to warm off-white #{{BOTTOM}}
at the bottom, crisp light blue overall, absolutely NOT beige, NOT kraft paper.
Only around the four corners and along the outer edges: scattered four-point
sparkle stars (thin elongated concave twinkle shape) in mustard yellow, soft
pink, cyan and mint green; a fine subtle 1px dot-grid texture; a thin ink-blue
outline of a magnifying glass peeking from a corner; a few short yellow
highlighter marker strokes; a couple of small hollow circles. Clean flat vector
shapes with crisp edges, cheerful refined children-education stationery style,
gentle and airy. The central 72 percent is completely empty clean space
reserved for text. No text, no letters, no words, no numbers, no watermark,
no people, no cards, no frames, no 3D.
```

**用途**：这张更适合作为 `make_background.py --overlay` 的输入，因为脚本只取它的高通纹理（装饰线条、星星、圆点），整体色调会被丢弃，风格漂移风险为零。

---

## 四、模板 C · 透明装饰贴片

```
Flat vector illustration of a single large vintage magnifying glass, ink-blue
#{{INK}} thick double circular rim, terracotta orange handle angled to
lower-right, clean white lens with a tiny pale-blue tint and a small white
glint, a subtle soft solid drop shadow. Inside the lens a short yellow
highlighter stroke over a few faint ink-blue ruled lines. Warm light and airy,
cheerful refined children-education editorial stationery style, crisp clean
outlines, generous padding around the object. Isolated centered on a fully
transparent background. No text, no letters, no words, no numbers, no
watermark, no people.
```

同类可替换主体：一叠便签卡、信纸+信封、小徽章、四角星簇。

参数：`size=1024x1024`, `quality=high`, `background=transparent`。

### ⚠ 透明背景的坑

即使申请 `background=transparent`，返回图常常是 **RGB + 浅灰白棋盘底**，不是真 alpha。直接贴进 PPT 会带一块「补丁方块」。

```bash
python3 scripts/strip_watermark.py "assets/*.png" --out-dir cleaned/ \
    --cutout --audit
```

`--cutout` 用四边连通域 flood-fill 抠背景（只删与边缘连通的部分，主体内部的白色纸卡会被保留），并做边缘羽化 + 开运算去噪。`--audit` 输出右下角对比度拉伸图，人工确认水印已清。

**验收**：输出 PNG 的透明像素占比应在 40%–85% 之间；若 < 10%，说明背景没抠掉，调大 `--tol`（默认 38）重试。

---

## 五、去水印

生图默认在**右下角**压「AI生成 / 平台名」水印。

```bash
# 透明贴片：右下角区域 alpha 清零
python3 scripts/strip_watermark.py elem.png --out-dir cleaned/ --cutout --audit

# 整张背景：不加 --cutout，脚本用「水印区上方一行渐变像素按列向下拉伸」补齐
python3 scripts/strip_watermark.py ai_bg.png --out-dir cleaned/ \
    --format jpg --quality 90
```

若水印不在右下角，用 `--wm X,Y` 调整区域起点比例（默认 `0.86,0.91`）。`--no-wm` 可完全跳过。

只有把图对比度拉伸 200 倍才显出的极淡痕迹，正常观看不可见，可接受 —— 不要为了追求绝对干净把图反复重采样。

---

## 六、成本与取舍

- 生图按张消耗积分，开工前告知用户张数与大致区间（例如 5 张约 25–50 积分）。
- **能不生图就不生图**：`decor_recipe.py` 代码渲染零积分、色值零漂移、可复现。
- 如果项目规范写了「画面由排版、SVG 与 CSS 生成，不是 AI 生成」，即便用户允许生图，也应优先代码渲染 —— 用户允许的是「手段」，不是「换风格」。
- 推荐的低成本组合：**1–2 张全页背景 + 3 个透明贴片**，其余靠 `make_background.py` 的 `--plan` 做逐页变化。

---

## 七、合成时的兜底

即使生图风格跑偏，`make_background.py` 也只取它的**高通纹理**：

```python
delta = clip(arr - gaussian_blur(arr, r=22), -70, 70) * strength
arr = exact_gradient + delta * center_fade
```

即：底色永远来自 tokens，AI 图只贡献边缘装饰的明暗变化。这是风格锁的最后一道保险。
