#!/usr/bin/env bash
# Sandbox: start N reader loops (default 2) detached; they wait for manual runs of the same kind to end.
cd "$(dirname "$0")/../.."; N=${1:-2}
for i in $(seq 1 $N); do ROLE=reader setsid nohup bash lab/autotrain/train_loop.sh >/dev/null 2>&1 < /dev/null & sleep 2; done
pgrep -fa "train_loop.sh" | grep -v pgrep | awk '{print $1}' | tr '\n' ' '; echo "loops started"
