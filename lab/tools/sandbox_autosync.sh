#!/usr/bin/env bash
# Sandbox safety net (owner 2026-10-24: "if credits run out, where did we stop?"):
# every 10 minutes commit + rebase + push whatever the trainers produced (checkpoints every 250 steps, logs),
# independent of the agent being alive. Runs detached: bash lab/tools/sandbox_autosync.sh start
# Logs to lab/logs/sandbox_autosync.log. Stops itself when no trainer has run for 2 hours (nothing new to push).
cd "$(dirname "$0")/../.."
if [ "${1:-}" = start ]; then
  pgrep -f "sandbox_autosync.sh loop" >/dev/null && { echo "already running"; exit 0; }
  setsid nohup bash "$0" loop >> lab/logs/sandbox_autosync.log 2>&1 < /dev/null &
  echo "autosync started pid $!"; exit 0
fi
[ "${1:-}" = loop ] || { echo "usage: $0 start"; exit 1; }
idle=0
while true; do
  sleep 600
  if pgrep -f "erp_finetune.py train" >/dev/null; then idle=0; else idle=$((idle+1)); fi
  msg="autosync[sandbox]: $(date -u +%FT%TZ) $(pgrep -fa 'erp_finetune.py train' | grep -oE 'weights/[^ ]+\.pt' | xargs -n1 basename 2>/dev/null | tr '\n' ' ')"
  bash lab/tools/safe_sync.sh "$msg" >/dev/null 2>&1 && echo "$(date -u +%FT%TZ) pushed $(git rev-parse --short HEAD)" || echo "$(date -u +%FT%TZ) PUSH_FAILED"
  [ $idle -ge 12 ] && { echo "$(date -u +%FT%TZ) no trainer for 2h -> exit"; exit 0; }
done
