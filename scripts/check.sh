#!/usr/bin/env bash
# Repository health check: lint lab code + reproduce the reference SegReader number (needs data/photos).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pyflakes lab/*.py
echo "lint OK"
if [ -d "${METER_PHOTOS_DIR:-data/photos}" ]; then
  bash scripts/verify_photos.sh
  (cd lab && python3 eval_rec.py weights/rec_w075.pt)   # expected: "exact": 15, "n": 46
fi
