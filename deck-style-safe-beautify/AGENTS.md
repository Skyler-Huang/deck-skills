# AGENTS.md

本目录是一个 **Agent Skill**（`deck-style-safe-beautify`），位于一个多技能仓库中，与 `deck-design-system`、`pptx-visual-audit` 并列。供所有读取本文件的智能体使用的持久规则。

## 硬规则

- 当用户要求美化一份已有 `.pptx`，或抱怨上一版美化改了风格 / 加了多余东西 / 太不明显时，**读取 `SKILL.md` 并严格按其流程执行**。
- 不要修改用户的文字、排版、形状、配色、背景风格或文件名；不要擅自新增产品截图、二维码、页眉等可见内容块。
- 不要凭空发明视觉风格；先做风格溯源（GitHub 项目 / 在线产品 / 原稿自带截图）。
- 不要使用会缓存旧版本的截图工具验证新增内容；用 `scripts/render_deck.py` 做独立渲染。
- 不要跳过 `scripts/verify_zero_change.py`；校验未全绿不得宣称完成。
- 不要替用户确认微软系软件对手写 OOXML 的兼容性，交付时明确提示其自行打开验证。
- 动手前先让用户勾选允许的范围，未选中的项一律不做。
- 写规则，别写教程：完整流程在 `SKILL.md`，细节在 `docs/`，本文件只保留约束。

## 环境

- Python 3.9+，`python-pptx`、`Pillow`、`numpy`。
- `soffice` + `pdftoppm`（独立渲染与像素校验）。
- 可选：生图工具、`git` / 网络（风格溯源）。

## 命令

```bash
python3 scripts/inspect_deck.py INPUT.pptx --out inspect.json \
    --tokens assets/color-tokens.json
python3 scripts/render_deck.py INPUT.pptx --out orig_pages/
python3 scripts/verify_zero_change.py INPUT.pptx OUTPUT.pptx \
    --orig-pages orig_pages/ --final-pages final_pages/ --report check.md
for f in scripts/*.py; do python3 "$f" --help >/dev/null; done   # 全部脚本均支持 --help
```

首次接触本任务请先读 `SKILL.md`（含完整 10 步流程与 Gotchas），再按需读 `docs/`。
