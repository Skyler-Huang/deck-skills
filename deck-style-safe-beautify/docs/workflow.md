# 完整工作流（可直接复制执行）

本文是 `SKILL.md` 第四步「10 步流程」的展开版：每一步给出**真实命令、输入输出、失败分支与判定标准**。所有命令在仓库根执行；`INPUT.pptx` 是你拿到的原稿，`WORK.pptx` 是工作副本。

---

## 0. 准备与范围确认（不可跳过）

```bash
cp INPUT.pptx WORK.pptx
pip install -r requirements.txt
# 系统依赖（Ubuntu/Debian）
sudo apt-get install -y libreoffice-impress poppler-utils
```

**先问用户并等回复**，把可选项编号列出：

| 编号 | 做法 | 是否改动原有对象 |
|---|---|---|
| ① | 按页内容配语义装饰 | 否，只加背景层 |
| ② | 克制切换动效 | 否，只加 `p:transition` |
| ③ | 统一投影 / 文字对比度 | **是**，改属性 |
| ④ | 章节背景节奏变化 | 否，但改变整体观感 |
| ⑤ | 新增可见对象（页眉、进度条、页码样式） | **是**，新增内容 |

同时确认三件事：**是否允许生图**、**是否必须保持文件名**、**装饰强度档位**（隐约 / 明显 / 浓）。

> 真实教训：用户在第 3 轮明确说「一是可以的，二顺带做一下，三和四风险高边际效益低」。若当时多做了 ③④，就是又一次返工。用户没选的，一律不做。

---

## 1. 读原稿，锁色板

```bash
python3 scripts/inspect_deck.py WORK.pptx \
    --out inspect.json --tokens assets/color-tokens.json
```

输出：

- `inspect.json`：页数、尺寸（英寸）、每页形状签名、图片清单、每页文本、`has_page_bg`、`timing_pages` / `transition_pages`。
- `assets/color-tokens.json`：`background.top/bottom/angle_deg`、`ink`、`accents`、`source_palette`。

**必须人工复核 `accents`**：脚本按品牌亮色优先排序，但项目若有自定义强调色，请按项目 CSS 的顺序手工调整。详见 `references/color-tokens.md`。

失败分支：
- 找不到渐变底板形状 → `base_shape` 为 `null`，tokens 会退回内置色板。此时**必须手工从原稿取色**，不要直接用默认值（等于换了风格）。
- 底色是纯色而非渐变 → 把 `top` 和 `bottom` 填成同一个值即可。

---

## 2. 风格溯源

按优先级找，找到就停：

1. **用户给的 GitHub 仓库**：读 `README.md`、`app.css` 里的 CSS 变量、`*Component.css`、SVG 资源、生成机制图脚本里的颜色常量。
2. **用户给的在线产品**：用浏览器走一遍主流程，逐页截图，记录卡片描边粗细、圆角、投影类型、按钮颜色。
3. **原稿自带的产品截图**：直接作为风格与元素来源（常见于「应用界面」页）。
4. **都没有**：只用原稿自身的色板与装饰元素，**不发明新风格**。

产出「元素清单」：项目里真实存在的视觉元素 + 它的形状语言。示例（来自真实案例）：

| 元素 | 形状语言 |
|---|---|
| 放大镜 | 墨蓝双圈描边 + 橙色柄 + 实心偏移投影 |
| 卡片/招式卡 | 暖白纸 + 3px 墨蓝描边 + 实心墨蓝投影 |
| 胶囊贴纸 | 黄/粉/橙填充 + 墨蓝描边 + 低透明度 |
| 圆点网格 | 1px 圆点、24px 间距、极淡 |
| 四角星 | 细长凹形 twinkle，黄/粉/青/绿 |

> **关键判断**：如果项目 README 写了「画面由排版、SVG 与 CSS 生成，不是 AI 生成」，那么用 AI 生图就是跑偏，应优先 `decor_recipe.py` 代码渲染。用户后来允许生图时，也要把色值逐字写进 prompt 做风格锁。

---

## 3. 锁定底色

底色由 `make_background.py` 按 tokens **逐像素生成**，不接受生图整张替换。先跑一张预览确认色调没跑偏：

