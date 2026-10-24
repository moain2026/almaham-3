#!/usr/bin/env bash
# Auto-commit + push EVERYTHING produced by training (weights .pt, logs, results JSON, docs) to branch auto-training.
# Idempotent; safe to call every cycle. Never pushes photos (gitignored) or secrets (grep guard).
# Usage: bash lab/autotrain/auto_push.sh "<message>"
set -uo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd); cd "$ROOT"
BR=${AUTO_BRANCH:-auto-training}
MSG=${1:-"auto: $(hostname) $(date -u +%FT%H:%MZ)"}
git config user.name  >/dev/null || git config user.name "autotrain-$(hostname)"
git config user.email >/dev/null || git config user.email "autotrain@almaham.local"
git fetch -q origin "$BR" 2>/dev/null || true
cur=$(git rev-parse --abbrev-ref HEAD)
if [ "$cur" != "$BR" ]; then
  git checkout -q -B "$BR" 2>/dev/null || { echo "[auto_push] cannot checkout $BR"; exit 1; }
fi
git add -f lab/weights/*.pt lab/logs/*.log benchmark/results/engines/*.json benchmark/results/engines/*.csv docs/training-log/*.md STATUS.md lab/autotrain/ 2>/dev/null
git add -A docs 2>/dev/null
# secret guard
if git diff --cached | grep -qE "ghp_[A-Za-z0-9]{20,}|BEGIN OPENSSH PRIVATE KEY"; then echo "[auto_push] STOP secret in diff"; git reset -q; exit 9; fi
git commit -q -m "$MSG" 2>/dev/null || true
# merge remote auto-training (other machine) without losing anything; ours wins on conflicts in logs
git pull -q --no-rebase -X ours origin "$BR" 2>/dev/null || true
for i in 1 2 3; do git push -q origin "$BR" && { rm -f "$ROOT/lab/autotrain/state/PUSH_FAILED"; echo "[auto_push] pushed $BR $(git rev-parse --short HEAD)"; exit 0; }; sleep 10; git pull -q --no-rebase -X ours origin "$BR" 2>/dev/null; done
# visible alarm: the results page shows this file (LESSONS 2026-10-24: 64 cycles pushed into the void unnoticed)
mkdir -p "$ROOT/lab/autotrain/state"; echo "$(date -u +%FT%TZ) $(hostname) push to $BR FAILED (pending $(git rev-list --count origin/$BR..HEAD 2>/dev/null || echo ?) commits)" >> "$ROOT/lab/autotrain/state/PUSH_FAILED"
echo "[auto_push] push failed"; exit 1
