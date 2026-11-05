---
name: deck-style-safe-beautify
description: "Beautify an existing PowerPoint deck WITHOUT changing its text, layout, shapes, color scheme, or filename. Use when a user asks to 美化 / 配图 / 加背景 / 加装饰 a .pptx, or to make slides prettier with themed backgrounds and illustrations while keeping the original style — even if they only say 美化一下 or 加点配图. Enforces style-lock, semantic decoration, automatic corner avoidance, independent-render verification, and a provable zero-change report. Also use when a user complains that a previous beautification changed the style, added unwanted screenshots/QR codes, or was too subtle to notice. Not for creating a deck from scratch, rewriting content, or redesigning the layout."
license: MIT
compatibility: "Requires Python 3.9+, python-pptx, Pillow, numpy; LibreOffice (soffice) + poppler-utils (pdftoppm) for independent rendering; optional: an image-generation tool and git/network for style sourcing."
metadata:
  author: community
  version: "1.0.0"
  category: document-beautification
---

# PPT 保风格美化

> **目标**：在不改文字、不改排版、不改整体框架、不改背景风格、不改文件名的前提下，把一份已有 `.pptx` 美化到「明显看得出来且美观」，并**用数据证明零改动**。

这套流程来自一次真实的、被用户连续否掉四版才做对的任务。前四版分别错在：换了背景风格、擅自贴产品截图和二维码、改了文件名、装饰淡到看不见。**把踩过的坑写进规则，比把技巧写进规则更重要**。

---

## 一、铁律（违反任意一条即返工）

1. **不换背景风格**。用户说"贴近我的风格"就是字面意思。不要因为"更好看"就换底色、换渐变、换纸质纹理。底色色值必须与原稿逐字一致。
2. **不改文件名**。交付文件名必须与输入一致（尤其是「学校-姓名-作品名」这类有格式要求的文件名）。要出新版就另存，不覆盖式改名。
3. **不擅自新增内容块**。产品截图、二维码、页眉胶囊、进度条、新的文字卡片——只要用户没明确点头，一律不加。前几轮的返工全栽在这里。
4. **不改变原有对象**。任何原有形状的位置、尺寸、填充、渐变、描边、透明度、文字、层级都不动；页面级背景（`p:bg`）不设置；原稿的渐变底板形状不能改成 `noFill`。
5. **先确认范围，再动手**。把可选做法列成编号项让用户勾选（例如：①语义装饰 ②切换动效 ③色质微调 ④背景节奏），用户没选的一律不做。不要"顺手多做一些"。
6. **风格溯源优先于凭空创作**。先找项目源码 / 在线产品 / 原稿自带截图，读它的色板与视觉语言。很多项目明确写「画面由排版、SVG 与 CSS 生成，不是 AI 生成」——这种情况下用 AI 生图就是跑偏。
7. **装饰必须看得出来，但不能抢主视觉**。太淡等于没做，太浓等于改版。判断标准：并排对比时四角能明确指出新增了什么，中部正文区渲染差异接近 0。
8. **不碰原有动画**（`p:timing`）。手写动画 XML 极易让 PowerPoint 提示"需要修复"。只加切换动效（`p:transition`），保留全部原始动画。

---

## 二、何时用 / 何时不用

**用**：用户给了一份已有 `.pptx`，要求美化、配图、加背景、加装饰、做得更好看；或抱怨上一版改了风格 / 加了多余东西 / 美化不明显。

**不用**：从零做 PPT、改文案、重排版、做内容重构、把 PPT 转成别的格式。用户明确说"重做一版设计"时，本技能的零改动护栏反而是束缚，应另走设计流程。

---

## 三、环境依赖

| 依赖 | 用途 | 缺失时 |
|---|---|---|
| Python 3.9+ / `python-pptx` / `Pillow` / `numpy` | 解析、绘制、校验 | 必需 |
| `soffice`（LibreOffice Impress）+ `pdftoppm` | **独立渲染验证** | 强烈建议；缺失时只能做 XML 校验，不能证明视觉无遮挡 |
| `git` / 网络 | 风格溯源（GitHub 项目、在线产品） | 可降级为"只读原稿自带元素" |
| 生图工具 | 可选的背景/配图 | 用户允许生图时才用；不用生图也能完成 |

统一用 `scripts/` 下的脚本，不要临时手写一次性代码——脚本本身就是这套方法论的可执行版本。

---

## 四、流程（10 步，按顺序）

### Step 0 · 范围确认（强制，不可跳过）
向用户列出可选项并请其勾选，例如：
① 按页内容配语义装饰　② 顺带加克制切换动效　③ 统一投影/文字对比度　④ 章节背景节奏变化　⑤ 新增可见对象（页眉、进度条等）
**只做被选中的**。同时确认：是否允许生图、是否要保持文件名、装饰强度档位。

