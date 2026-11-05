#!/usr/bin/env bash
# deck-style-safe-beautify :: multi-agent installer
# Installs this Agent Skill into the directory each agent scans for skills.
# Pure POSIX-ish bash, no dependencies beyond cp/mkdir/sort.
set -euo pipefail

NAME="deck-style-safe-beautify"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PLATFORM="all"
SCOPE="project"
PREFIX=""
DRY_RUN=0
FORCE=0
UNINSTALL=0
WITH_AGENTS=0

usage() {
  cat <<'EOF'
用法: install.sh [选项]

  --platform TARGET   all | claude | codex | dsh | codebuddy | cursor |
                      copilot | gemini | generic      (默认 all)
  --scope SCOPE       project | user                   (默认 project)
  --prefix PATH       安装根目录（覆盖 scope 的默认根）
  --dry-run           只打印将要执行的动作，不写任何文件
  --force             目标已存在时覆盖（默认跳过）
  --with-agents       同时把 AGENTS.snippet.md 追加到安装根的 AGENTS.md
  --uninstall         删除已安装的目标目录
  -h, --help          显示本帮助

示例:
  ./install.sh --platform all --scope project --dry-run
  ./install.sh --platform claude --scope user
  ./install.sh --platform dsh --scope project --with-agents
  ./install.sh --uninstall --platform all --scope project
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --platform)   PLATFORM="$2"; shift 2 ;;
    --scope)      SCOPE="$2"; shift 2 ;;
    --prefix)     PREFIX="$2"; shift 2 ;;
    --dry-run)    DRY_RUN=1; shift ;;
    --force)      FORCE=1; shift ;;
    --with-agents) WITH_AGENTS=1; shift ;;
    --uninstall)  UNINSTALL=1; shift ;;
    -h|--help)    usage; exit 0 ;;
    *) echo "未知参数: $1" >&2; usage; exit 2 ;;
  esac
done

case "$PLATFORM" in
  all|claude|codex|dsh|codebuddy|cursor|copilot|gemini|generic) ;;
  *) echo "无效的 --platform: $PLATFORM" >&2; exit 2 ;;
esac
case "$SCOPE" in
  project|user) ;;
  *) echo "无效的 --scope: $SCOPE" >&2; exit 2 ;;
esac

# ---------------------------------------------------------------- 解析根目录
if [ -n "$PREFIX" ]; then
  ROOT="$PREFIX"
elif [ "$SCOPE" = "user" ]; then
  ROOT="$HOME"
else
  ROOT="$PWD"
fi

# ---------------------------------------------------------------- 目标路径表
# 格式: "相对路径|平台标签"
targets_for() {
  local p="$1"
  case "$p" in
    claude)
      [ "$SCOPE" = "user" ] && echo "$HOME/.claude/skills/$NAME|claude-code" \
                            || echo ".claude/skills/$NAME|claude-code" ;;
    codex)
      [ "$SCOPE" = "user" ] && echo "$HOME/.agents/skills/$NAME|codex" \
                            || echo ".agents/skills/$NAME|codex" ;;
    dsh)
      [ "$SCOPE" = "user" ] && echo "$HOME/.dsh/skills/$NAME|deepseek-harness" \
                            || echo ".dsh/skills/$NAME|deepseek-harness" ;;
    codebuddy)
      [ "$SCOPE" = "user" ] && echo "$HOME/.codebuddy/skills/$NAME|codebuddy-workbuddy" \
                            || echo ".codebuddy/skills/$NAME|codebuddy-workbuddy" ;;
    cursor)
      [ "$SCOPE" = "user" ] && echo "$HOME/.cursor/skills/$NAME|cursor" \
                            || echo ".cursor/skills/$NAME|cursor" ;;
    copilot)
      [ "$SCOPE" = "user" ] && echo "$HOME/.copilot/skills/$NAME|github-copilot" \
                            || echo ".github/skills/$NAME|github-copilot" ;;
    gemini)
      [ "$SCOPE" = "user" ] && echo "$HOME/.gemini/skills/$NAME|gemini-cli" \
                            || echo ".agents/skills/$NAME|gemini-cli" ;;
    generic)
      [ "$SCOPE" = "user" ] && echo "$HOME/.agents/skills/$NAME|generic-harness" \
                            || echo ".agents/skills/$NAME|generic-harness" ;;
  esac
}

