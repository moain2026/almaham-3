#!/usr/bin/env bash
# One-shot evaluation of a (locator.pt, reader.pt) pair on the 49 test photos (EVAL ONLY, never trains on them).
# Usage: bash eval_ckpt.sh <locator.pt> <reader.pt> <tag>
# Writes benchmark/results/engines/digitnet_<tag>_{A,B}.{json,csv}, vote_<tag>.json, locator_<tag>_real.json
set -euo pipefail
cd "$(dirname "$0")"
LOC=$1; RD=$2; TAG=$3
DIR=../data/models_$TAG; mkdir -p "$DIR"
python3 export_onnx.py "$LOC" "$RD" "$DIR" 2>&1 | grep -v Warn | tail -2
python3 eval_e2e.py "$DIR" "$TAG" 2>&1 | grep -v Warn | grep -E "^(A|B) "
python3 eval_vote.py "$DIR" "$TAG" 2>&1 | grep -v Warn | tail -3
python3 eval_locator_real.py "$LOC" "$TAG" 2>&1 | grep -v Warn | tail -2