```bash
python3 scripts/decor_recipe.py --tokens assets/color-tokens.json \
    --out base_preview.png --element letter:br --stars 8
```

看一眼 `base_preview.png`：主色应是原稿那个浅蓝，不能偏米黄/牛皮纸色。

---

## 4. 生成装饰素材

**路线 A · 代码渲染（默认，零积分）**：

```bash
python3 scripts/decor_recipe.py --tokens assets/color-tokens.json \
    --out elem_preview.png --element cards3:tr --magnifier bl
```

`ELEMENTS` 当前提供：`mag` / `magnifier` / `cards` / `cards3` / `cards5` / `letter` / `badge` / `badges` / `quote` / `sticker`。需要新元素就照 `decor_recipe.py` 里的函数签名加一个绘制函数，风格保持「暖白纸 + 墨蓝描边 + 实心投影 + 彩色点缀」。

**路线 B · 用户允许生图**：按 `references/imagegen-prompts.md` 写 prompt，生成后必须后处理：

```bash
# 透明贴片元素：去水印 + flood-fill 抠透明 + 输出自检图
python3 scripts/strip_watermark.py "assets/*.png" --out-dir cleaned/ \
    --cutout --audit

# 整张背景图：只去水印（用上方渐变像素补齐），不要 --cutout
python3 scripts/strip_watermark.py ai_bg.png --out-dir cleaned/ \
    --format jpg --quality 90
```

`--audit` 会在 `cleaned/_audit/` 输出右下角对比度拉伸图，人工确认没有残字。

---

## 5. 自动避让（不要拍脑袋定角落）

```bash
python3 scripts/render_deck.py WORK.pptx --out orig_pages/
python3 scripts/pick_corners.py --pages orig_pages/ \
    --out corners.json --report corners.md
```

`render_deck.py` 走 `soffice → pdf → pdftoppm`，输出 `p1.png … pN.png`。**不要用内置截图工具做这件事**（见 `docs/anti-patterns.md` 第 1 条）。

`pick_corners.py` 用真实渲染像素算四角候选区里「与背景色差 > threshold」的像素占比，输出每页最空角落 + 全稿统计。若某个角落（常见是右上）在全稿统一留白，把所有配图统一放那里，反而像设计过的版式。

只渲染部分页做快速迭代：`--pages 1,5,12,18,20`。

---

## 6. 语义映射

把每页文本主题映射到第 2 步的元素清单，写成 `plan.json`：

```json
{
  "1":  {"element": "mag",     "corner": "tr", "stars": 5, "opacity": 0.55},
  "5":  {"element": "cards5",  "corner": "tr", "stars": 8, "opacity": 0.72},
  "12": {"element": "letter",  "corner": "tr", "stars": 7, "opacity": 0.72},
  "18": {"element": "cards3",  "corner": "tr", "stars": 6, "opacity": 0.68}
}
```

字段：`element`（`ELEMENTS` 键）、`corner`（tl/tr/bl/br）、`stars`、`opacity`、`size`、`margin`、`magnifier`（可选角落）、`dot`（是否画圆点网格）。

映射示例：讲「卡片/招式/清单」→ 一叠卡片；讲「回信」→ 信纸信封；讲「收藏册」→ 册子/徽章；讲「逐字标注」→ 高亮引用卡；封面/尾页 → 极轻星点（**别再放放大镜**，容易和原有主视觉打架）。

---

## 7. 装配（单一图层）

```bash
python3 scripts/make_background.py --tokens assets/color-tokens.json \
    --pages 20 --plan plan.json --out backgrounds/ \
    [--overlay cleaned/ai_bg.jpg --overlay-strength 0.8]

python3 scripts/apply_background.py WORK.pptx backgrounds/ \
    --prefix aigc_bg_ --no-backup
```

`make_background.py` 输出 `bg_01.jpg … bg_20.jpg` + `background_manifest.json`。`--center-clear 0.22`（默认）会把装饰层中部 alpha 乘 0，从数学上保证正文零干扰。

`apply_background.py` 的硬性行为：