if [ "$PLATFORM" = "all" ]; then
  PLATFORMS="claude codex dsh codebuddy cursor copilot gemini generic"
else
  PLATFORMS="$PLATFORM"
fi

RAW=""
for p in $PLATFORMS; do
  line="$(targets_for "$p")"
  [ -n "$line" ] && RAW="$RAW$line"$'\n'
done
# 去重路径（多个平台共用 .agents/skills/），保留第一次出现的标签
TARGETS="$(printf '%s' "$RAW" | sed '/^$/d' | awk -F'|' '!seen[$1]++')"

# ---------------------------------------------------------------- 要复制的内容
ITEMS="SKILL.md AGENTS.md AGENTS.snippet.md skill.json README.md LICENSE CHANGELOG.md requirements.txt docs scripts references assets examples"

abs_path() {
  case "$1" in
    /*|"$HOME"/*) printf '%s' "$1" ;;
    *) printf '%s/%s' "$ROOT" "$1" ;;
  esac
}

echo "技能: $NAME"
echo "来源: $SRC"
echo "根目录: $ROOT"
echo "模式: $([ "$UNINSTALL" -eq 1 ] && echo uninstall || ([ "$DRY_RUN" -eq 1 ] && echo dry-run || echo install))"
echo "------------------------------------------------------------"

n_ok=0; n_skip=0
while IFS='|' read -r rel label; do
  [ -z "$rel" ] && continue
  dest="$(abs_path "$rel")"

  if [ "$UNINSTALL" -eq 1 ]; then
    if [ -d "$dest" ]; then
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "[would remove] $dest   ($label)"
      else
        rm -rf "$dest"
        echo "[removed]     $dest   ($label)"
      fi
      n_ok=$((n_ok+1))
    else
      echo "[absent]      $dest   ($label)"
    fi
    continue
  fi

  if [ -e "$dest" ] && [ "$FORCE" -eq 0 ]; then
    echo "[skip exists] $dest   ($label)  --force 可覆盖"
    n_skip=$((n_skip+1))
    continue
  fi

  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[would install] $dest   ($label)"
    printf '                 -> %s\n' "$ITEMS"
  else
    mkdir -p "$dest"
    for item in $ITEMS; do
      if [ -e "$SRC/$item" ]; then
        if [ -d "$SRC/$item" ]; then
          mkdir -p "$dest/$item"
          cp -R "$SRC/$item/." "$dest/$item/"
        else
          cp "$SRC/$item" "$dest/$item"
        fi
      fi
    done
    # 不要把本地 Python 缓存带进技能目录
    find "$dest" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$dest" -type f -name "*.pyc" -delete 2>/dev/null || true
    echo "[installed]   $dest   ($label)"
  fi
  n_ok=$((n_ok+1))
done <<< "$TARGETS"

# ---------------------------------------------------------------- AGENTS.md 片段
if [ "$UNINSTALL" -eq 0 ] && [ "$WITH_AGENTS" -eq 1 ]; then
  agents_file="$ROOT/AGENTS.md"
  marker="deck-style-safe-beautify"
  if [ -f "$agents_file" ] && grep -q "$marker" "$agents_file"; then
    echo "[skip]        $agents_file 已包含本技能片段"
  elif [ "$DRY_RUN" -eq 1 ]; then
    echo "[would append] $agents_file <- AGENTS.snippet.md"
  else
    mkdir -p "$(dirname "$agents_file")"
    printf '\n' >> "$agents_file"
    cat "$SRC/AGENTS.snippet.md" >> "$agents_file"
    echo "[appended]    $agents_file <- AGENTS.snippet.md"
  fi
fi

echo "------------------------------------------------------------"
if [ "$UNINSTALL" -eq 1 ]; then
  echo "完成：移除 $n_ok 处，跳过 $n_skip 处。"
  echo "注意：--uninstall 不会改动项目根 AGENTS.md，请手动移除其中的片段。"
else
  echo "完成：处理 $n_ok 处，跳过 $n_skip 处。"
  echo "验证：在智能体里输入技能名（Claude Code: /$NAME，Codex: \$$NAME），或直接提出 PPT 美化请求。"
  echo "提示：DeepSeek Harness 需把 AGENTS.md 放在项目根或 ~/.dsh/AGENTS.md 才作为工作区指令生效。"
fi
