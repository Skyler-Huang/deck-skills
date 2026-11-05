# Deck Skills

三个可复用的 PPT 技能：**做之前定风格、做完验收、已有的稿子只美化不动风格**。

为 [DeepSeek Harness](https://github.com/deepseek-ai) 的 skill 格式编写（`SKILL.md` + `name/description` frontmatter，另支持 `whenToUse`、`license`、`compatibility`、`metadata`），也可直接放进任何读取 `skills/` 或 `AGENTS.md` 的智能体（Claude Code、Codex、Cursor、Copilot 等）。

## 技能一览

| 技能 | 什么时候用 | 关键内容 | 体积 |
|---|---|---|---|
| [`deck-design-system`](deck-design-system/SKILL.md) | 从零做一份 deck，或整份重做风格 | 两套预设（贴纸儿童风 / 温暖学院风）、字号阶梯、12 栏栅格、12 种页型、`deck_kit.py` | 5 文件 |
| [`pptx-visual-audit`](pptx-visual-audit/SKILL.md) | 任何 deck 交付前 | 字号下限、文本溢出、墨迹重叠、贴边、对比度、emoji、动画超长、整页截图；JSON 报告 + 退出码 | 3 文件 |
| [`deck-style-safe-beautify`](deck-style-safe-beautify/SKILL.md) | 已有稿子，只加背景与装饰 | 八条铁律、10 步流程、9 个脚本、独立渲染与零改动校验 | 32 文件 |

## 三个技能怎么选

一句话：**看这份稿子是不是要保留原样**。

- **新稿，允许改风格** → `deck-design-system`：选预设、上栅格、按页型搭，别手摆形状。
- **老稿，一个字一个像素都不能动** → `deck-style-safe-beautify`：风格溯源、代码渲染装饰、逐页避让、交付时用数据证明零改动。
- **两种情况都适用** → `pptx-visual-audit`：静态检查，退出码可以直接当构建门禁。

> ⚠️ 最容易混的一处：`deck-design-system` 是**允许换风格**的（它就是设计器，按预设重新排版）；`deck-style-safe-beautify` 的**第一条铁律就是不许换风格**（它是修图师，只在内容之下加装饰层）。
>
> 拿 design-system 去"美化"别人的现成稿子，结果必然是「你把我原来的风格改了」。这正是 beautify 存在的理由。

三个技能的由来：

- 前两个来自一份 20 页路演稿——被指出「风格像金融报告、字号太小、排版粘连」，于是把设计规则和验收规则分别固化成技能；token 是从产品 CSS 变量里提取的，不是凭感觉配的。
- 第三个来自一次被连续否掉四版的美化任务——换背景、贴截图、加二维码、改文件名、装饰淡到看不见。把踩过的坑写成铁律，比把技巧写进规则更值钱。

## 安装

技能就是文件夹，没有构建步骤，没有运行时，没有 SDK。

| 环境 | 路径 |
|---|---|
| DeepSeek Harness | `~/.dsh/skills/`（用户级，所有项目可用）或 `<项目>/.dsh/skills/` |
| Claude Code | `~/.claude/skills/` 或 `<项目>/.claude/skills/` |
| Codex / 通用 | `~/.agents/skills/` 或 `<项目>/.agents/skills/` |

**一次全部装上**（三个技能都是自包含目录）：

```bash
cp -r deck-design-system pptx-visual-audit deck-style-safe-beautify ~/.dsh/skills/
```

**`deck-style-safe-beautify` 也可以用它自带的安装器**（按平台选路径、跳过已存在项、清理 `__pycache__`）：

```bash
cd deck-style-safe-beautify
./install.sh --platform dsh --scope user --dry-run   # 先看会装到哪
./install.sh --platform dsh --scope user
```

`install.sh` 是纯 bash；Windows 上用 Git Bash 或 WSL 跑，或者直接按上表 `cp -r`。注意它会把技能目录里的 `README.md`、`LICENSE`、`AGENTS.md` 一并复制到目标目录，介意的话手工只拷 `SKILL.md`、`scripts`、`docs`、`references`、`assets`。

安装后重启会话（或等目录监听刷新），技能会出现在目录里，直接说「用 deck-design-system 做一份 deck」即可。

## 依赖

| 技能 | Python 包 | 系统命令 |
|---|---|---|
| `deck-design-system` | `python-pptx` | — |
| `pptx-visual-audit` | `Pillow` | —（需要字体文件，见下） |
| `deck-style-safe-beautify` | `python-pptx`、`Pillow`、`numpy` | `soffice` + `pdftoppm`（LibreOffice Impress / poppler，用于独立渲染校验，强烈建议） |

```bash
pip install -r deck-style-safe-beautify/requirements.txt
```

缺 `soffice` / `pdftoppm` 时 beautify 只能做 XML 级校验，无法证明「视觉上没有遮挡」——这一步不建议省。

## 快速开始

### 1. 验收一份现成的 PPT

```bash
python pptx-visual-audit/scripts/audit_pptx.py 你的文件.pptx
python pptx-visual-audit/scripts/audit_pptx.py 你的文件.pptx --json report.json --out report.txt
```

有 error 时退出码为 1，可直接当构建门禁：

```python
import subprocess, sys
r = subprocess.run([sys.executable, "audit_pptx.py", "deck.pptx", "--quiet"], check=False)
if r.returncode:
    raise SystemExit("deck fails the legibility floor")
```

### 2. 用设计系统搭一页

```python
import sys
sys.path.insert(0, "deck-design-system/scripts")
from deck_kit import Deck

d = Deck("sticker-kids")          # 或 "warm-academic"
s = d.new_slide()
d.bg(s)
d.title("515 处引用，逐字核对通过")
d.card(72, 258, 340, 218)
d.stat(100, 282, 290, "79/79", "篇有招", "每一篇都拆出了可用的写法")
d.save("out.pptx")
```

坐标是 1280×720 设计像素；`P(px)` / `PT(px)` 负责换算，`fit_size()` 会自动把长标题缩到框宽内。

### 3. 美化一份已有的 PPT（不动原文）

```bash
cd deck-style-safe-beautify
python3 scripts/inspect_deck.py README.pptx --out inspect.json --tokens assets/color-tokens.json
python3 scripts/render_deck.py README.pptx --out orig_pages/
python3 scripts/pick_corners.py --pages orig_pages/ --out corners.json
python3 scripts/make_background.py --tokens assets/color-tokens.json --pages 20 --plan plan.json --out backgrounds/
python3 scripts/apply_background.py README.pptx backgrounds/ --out README_beautified.pptx
python3 scripts/verify_zero_change.py README.pptx README_beautified.pptx \
    --orig-pages orig_pages/ --final-pages final_pages/ --report check.md
```

`--tokens` 是**输出**参数：`inspect_deck.py` 从原稿提取色板并落盘，后续所有绘制与校验只读这个文件，不靠记忆写十六进制。完整 10 步流程、范围确认清单和 Gotchas 见 [`SKILL.md`](deck-style-safe-beautify/SKILL.md)，细节在它的 `docs/` 下。

## 目录结构

```
deck-design-system/
├── SKILL.md                   工作流、硬规则、反模式
├── assets/tokens.json         两套预设 + 字号阶梯 + 12 栏栅格
├── references/page-types.md   12 种页型（含线框与字数预算）
├── references/typography.md   字号表、中英混排、断行、对比度
└── scripts/deck_kit.py        bg / card / pill / stat / title / text …

pptx-visual-audit/
├── SKILL.md                   检查项、阈值、怎么读输出
├── references/checks.md       每项检查的度量方式与误报说明
└── scripts/audit_pptx.py      审计脚本（无第三方依赖，除 Pillow）

deck-style-safe-beautify/
├── SKILL.md                   八条铁律 + 10 步流程
├── AGENTS.md                  持久规则（可注入工作区指令）
├── skill.json                 机器可读清单（平台、依赖、脚本用途）
├── install.sh                 多平台安装器（bash）
├── scripts/                   inspect / render / verify_zero_change / pick_corners /
│                              decor_recipe / make_background / apply_background /
│                              strip_watermark / inject_transitions
├── docs/                      workflow / guardrails / anti-patterns /
│                              platform-compat / ooxml-notes
├── references/                imagegen-prompts / color-tokens / checklist
├── assets/                    color-tokens.example.json（仅格式示例，换稿必须重新提取）
└── examples/case-study.md     一次真实任务的复盘
```

## 跨平台字体

审计用真实字体度量来估算文字占位，所以需要能找到字体文件。查找顺序：

1. 环境变量 `DECK_FONT_DIRS`（多个目录用系统分隔符）
2. `--font-dir` 参数（可重复）
3. 平台默认：Windows `C:\Windows\Fonts`；macOS `/System/Library/Fonts`、`/Library/Fonts`、`~/Library/Fonts`；Linux `/usr/share/fonts`、`~/.fonts` 等

```bash
DECK_FONT_DIRS=/path/to/fonts python audit_pptx.py deck.pptx
python audit_pptx.py deck.pptx --font-dir ./fonts --font-dir ~/fonts
```

找不到某个字体时不会中断，会回退到可用字体并在报告里列出：

```text
Fonts not found: 幼圆 — these runs were measured with a fallback face, expect a few percent error.
```

中文 deck 建议装：思源黑体 / Noto Sans CJK / 微软雅黑 / 幼圆（Windows 自带），否则中文字符宽度会按回退字体估算，误差几个百分点。

## 加一套自己的风格

不要改现有预设，往 `deck-design-system/assets/tokens.json` 里加一项：

```json
"my-brand": {
  "label": "我的品牌",
  "useFor": "什么场合用",
  "avoidFor": "什么场合别用",
  "background": { "type": "linear", "angle": 90, "stops": [["#FFFFFF", 0], ["#F5F5F5", 1]] },
  "ink": "#111111",
  "inkSoft": "#555555",
  "surface": "#FFFFFF",
  "paper": "#FAFAFA",
  "accents": { "primary": "#0066CC" },
  "accentsText": { "primary": "#004C99" },
  "radiusPx": { "lg": 12, "md": 8, "sm": 4, "pill": 999 },
  "shadow": { "x": 0, "y": 2, "blur": 8, "color": "#000000", "alpha": 0.12 },
  "fonts": { "display": "Arial", "body": "Arial", "numeric": "Arial", "mono": "Consolas" }
}
```

`accents` 用于填充，`accentsText` 用于文字（保证 4.5:1 对比度）。

## 三个设计决定

- **叠字按墨迹算，不按文本框算。** PPT 的文本框通常比文字高 2–3 倍，按框判重叠会把「没事」报成「粘连」。脚本用字体步进、行数、对齐和垂直锚点估算实际着色区域。
- **字号下限是硬门槛，不是建议。** 正文 18pt、标签 13pt。投影到 8 米外时，13pt 已经接近可读极限；文档式的 9–11pt 在后排等于没有。
- **美化只加一层，且必须证明没动原文。** 装饰是每页位于内容之下的单张全页图，原有对象的 XML 保持不变；用 LibreOffice 独立渲染做像素级对比，中心文字区差异接近 0 才算通过。

## 限制

- 审计是静态的：不做渲染，抓不到「不好看」，只能抓「不合格」；看过渲染图才算验收完成。
- 图表与 SmartArt 里的文字不遍历，需要人眼检查。
- 度量是估算，字体回退会带来几个百分点的偏差，不要把文本框卡到像素级。
- 只支持 `.pptx`；Keynote / Google Slides 请先导出。
- 美化不做内容重构：要从零改设计，请走 `deck-design-system`。
- 手写 OOXML 的产物不保证在 Microsoft PowerPoint 里 100% 兼容，交付时请在目标软件里打开确认。

## License

MIT，见 [LICENSE](LICENSE)。