- 每页恰好 1 张全页图，命名 `aigc_bg_01 …`；
- 把该图的 XML 移到 `spTree` 中**第一个原有形状之后**（即 `shapes` 序列 index 1）；
- 不设 `p:bg`、不碰 `deco_bg`；
- 输入里若已有 `aigc_bg_` 前缀的图，直接报错退出——**强制从原稿重新装配**；
- 缺省原地更新并自动备份 `*.orig.pptx`（加 `--no-backup` 可关）；
- 输出文件名若与输入不同，打印违反铁律 2 的警告。

先跑 `--dry-run` 看页↔图映射是否正确。

---

## 8. 切换动效（仅当第 0 步选中②）

```bash
python3 scripts/inject_transitions.py WORK.pptx \
    --preset gentle --chapter-zoom 3,7,10,14,18
```

- 全页 `spd="slow"` 淡入，章节入口用 `<p:zoom dir="in"/>`；
- `p:transition` 插在 `clrMapOvr` 之后、`timing` 之前；
- 原稿已有 `p:timing` 一律原样保留，绝不生成进入动画；
- 原稿已有 `p:transition` 默认跳过（`--force` 才替换）；
- `--remove` 可回滚；`--dry-run` 只看统计；
- 缺省原地更新并自动备份。

**验证**：用 `soffice --headless --convert-to pdf` 能成功转换即说明 XML 合法。沙箱里通常没有 PowerPoint/WPS，不要向用户打包票说微软系一定兼容，让用户在自己实际演示的软件里打开确认。

---

## 9. 独立渲染 + 零改动校验（强制）

```bash
python3 scripts/render_deck.py WORK.pptx --out final_pages/

python3 scripts/verify_zero_change.py INPUT.pptx WORK.pptx \
    --prefix aigc_bg_ --orig-pages orig_pages/ --final-pages final_pages/ \
    --report check.md --json check.json
```

`--orig-pages` 与 `--final-pages` 必须包含相同页码集合（用同样的 `--pages` 渲染两边）。校验项与判定标准见 `docs/guardrails.md`。

**任何一项红灯都要修到绿**，不要"差不多就行"。真实跑通的输出示例：

```
| 渐变底板 spPr XML 逐字一致 | 20 | 20 | PASS |
| 装饰层每页恰好 1 张且位于第 2 位 | 20 | 20 | PASS |
| 形状签名全等页 | 20 | 20 | PASS |
| 原有 p:timing 完整保留 | 20 | 20 | PASS |
| 中部正文区渲染差异（应≈0） | < 3.0 | 0.596 | PASS |
| 中部差异>15 的像素占比 | < 0.01% | 0.000% | PASS |
| 四周边缘带渲染差异（证明看得见） | > 0.3 | 1.114 | PASS |
**结论：PASS · 可交付**
```

注意「边缘差异 > 0.3」这一项：它证明美化**看得出来**。若这项太低，说明装饰淡到白做，回到第 4/6 步调强度；不要靠动正文区来凑。

---

## 10. 交付

1. 导出几张 `final_pages/pN.png` 作为效果预览；
2. 做一张「原稿 vs 美化」并排对比图（左右各一张同尺寸渲染，上方标注）；
3. 附 `check.md` 校验报告；
4. 明确告知**哪些没做**（用户没勾的选项）和**需要用户自己确认的点**（微软系软件打开手写 XML 是否正常）；
5. 文件名必须与输入一致；若用户要「原稿 + 美化版」两套，另存一份，不要覆盖。

---

## 附：一次性串起来的最小命令序列

```bash
cp INPUT.pptx WORK.pptx
python3 scripts/inspect_deck.py WORK.pptx --out inspect.json --tokens assets/color-tokens.json
python3 scripts/render_deck.py WORK.pptx --out orig_pages/
python3 scripts/pick_corners.py --pages orig_pages/ --out corners.json
# 人工写 plan.json（语义映射）
python3 scripts/make_background.py --tokens assets/color-tokens.json \
    --pages 20 --plan plan.json --out backgrounds/
python3 scripts/apply_background.py WORK.pptx backgrounds/ --no-backup
python3 scripts/inject_transitions.py WORK.pptx --preset gentle \
    --chapter-zoom 3,7,10,14,18 --no-backup
python3 scripts/render_deck.py WORK.pptx --out final_pages/
python3 scripts/verify_zero_change.py INPUT.pptx WORK.pptx \
    --orig-pages orig_pages/ --final-pages final_pages/ --report check.md
```
