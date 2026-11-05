# deck-style-safe-beautify · PPT 保风格美化技能

> 美化一份**已有**的 `.pptx`，但**用数据证明**：文字、排版、形状、配色、背景风格、文件名，一个都没动。

[![format](https://img.shields.io/badge/format-Agent%20Skills%2FSKILL.md-blue)]() [![license](https://img.shields.io/badge/license-MIT-green)]() [![python](https://img.shields.io/badge/python-3.9%2B-orange)]()

一个跨平台 **Agent Skill**：写给 Claude Code、Codex、DeepSeek Harness、CodeBuddy / WorkBuddy、Cursor、Copilot、Gemini CLI 以及任意读取 `AGENTS.md` 的自定义 harness。无运行时、无 SDK、无编译，纯 Markdown + Python 脚本。

---

## 为什么会有这个技能

它提炼自一次被用户**连续否掉四版**的真实 PPT 美化任务。四版分别错在：

| 版本 | 做了什么 | 用户反馈 |
|---|---|---|
| v1 | AI 生成米黄纸纹整张替换背景 | 「不要改我背景风格！你没看见产品风格与我 ppt 一样吗」 |
| v2 | 贴了产品界面截图和二维码 | 「不要擅自改我 ppt 排版，擅自加产品截图和二维码一点都不美观」 |
| v3 | 装饰压到「隐约可见」 | 「没有看得出来的美化」；还改了文件名 |
| v4 | 风格对了但装饰随机撒、与内容无关 | 「不明显」→ 要求改成按页内容配元素 |

第五版才做对。**这四版的反面清单比正面技巧更值钱**，所以 `docs/anti-patterns.md` 是这个包里最重要的文档之一。

最终方案：风格溯源到项目源码（`app.css` 锁定色板 + README 明确写「画面由排版、SVG 与 CSS 生成，不是 AI 生成」）→ 代码精确还原原稿渐变 → 按页内容配代码渲染的语义元素 → 基于真实渲染像素自动选最空角落 → 每页只加一张位于内容之下的装饰层 → LibreOffice 独立渲染 + 零改动校验。

---

## 核心原则（一句话）

> 用户要的是「**我的这份 PPT 变好看了**」，不是「**你做的另一份好看的 PPT**」。

由此推出八条铁律：不换背景风格、不改文件名、不擅自加内容块、不改变原有对象、范围先确认、风格溯源优先、装饰看得出来但不抢主视觉、不碰原有动画。详见 [`SKILL.md`](SKILL.md)。

---

## 快速开始

```bash
# 0. 装依赖
pip install python-pptx Pillow numpy
sudo apt install libreoffice-impress poppler-utils    # 独立渲染，强烈建议

# 1. 安装技能到你的智能体（以 Claude Code 项目级为例）
./install.sh --platform claude --scope project

# 2. 之后直接对智能体说：
#    「按我的风格美化这份 PPT，别改文字和排版」
# 智能体会自动加载 SKILL.md 并走完整流程
```

也可以不安装，直接把 [`SKILL.md`](SKILL.md) 的内容作为系统提示词 / 用户指令注入任意 harness，把 [`AGENTS.snippet.md`](AGENTS.snippet.md) 追加到项目的 `AGENTS.md`。

手动跑脚本同样可用（`--help` 查看全部参数；完整 10 步命令序列见 [`docs/workflow.md`](docs/workflow.md)）：

```bash
python3 scripts/inspect_deck.py deck.pptx \
    --out inspect.json --tokens assets/color-tokens.json
python3 scripts/render_deck.py deck.pptx --out orig_pages/
python3 scripts/verify_zero_change.py deck.pptx deck-beautified.pptx \
    --orig-pages orig_pages/ --final-pages final_pages/ --report check.md
```

---

## 安装

### 一键安装

```bash
./install.sh --platform all --scope project --dry-run   # 先看会写到哪
./install.sh --platform all --scope project            # 实际安装
./install.sh --platform claude --scope user            # 只装给 Claude Code 个人级
./install.sh --platform dsh --scope project            # 只装给 DeepSeek Harness
./install.sh --uninstall --platform all --scope project
```

`--platform` 可选：`all` `claude` `codex` `dsh` `codebuddy` `cursor` `copilot` `gemini` `generic`。
`--scope`：`project`（写到当前目录）或 `user`（写到 `$HOME`）。可用 `--prefix /path` 改变安装根。

### 各平台安装路径

| 智能体 | 项目级 | 个人级 | 技能格式 |
|---|---|---|---|
| **Claude Code** | `.claude/skills/deck-style-safe-beautify/` | `~/.claude/skills/…` | `SKILL.md` |
| **OpenAI Codex** | `.agents/skills/deck-style-safe-beautify/` | `~/.agents/skills/…` | `SKILL.md`（`$name` 调用） |
| **DeepSeek Harness** | `.dsh/skills/…` 或 `.agents/skills/…` | `~/.dsh/skills/…` 或 `~/.agents/skills/…` | `SKILL.md` + `AGENTS.md` |
| **CodeBuddy / WorkBuddy** | — | `~/.codebuddy/skills/…` | `SKILL.md` |
| **Cursor** | `.cursor/skills/…` 或 `.agents/skills/…` | `~/.cursor/skills/…` | `SKILL.md` |
| **GitHub Copilot** | `.github/skills/…` 或 `.agents/skills/…` | `~/.copilot/skills/…` | `SKILL.md` |
| **Gemini CLI** | `.agents/skills/…` | `~/.gemini/skills/…` | `SKILL.md` |
| **任意自定义 harness** | 读 `AGENTS.md` | 把 `SKILL.md` 正文注入提示词 | 纯 Markdown |

> **兼容性基线**：`SKILL.md` 的 frontmatter 只使用标准字段 `name` / `description`（必填）与 `license` / `compatibility` / `metadata`（可选）。只用 `name` + `description` + 纯 Markdown 正文，在所有列出的智能体里都能加载。若某个实现对未知字段报错，删掉 frontmatter 里除前两项之外的行即可，正文不受影响。

`AGENTS.md` 是本技能目录自身的短约束文件；`AGENTS.snippet.md` 是可粘贴到你自己项目 `AGENTS.md` / `CLAUDE.md` 的片段。DeepSeek Harness 另需把 `AGENTS.md` 放到项目根或 `~/.dsh/AGENTS.md` 才作为全局工作区指令生效。

---

## 目录结构

```
deck-style-safe-beautify/          # 仓库根 = 技能目录（name 与目录名一致）
├── SKILL.md                      # 标准入口：铁律 + 10 步流程 + Gotchas
├── AGENTS.md                     # 通用智能体约束（短，规则不教程）
├── AGENTS.snippet.md             # 可粘贴到任意项目 AGENTS.md 的片段
├── skill.json                    # 机器可读 manifest（自定义 harness 用）
├── README.md                     # 本文件
├── LICENSE / CHANGELOG.md / .gitignore
├── requirements.txt             # pip 依赖（LibreOffice / poppler 为系统包）
├── install.sh                    # 多平台安装 / 卸载
├── docs/
│   ├── workflow.md               # 每一步的详细参数、输入输出、失败分支
│   ├── guardrails.md             # 零改动护栏 + 逐项校验表
│   ├── anti-patterns.md          # 四版返工的真实反面清单 ★
│   ├── platform-compat.md        # 兼容矩阵与平台差异
│   └── ooxml-notes.md            # spTree / blipFill / transition / timing 备忘
├── scripts/                      # 9 个通用脚本，全部支持 --help
│   ├── inspect_deck.py
│   ├── render_deck.py
│   ├── verify_zero_change.py
│   ├── pick_corners.py
│   ├── decor_recipe.py
│   ├── make_background.py
│   ├── apply_background.py
│   ├── strip_watermark.py
│   └── inject_transitions.py
├── references/
│   ├── imagegen-prompts.md       # 风格锁定的生图 prompt 模板
│   ├── color-tokens.md           # 色板提取与锁定方法
│   └── checklist.md              # 交付前打勾清单
├── assets/
│   └── color-tokens.example.json
└── examples/
    └── case-study.md             # 脱敏真实案例：五版返工轨迹 + 最终校验数据
```

---

## 校验报告长什么样

`verify_zero_change.py` 的输出示例（摘自 `examples/case-study.md`）：

```
页数 原/成品              : 20 / 20
渐变底板 spPr XML 逐字一致 : 20 / 20
渐变底板被改 noFill        : 0   (应 0)
新增页面级背景图 p:bg      : 0   (应 0)
装饰层位于第 2 位          : 20 / 20
原有形状数量变化页         : 0   (应 0)
文字内容变化页             : 0   (应 0)
形状签名全等页             : 20 / 20
原有 p:timing 保留         : 20 / 20
中部正文区渲染差异         : 0.596 ; 差异>15 像素占比 0.000%
四周边缘带渲染差异         : 1.114（美化可见）
→ PASS
```

---

## FAQ

**Q：不用生图也能用吗？**
能。项目规范写「代码渲染，不是 AI 生成」时**必须**不用生图；`decor_recipe.py` 提供全部装饰原语。生图只在 Step 0 用户明确允许时启用。

**Q：为什么必须用 LibreOffice 渲染？**
某些内置截图工具对同一文件路径缓存旧版本，连「纯红不透明矩形」都返回原稿像素，无法验证新增内容。`soffice` → PDF → `pdftoppm` 是独立、可复现的渲染路径。

**Q：会保证 PowerPoint 能打开吗？**
`p:transition` 是标准 OOXML，LibreOffice 转 PDF 已验证合法；但手写 XML 无法在此打包票说微软系软件一定不提示「需要修复」。技能要求交付时明确提示用户自行打开验证。若对方只要静态稿/PDF，可跳过 Step 8。

**Q：能不能顺便改一下文字/排版？**
不能，那是另一个任务。本技能的护栏就是为「一个像素都不动」设计的。

**Q：怎么贡献？**
欢迎提交新的装饰原语、新平台的安装路径、或你踩过的新坑（尤其是补进 `docs/anti-patterns.md`）。请保持 `SKILL.md` 正文 < 500 行，细节放 `docs/`。

---

## License

MIT — 见 [LICENSE](LICENSE)。可自由用于个人与商业项目、修改后重新分发。
