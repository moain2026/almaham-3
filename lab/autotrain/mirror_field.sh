#!/usr/bin/env bash
# Contabo cron (every 5 min, with publish_results.sh): mirror every owner field upload (basirapp.site/meter ->
# data/webdemo: photo + reading + feedback json) into the PRIVATE repo webdemo/field/. Owner rule 2026-10-24:
# "every small and big thing is saved on the repos; we never lose anything". Idempotent; pushes only when new files.
set -uo pipefail
SRC=/opt/almaham/almaham-3/data/webdemo; PRIV=/opt/almaham/almaham-3-private-data; DST=$PRIV/webdemo/field
export HOME=${HOME:-/root}
mkdir -p "$DST"; cp -n "$SRC"/* "$DST"/ 2>/dev/null
cd "$PRIV" || exit 1
git add webdemo/field >/dev/null 2>&1
git diff --cached --quiet && exit 0
n=$(git diff --cached --name-only | grep -c '\.jpg$')
git -c user.name=mirror-contabo -c user.email=mirror@almaham.local commit -q -m "data(webdemo/field): +$n field photos (auto-mirror $(date -u +%FT%H:%MZ))"
git pull -q --rebase origin main 2>/dev/null; git push -q origin main 2>/dev/null || echo "$(date -u +%FT%TZ) mirror push FAILED" >> /opt/almaham/almaham-3/lab/autotrain/state/PUSH_FAILED
