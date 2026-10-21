#!/usr/bin/env bash
# Preserve EVERYTHING a training/eval round produced so nothing dies with the sandbox (owner rule, 2026-10-21).
#   public repo (almaham-3):   final weights lab/weights/<tag>.pt (~1 MB), benchmark/results/engines/*<tag>*, logs text
#   private repo:              weights_archive/<tag>/ (all checkpoints incl. intermediate), logs_archive/<tag>/,
#                              results_archive/<tag>/ (data/review/e2e_<tag> review images = customer crops), ft report
# Usage: bash scripts/archive_run.sh <tag>        e.g. ft5p
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); TAG=${1:?tag}
PRIV=${PRIVATE_DATA_DIR:-$ROOT/../almaham-3-private-data}
cd "$ROOT"
mkdir -p "$PRIV/weights_archive/$TAG" "$PRIV/logs_archive/$TAG" "$PRIV/results_archive/$TAG"
# 1) weights + logs + review images -> private
cp -f lab/weights/*"$TAG"*.pt "$PRIV/weights_archive/$TAG/" 2>/dev/null || true
cp -f lab/logs/*"$TAG"*.log "$PRIV/logs_archive/$TAG/" 2>/dev/null || true
[ -d "data/review/e2e_$TAG" ] && mkdir -p "$PRIV/results_archive/$TAG/review_e2e" && cp -r "data/review/e2e_$TAG"/. "$PRIV/results_archive/$TAG/review_e2e/" || true
ls data/erp/ft/"$TAG"_report.json >/dev/null 2>&1 && cp -f data/erp/ft/"$TAG"_report.json "$PRIV/results_archive/$TAG/" || true
( cd "$PRIV/weights_archive/$TAG" && sha256sum *.pt > SHA256SUMS 2>/dev/null ) || true
bash scripts/private_data.sh push-dir "$PRIV/weights_archive/$TAG" "weights_archive/$TAG" >/dev/null
bash scripts/private_data.sh push-dir "$PRIV/logs_archive/$TAG" "logs_archive/$TAG" >/dev/null
bash scripts/private_data.sh push-dir "$PRIV/results_archive/$TAG" "results_archive/$TAG" >/dev/null
# 2) public: final weights, result jsons/csvs, logs (text only) — commit left to caller with a meaningful message
git add -f lab/weights/*"$TAG"*.pt lab/logs/*"$TAG"*.log benchmark/results/engines/*"$TAG"* 2>/dev/null || true
echo "[archive] $TAG -> private (weights/logs/review) + staged in public. Now: git commit && git pull --rebase && git push"