### Step 1 · 读原稿
```bash
python3 scripts/inspect_deck.py INPUT.pptx \
    --out inspect.json --tokens assets/color-tokens.json
```
输出：页数、尺寸、每页形状签名、渐变色值（含角度）、色板频次、已有图片、是否已有 `timing`/`transition`、每页文本。
**`assets/color-tokens.json` 是后续所有绘制与校验的唯一色值来源**，不要凭记忆写十六进制。

### Step 2 · 风格溯源（本技能的关键差异点）
按顺序尝试，找到就停：
1. 用户给的 GitHub 仓库 → 读 `README.md`、CSS 变量、`*.css` 组件、SVG 资源、机制图脚本里的颜色常量；
2. 用户给的在线产品 → 用浏览器走一遍主流程，截图，记录卡片/描边/投影/按钮样式；
3. 原稿自带的产品截图（常见在某几页）→ 直接作为风格与元素来源；
4. 都没有 → 只用原稿自身的色板与装饰元素，**不要发明新风格**。

产出一份「元素清单」：项目里真实存在的视觉元素（放大镜、卡片、信纸、贴纸、徽章、高亮笔触、四角星…）及其形状语言（描边粗细、圆角、实心投影、透明度）。

### Step 3 · 锁定底色
`make_background.py` 会按 `assets/color-tokens.json` 里的色值与角度**逐像素生成渐变**；AI 图只能通过 `--overlay` 贡献「高通后的装饰纹理」，绝不整张替换背景——色值一定漂。先用色板跑一张预览确认色调：
```bash
python3 scripts/decor_recipe.py --tokens assets/color-tokens.json --out base_preview.png
```
真正的逐页背景在 Step 7 一次性生成，本步只负责把色板文件锁死。

### Step 4 · 生成装饰素材
- **优先代码渲染**（项目规范说"代码渲染"时必须如此）：`scripts/decor_recipe.py` 提供四角星、放大镜线稿、圆点网格、荧光笔、胶囊贴纸、卡片、信纸等可组合的绘制函数。
- **用户允许生图时**：按 `references/imagegen-prompts.md` 写 prompt（把 Step 1 的色值逐字写进 prompt 做风格锁），生成后必须后处理：
  ```bash
  python3 scripts/strip_watermark.py "assets/*.png" --out-dir cleaned/ \
      --cutout --audit
  ```
  `--cutout` 做四边连通域 flood-fill 抠透明，`--audit` 导出右下角对比度拉伸图人工确认无残字。**透明元素常被压成浅灰白底，直接贴会出现「补丁方块」，必须抠。** 整张背景图则不加 `--cutout`，脚本会用上方渐变像素把水印区补齐。

### Step 5 · 自动避让（不要拍脑袋定角落）
```bash
python3 scripts/render_deck.py INPUT.pptx --out orig_pages/
python3 scripts/pick_corners.py --pages orig_pages/ --out corners.json
```
用**原稿真实渲染图**计算四角区域里"已有卡片/文字"的像素占比，选最空的角落。固定角落必然会在某些页压住小字或页码——这是实测踩过的坑。若某类页面右上角全稿统一留白，统一放右上反而像设计过的版式。

### Step 6 · 语义映射
把每页文本主题映射到 Step 2 的元素清单，例如：讲"卡片/招式/清单"配一叠卡片，讲"回信"配信纸信封，讲"收藏册"配册子，讲"逐字标注"配高亮引用卡。**装饰是这一页内容的注解，不是随机撒星星。**

### Step 7 · 装配（单一图层）
```bash
# plan.json: {"1":{"element":"mag","corner":"tr","stars":6}, ...}
#            可选 --overlay ai_bg.png 叠加同风格 AI 装饰纹理
python3 scripts/make_background.py --tokens assets/color-tokens.json \
    --pages 20 --plan plan.json --out backgrounds/
python3 scripts/apply_background.py INPUT.pptx backgrounds/ \
    --prefix aigc_bg_ --out OUTPUT.pptx
```
`apply_background.py` 会读取 `background_manifest.json`（或 `bg_NN.jpg` 命名），每页插入 1 张全页图并把它移到 `spTree` 中**第一个原有形状之后**；缺省原地更新并自动保留 `*.orig.pptx` 备份，检测到输入已含装饰层会直接报错要求从原稿重来。
硬性要求：
- 每页**只新增一张全页装饰图**；
- 在 `spTree` 中位置为 **第 2 位**（渐变底板之后、所有内容之前）；这样白底卡片会自然盖住装饰，装饰只从四角露出；
- 不设置 `p:bg`，不修改 `deco_bg`；
- **从原稿重新装配**，不要直接替换成品里的 `ppt/media/` 文件——多个页面可能共用同一张媒体，替换会误伤。

