#!/usr/bin/env bash
# Commit + rebase + push WITHOUT stashing (stash/pop replaces files that running trainers hold open -> "frozen" logs).
# Usage: bash lab/tools/safe_sync.sh "commit message"
set -euo pipefail
cd "$(dirname "$0")/../.."
git add -A lab/logs lab/weights benchmark/results docs STATUS.md CHANGELOG.md LESSONS.md 2>/dev/null || true
git add -A lab/*.py lab/tools lab/autotrain scripts app 2>/dev/null || true
git diff --cached --quiet || git commit -qm "$1"
git pull -q --rebase origin genspark_ai_developer
git push -q origin genspark_ai_developer
# any trainer whose stdout now points at a deleted inode: refresh the on-disk file from /proc
for pid in $(pgrep -f "erp_finetune.py train" || true); do
  f=$(readlink /proc/$pid/fd/1 2>/dev/null | sed -n 's/ (deleted)$//p') || true
  [ -n "${f:-}" ] && cp "/proc/$pid/fd/1" "$f" || true
done
git log --oneline -1
