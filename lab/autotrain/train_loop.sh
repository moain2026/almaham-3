#!/usr/bin/env bash
# Endless training loop (one machine). Reads recipes from lab/autotrain/queue_<role>.txt line by line:
#   <tag> | <kind reader|locator> | <init.pt> | <real_prefix> | <synth_prefixes> | <steps> | <threads> | <extra env>
# For each: train -> eval (eval_ckpt + testset_human + risk_coverage) -> archive to private -> append runs.md -> auto_push.
# When the queue is exhausted it generates a new seed of the best recipe (never idles). Survives sandbox/agent death
# (run under setsid/systemd). Everything it produces is pushed to branch auto-training every cycle.
# Usage: ROLE=reader|locator bash lab/autotrain/train_loop.sh
set -uo pipefail
export HOME=${HOME:-/root}   # systemd services have no HOME -> git finds no credentials (64 cycles lost, 2026-10-24)
ROOT=$(cd "$(dirname "$0")/../.." && pwd); cd "$ROOT/lab"; source ../.venv/bin/activate
ROLE=${ROLE:-reader}; Q=autotrain/queue_$ROLE.txt; DONE=autotrain/done_$ROLE.txt; touch "$Q" "$DONE"
LOG=logs/autotrain_$ROLE.log; exec >>"$LOG" 2>&1
echo "=== train_loop $ROLE start $(date -u +%FT%TZ) host=$(hostname)"
# do not compete with a manually started training of the same kind (e.g. Contabo locator_m3 via queue_loc_m2.sh)
while pgrep -f "erp_finetune.py train .* $ROLE\$" >/dev/null; do sleep 60; done
next_seed() { n=$(grep -c . "$DONE"); echo $((100 + n)); }
while true; do
  line=$(grep -v '^#' "$Q" | grep -v '^$' | head -1)
  if [ -z "$line" ]; then  # queue empty -> new seed of default recipe
    s=$(next_seed)
    if [ "$ROLE" = reader ]; then
      line="auto_rd_s$s | reader | weights/reader_ft6m2_s1.pt | ../data/erp/ft/ft6m3 | ../data/synth/line_s1,../data/synth/line_crystal_opt2 | 3000 | 1 | SEED=$s AUG_SEED=$s"
    else
      line="auto_loc_s$s | locator | weights/locator_m1_augv2.pt | ../data/erp/ft/m3 | ../data/synth/scene_s1 | 3000 | 3 | SEED=$s AUG_SEED=$s"
    fi
  else
    python3 - "$Q" <<'PY'
import sys; p=sys.argv[1]; L=open(p).read().split("\n"); i=next(k for k,l in enumerate(L) if l.strip() and not l.startswith("#")); L.pop(i); open(p,"w").write("\n".join(L))
PY
  fi
  IFS='|' read -r tag kind init real synth steps thr extra <<<"$line"
  tag=$(echo $tag); kind=$(echo $kind); init=$(echo $init); real=$(echo $real); synth=$(echo $synth); steps=$(echo $steps); thr=$(echo $thr); extra=$(echo $extra)
  echo "--- $(date -u +%FT%TZ) START $tag ($kind) init=$init real=$real synth=$synth steps=$steps thr=$thr env=[$extra]"
  [ -f "$init" ] || { echo "skip: init missing $init"; echo "$tag skipped" >> "$DONE"; continue; }
  env $extra AUG=v2 TORCH_THREADS=$thr python3 erp_finetune.py train "$init" "$real" "$synth" "$steps" "weights/${kind}_$tag.pt" "$kind" > "logs/train_${kind}_$tag.log" 2>&1
  rc=$?; echo "train rc=$rc $(grep '^step' logs/train_${kind}_$tag.log | tail -1)"
  if [ $rc -eq 0 ]; then
    if [ "$kind" = reader ]; then LOC=${BEST_LOC:-weights/locator_m1_augv2.pt}; RD=weights/reader_$tag.pt; else LOC=weights/locator_$tag.pt; RD=${BEST_RD:-weights/reader_ft6m2_s1.pt}; fi
    TORCH_THREADS=$thr bash eval_ckpt.sh "$LOC" "$RD" "$tag" > "logs/eval_$tag.log" 2>&1
    TORCH_THREADS=$thr python3 eval_testset_human.py "../data/models_$tag" "$tag" >> "logs/eval_$tag.log" 2>&1
    TORCH_THREADS=$thr python3 risk_coverage.py "../data/models_$tag" "$tag" >> "logs/eval_$tag.log" 2>&1
    A=$(grep -E '^A ' logs/eval_$tag.log | python3 -c "import sys,json;print(json.loads(sys.stdin.read()[2:])['exact'])" 2>/dev/null)
    B=$(grep -E '^B ' logs/eval_$tag.log | python3 -c "import sys,json;print(json.loads(sys.stdin.read()[2:])['exact'])" 2>/dev/null)
    TH=$(grep '"exact"' logs/eval_$tag.log | tail -1 | python3 -c "import sys,json;d=json.loads(sys.stdin.read());print(d['exact'],d['by_type'])" 2>/dev/null)
    RC=$(grep "min_conf>=0.55 & alt" logs/eval_$tag.log | head -1 | awk '{print "accepted",$6,"correct",$8,"wrong",$10}')
    echo "| $tag (auto) | $kind | $(basename $init) | $(basename $real) | $(basename $synth) | $steps, AUG v2, $extra | $(hostname) | $A/39 / $B | $TH | risk: $RC |" >> ../docs/training-log/runs.md
    echo "RESULT $tag: 49 A=$A B=$B | 34: $TH | $RC"
    (cd .. && bash scripts/archive_run.sh "$tag" >/dev/null 2>&1 || true)
  fi
  echo "$tag rc=$rc $(date -u +%FT%TZ)" >> "$DONE"
  (cd .. && bash lab/autotrain/auto_push.sh "auto[$(hostname)]: $tag done (49 A=$A B=$B; 34 ${TH%% *})") || true
done
