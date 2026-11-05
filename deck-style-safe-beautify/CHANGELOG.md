# Changelog

All notable changes to this skill are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
Semantic Versioning.

## [1.0.0] - 2026-11-05

首个公开版本，从一次真实的 20 页 PPT 美化任务中提炼（该任务前四版被用户连续否掉）。

### Added

- `SKILL.md`：Agent Skills 标准入口。八条铁律、10 步流程、9 条实测 Gotchas、渐进披露索引。
- 多平台入口：`AGENTS.md`（通用约束）、`AGENTS.snippet.md`（可粘贴片段）、`skill.json`（机器可读 manifest）。
- `install.sh`：Claude Code / Codex / DeepSeek Harness / CodeBuddy-WorkBuddy / Cursor / Copilot / Gemini CLI / 通用 harness 的项目级与个人级安装、卸载、dry-run。
- 9 个通用化脚本：inspect / render / verify_zero_change / pick_corners / decor_recipe / make_background / apply_background / strip_watermark / inject_transitions。均不硬编码文件名、色值或页数。
- 方法论文档：`workflow.md`、`guardrails.md`、`anti-patterns.md`（四版返工的真实反面清单）、`platform-compat.md`、`ooxml-notes.md`。
- 参考资料：`imagegen-prompts.md`（风格锁定模板）、`color-tokens.md`、`checklist.md`、`color-tokens.example.json`。
- `examples/case-study.md`：脱敏的五版返工轨迹与最终校验数据。

### Design decisions

- frontmatter 只用标准字段，保证「只留 `name` + `description` 也能到处加载」。
- 装饰层固定置于 `spTree` 第 2 位（渐变底板之后、所有内容之前），白卡片自然盖住装饰。
- 校验以 LibreOffice 独立渲染为准，不信任可能缓存旧版本的内置截图工具。
- 不承诺微软 PowerPoint 对手写 OOXML 的兼容性，交付时强制提示用户自行验证。