### Step 8 · 切换动效（仅当 Step 0 选中②）
```bash
python3 scripts/inject_transitions.py OUTPUT.pptx \
    --preset gentle --chapter-zoom 3,7,10,14,18
```
（`--remove` 可回滚；`--force` 才替换原稿已有的切换；缺省原地更新并自动备份。）
全页柔和淡入为基调，仅章节入口用推近呼应叙事。`p:transition` 必须插在 `clrMapOvr` 之后、`timing` 之前；**完整保留原 `p:timing`**；无声音、不改放映方式。星空淡入这类进入动画不加（需要用户在 PowerPoint 里手动选中对象添加）。

### Step 9 · 独立渲染 + 零改动校验（强制）
```bash
python3 scripts/render_deck.py OUTPUT.pptx --out final_pages/
python3 scripts/verify_zero_change.py INPUT.pptx OUTPUT.pptx \
    --prefix aigc_bg_ --orig-pages orig_pages/ --final-pages final_pages/ \
    --report check.md
```
必须全绿才算完成，任何一项红灯都要修到绿：

| 检查项 | 期望 |
|---|---|
| 页数 | 一致 |
| 渐变底板 `spPr` XML | 逐字一致、未被改 `noFill` |
| 新增页面级背景图 `p:bg` | 0 |
| 装饰层数量与位置 | 每页恰好 1 张、位于第 2 位 |
| 原有形状签名（位置/尺寸/渐变/填充/透明度/文字） | 20/20 页全等 |
| 文字内容变化页 / 形状数量变化页 | 0 / 0 |
| 中部正文区渲染像素差异 | 接近 0，差异>15 的像素占比 < 0.01% |
| 四周边缘带渲染差异 | 明显 > 0（证明美化看得见） |
| 用户自带图片（如某页的界面截图） | 完整保留、无遮挡 |
| 原有 `p:timing` | 100% 保留 |
| 文件名 | 与输入一致 |

### Step 10 · 交付
导出几张真实渲染预览 + 一张「原稿 vs 美化」并排对比图；附校验报告；明确告知用户「哪些没做」和「需要你在 PowerPoint/WPS 里确认的点」。**不要替用户打包票说微软系软件一定兼容手写 XML**。

---

## 五、Gotchas（实测踩过，写在这里防止重犯）

- **内置截图工具可能对同一路径缓存旧版本**，连纯红不透明矩形都返回原稿像素。不要用它验证新增图片。用 `soffice --headless --convert-to pdf` + `pdftoppm` 独立渲染，并给每次验证用新的临时文件名。
- **生图默认带右下角「AI生成」类水印**：需在底图阶段清除；可用对比度拉伸 200 倍自检残留。
- **"透明背景"生图常返回 RGB + 浅灰白棋盘底**：用连通域 flood-fill 从四边抠背景，并做边缘羽化；否则贴到 PPT 上是一块补丁。
- **装饰层放错层级会盖住文字**：预览合成图时若把装饰叠在渲染图最上层，会误判为"盖住卡片"；真实 PPT 里放在内容之下即可。
- **媒体去重陷阱**：成品里 20 页背景图可能只有 11 张唯一（多页共用同一 `r:embed`），按页替换媒体文件会连坐。永远从原稿重新装配。
- **固定角落 = 必翻车**：某一页左下角有页码和放大镜线稿、另一页横跨整页的标题框会被 bbox 误判成"满"。必须基于渲染像素拥挤度逐页选。
- **原稿自带 `p:timing`**：注入 `transition` 时顺序错了 PowerPoint 会提示修复。
- **"不改整体框架"包含不改文件名**，这条最容易被忽略。
- **用户说"不明显"时**：优先提高装饰在四角的可见度和语义关联，而不是动正文区或放大底色对比。

---

## 六、渐进披露（按需读取，不要一次性全读）

| 文件 | 何时读 |
|---|---|
| `docs/workflow.md` | 需要每一步的详细参数、输入输出、失败分支 |
| `docs/guardrails.md` | 写装配代码前、出校验报告时 |
| `docs/anti-patterns.md` | 用户否掉一版、要重做时（先看这个再动手） |
| `docs/platform-compat.md` | 安装到某个具体智能体时 |
| `docs/ooxml-notes.md` | 手写 `spTree` / `transition` / `blipFill` 时 |
| `references/imagegen-prompts.md` | 用户允许生图时 |
| `references/color-tokens.md` | 提取与锁定色板时 |
| `references/checklist.md` | 交付前逐项打勾 |
| `examples/case-study.md` | 想看一个完整的真实案例与返工轨迹 |

---

## 七、一句话原则

**用户要的是"我的这份 PPT 变好看了"，不是"你做的另一份好看的 PPT"。** 所有技术手段都服务于这个区分；所有校验都服务于证明这个区分成立。
