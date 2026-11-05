# 跨平台兼容与安装

## 一、最小公分母（为什么这个包能通吃）

所有主流智能体技能的共同基线是：

> 一个目录里放一份 `SKILL.md`，文件头是 YAML frontmatter，至少含 `name` 与 `description`，正文是纯 Markdown 指令。

本包严格按此写：

```yaml
---
name: deck-style-safe-beautify
description: "Beautify an existing PowerPoint deck WITHOUT changing its text, ..."
license: MIT
compatibility: "Requires Python 3.9+, ..."
metadata:
  author: community
  version: "1.0.0"
---
```

额外字段（`license` / `compatibility` / `metadata`）在部分平台会被忽略 —— 这不影响加载，因为规范只要求读 `name` 与 `description`。**正文不依赖任何平台特有的运行时、SDK、MCP 工具或网络**：智能体只需要能读文件、执行 Python 脚本、写文件。

因此兼容性分三档：

| 档位 | 平台 | 加载方式 |
|---|---|---|
| 原生技能 | Claude Code、Codex、Cursor、GitHub Copilot、Gemini CLI、WorkBuddy/CodeBuddy | 扫描技能目录，读 `SKILL.md` |
| 指令文件 | DeepSeek Harness、通用 harness | 读项目根 `AGENTS.md` 或 `~/.dsh/AGENTS.md`，或把 `SKILL.md` 正文注入 system/user prompt |
| 纯提示词 | 任何 LLM / 本地模型 | 直接把 `SKILL.md` 贴进对话 |

> 各平台的技能目录与触发语法会随版本变化，以对应平台当前官方文档为准。本包把所有路径集中在 `install.sh` 与 `skill.json` 两处，改动只需改这两处。

---

## 二、安装路径矩阵

`skill.json` 的 `install_targets` 与 `install.sh` 保持同步：

| 平台 | 项目级 | 用户级 |
|---|---|---|
| Claude Code | `.claude/skills/deck-style-safe-beautify/` | `~/.claude/skills/deck-style-safe-beautify/` |
| Codex | `.agents/skills/deck-style-safe-beautify/` | `~/.agents/skills/` 或 `$CODEX_HOME/skills/` |
| DeepSeek Harness | `.dsh/skills/` 或 `.agents/skills/` | `~/.dsh/skills/` 或 `~/.agents/skills/` |
| WorkBuddy / CodeBuddy | — | `~/.codebuddy/skills/deck-style-safe-beautify/` |
| Cursor | `.cursor/skills/` 或 `.agents/skills/` | `~/.cursor/skills/` |
| GitHub Copilot | `.github/skills/` 或 `.agents/skills/` | `~/.copilot/skills/` |
| Gemini CLI | `.agents/skills/` | `~/.gemini/skills/` |
| 通用 harness | 项目根放 `AGENTS.md` | 把 `AGENTS.snippet.md` 追加到你的全局指令 |

**目录名必须与 frontmatter `name` 一致**（`deck-style-safe-beautify`），否则部分平台不识别。

---

## 三、安装

```bash
# 先看会做什么，不写任何文件
./install.sh --platform all --scope project --dry-run

# 项目级：给当前仓库的所有智能体装
./install.sh --platform all --scope project

# 只装某一个平台，用户级
./install.sh --platform claude --scope user

# DeepSeek Harness：同时把指令片段追加到项目根 AGENTS.md
./install.sh --platform dsh --scope project --with-agents

# 指定安装根目录（例如 monorepo 子包）
./install.sh --platform codex --prefix /path/to/subproject

# 覆盖已存在的目标
./install.sh --platform all --scope user --force

# 卸载
./install.sh --uninstall --platform all --scope project
```

`--platform` 可选：`all | claude | codex | dsh | codebuddy | cursor | copilot | gemini | generic`。

安装器会复制整个技能目录（含 `scripts/`、`docs/`、`references/`、`assets/`、`examples/`），保证脚本与文档在同一个目录内自洽。

---

## 四、各平台如何触发

| 平台 | 触发方式 |
|---|---|
| Claude Code | `/deck-style-safe-beautify`，或直接说「美化这份 PPT，别改我的文字和风格」；技能靠 `description` 自动匹配 |
| Codex | `$deck-style-safe-beautify`，或把 `AGENTS.md` 作为项目指令 |
| DeepSeek Harness | 项目根 `AGENTS.md` 自动生效；或在会话里引用 `SKILL.md` |
| WorkBuddy / CodeBuddy | 技能目录自动扫描；也可在对话里点名技能 |
| 通用 / 无技能系统 | 把 `SKILL.md` 正文作为 system prompt 注入，然后给出 PPT 路径 |

`description` 里刻意写了中英触发词（美化 / 配图 / 加背景 / 加装饰 / "make slides prettier"）和「用户抱怨上一版改了风格」这类场景，便于语义匹配。

---

## 五、上传到 GitHub 的仓库布局

推荐直接把**本目录作为仓库根**（即 `SKILL.md` 在仓库根），这样：

- 各平台 `git clone` 后可直接把仓库当技能目录用；
- `SKILL.md` 在 GitHub 仓库首页可见，等价于 README 的作用；
- `README.md` 保留给人类读者（安装说明、兼容表、目录导览）。

若你更习惯 `skills/<name>/` 的布局，也可以把本目录整体放进去，但要同步更新 `install.sh` 里的 `SRC` 与 `skill.json` 的路径说明。

`LICENSE` 是 MIT；`.gitignore` 已排除 `__pycache__/`、`*.orig.pptx`、`backgrounds/`、`*_pages/`、临时渲染产物等。

---

## 六、环境依赖（跨平台）

| 依赖 | Windows | macOS | Linux |
|---|---|---|---|
| Python 3.9+ | python.org 安装包 | brew | 系统自带 |
| `python-pptx` / `Pillow` / `numpy` | `pip install -r requirements.txt` | 同左 | 同左 |
| `soffice` | 安装 LibreOffice 并加入 PATH | `brew install --cask libreoffice` | `apt-get install libreoffice-impress` |
| `pdftoppm` | poppler for Windows | `brew install poppler` | `apt-get install poppler-utils` |

没有 LibreOffice / pdftoppm 时，`render_deck.py` 会失败，`verify_zero_change.py` 的像素校验项会被跳过 —— 此时**只能做 XML 结构校验，不能证明视觉无遮挡**，交付说明里必须如实告知。

---

## 七、自检清单（发布前）

- [ ] `SKILL.md` frontmatter 是合法 YAML，`name` == 目录名
- [ ] `python3 -m py_compile scripts/*.py` 通过
- [ ] 每个脚本 `--help` 能跑
- [ ] `./install.sh --platform all --scope project --dry-run` 输出符合预期
- [ ] 在一份真实 `.pptx` 上跑通 `inspect → render → make_background → apply → inject → verify` 且全绿
- [ ] `install.sh` 与 `scripts/*.py` 有可执行位，且 zip/tar 包保留了权限
- [ ] 没有把用户真实的 PPT、截图、姓名等敏感文件打进包里
