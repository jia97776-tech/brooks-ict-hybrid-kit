#!/usr/bin/env bash
# 三端同步：~/.claude/skills/brooks-ict-hybrid 为 source of truth。
# 改完 claude 侧后跑 ./sync.sh "commit message"，自动提交并让 codex/grok 两端 pull。
set -euo pipefail

SRC="$HOME/.claude/skills/brooks-ict-hybrid"
MSG="${1:-sync $(date +%F)}"

cd "$SRC"
if [[ -n "$(git status --porcelain)" ]]; then
  git add -A
  git commit -m "$MSG"
fi

for dst in "$HOME/.codex/skills/brooks-ict-hybrid" "$HOME/.grok/skills/brooks-ict-hybrid"; do
  git -C "$dst" pull -q --ff-only
  echo "synced: $dst -> $(git -C "$dst" log --oneline -1)"
done
