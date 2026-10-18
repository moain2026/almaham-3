#!/usr/bin/env bash
# Verify the 49 private test photos in $METER_PHOTOS_DIR (default data/photos) are byte-identical to the
# set used for every published number (benchmark/data/photos.sha256). Photos are NOT in git (ADR-0004).
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="${METER_PHOTOS_DIR:-data/photos}"
[ -d "$DIR" ] || { echo "missing $DIR — see docs/runbooks/setup-environment.md"; exit 1; }
( cd "$DIR" && sha256sum -c --quiet "$OLDPWD/benchmark/data/photos.sha256" ) && echo "OK: 49/49 photos match"
