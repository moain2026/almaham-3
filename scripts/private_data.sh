#!/usr/bin/env bash
# Private data bridge between this PUBLIC repo and the PRIVATE data repo moain2026/almaham-3-private-data (ADR-0006).
# Nothing here ever writes customer photos into the public repo. Token: ~/.git-credentials (scope: repo).
#
# Usage (from repo root):
#   bash scripts/private_data.sh pull                 # clone/update ../almaham-3-private-data, link data/photos + data/erp/photos, verify 49
#   bash scripts/private_data.sh push-49  <dir|zip>   # import the 49 test photos (dir or zip), verify sha256 49/49, commit+push
#   bash scripts/private_data.sh push-erp [dir]       # push data/erp/photos (default) in <=1.5 GB batches, writes erp/manifests/erp_photos.sha256
#   bash scripts/private_data.sh push-dir <src> <dst> # push any folder (weights_archive/, logs_archive/, phone/, results_archive/ ...)
#   bash scripts/private_data.sh status               # what is in the private repo (counts, sizes, last commits)
# Every push appends a row to MANIFEST.md in the private repo. Secrets are grepped before each push.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PRIV=${PRIVATE_DATA_DIR:-$ROOT/../almaham-3-private-data}
URL=https://github.com/moain2026/almaham-3-private-data.git
BATCH_BYTES=${BATCH_BYTES:-1500000000}   # GitHub rejects pushes > 2 GB; files > 100 MB
NOW=$(date -u +%Y-%m-%d)
cmd=${1:-}; shift || true

ensure() {
  if [ ! -d "$PRIV/.git" ]; then
    echo "[private] cloning $URL -> $PRIV"
    git clone -q "$URL" "$PRIV"
  else
    (cd "$PRIV" && git pull -q --rebase origin main)
  fi
}
no_secrets() {  # refuse to push if anything looks like a credential
  (cd "$PRIV" && ! git grep -iIE "ghp_[A-Za-z0-9]{20,}|passw(or)?d\s*[:=]|ERP_PASS\s*=\s*[^\$]" -- . ':!README.md' ':!MANIFEST.md' >/dev/null) \
    || { echo "STOP: possible secret in private repo working tree"; exit 9; }
}
manifest_row() {  # $1 path, $2 what, $3 count/size, $4 check
  python3 - "$PRIV/MANIFEST.md" "$NOW" "$1" "$2" "$3" "$4" <<'EOF'
import sys
p,now,path,what,cnt,chk=sys.argv[1:]
s=open(p,encoding='utf-8').read()
hdr="|---|---|---|---|---|---|\n"
row=f"| {now} | `{path}` | {what} | {cnt} | {chk} | وكيل |\n"
i=s.index(hdr)+len(hdr)
open(p,'w',encoding='utf-8').write(s[:i]+row+s[i:])
EOF
}
link() {  # symlink $2 -> $1 (replace plain empty dir)
  mkdir -p "$(dirname "$2")"
  if [ -L "$2" ]; then rm "$2"; elif [ -d "$2" ] && [ -z "$(ls -A "$2")" ]; then rmdir "$2"; fi
  [ -e "$2" ] || ln -s "$1" "$2"
}

case "$cmd" in
  pull)
    ensure
    link "$PRIV/photos_49" "$ROOT/data/photos"
    link "$PRIV/erp/photos" "$ROOT/data/erp/photos"
    link "$PRIV/erp/manifests" "$ROOT/data/erp/manifests"    # server indexes (agent D, 2026-10-21)
    echo "[private] 49 photos: $(ls "$PRIV/photos_49" | grep -c '\.jpg$' || true) | erp photos: $(ls "$PRIV/erp/photos" | grep -c '\.jpg$' || true)"
    bash "$ROOT/scripts/verify_photos.sh" || echo "[private] 49 photos not (fully) present yet"
    ;;
  push-49)
    SRC=${1:?dir or zip}; ensure
    T=$(mktemp -d)
    if [ -f "$SRC" ]; then unzip -q -o "$SRC" -d "$T"; else cp -r "$SRC"/. "$T"/; fi
    # take every jpg whose sha256 is in the official list, whatever folder the archive uses
    n=0
    while read -r sum name; do
      f=$(find "$T" -type f -name "$name" | head -1)
      [ -n "$f" ] || { echo "missing $name"; continue; }
      echo "$sum  $f" | sha256sum -c --quiet && cp "$f" "$PRIV/photos_49/$name" && n=$((n+1))
    done < "$ROOT/benchmark/data/photos.sha256"
    rm -rf "$T"
    echo "[private] imported $n/49 verified photos"
    ( cd "$PRIV/photos_49" && sha256sum -c --quiet "$ROOT/benchmark/data/photos.sha256" ) && echo "OK: 49/49"
    manifest_row "photos_49/" "صور الاختبار الـ49 (تقييم فقط)" "$n ملف، $(du -sh "$PRIV/photos_49" | cut -f1)" "photos.sha256 ⇒ $n/49"
    no_secrets
    (cd "$PRIV" && git add -A && git commit -q -m "data: 49 test photos ($n/49 verified against almaham-3/benchmark/data/photos.sha256)" && git push -q origin main)
    echo "[private] pushed"
    link "$PRIV/photos_49" "$ROOT/data/photos"
    ;;
  push-erp)
    SRC=${1:-$ROOT/data/erp/photos}; ensure
    [ "$(readlink -f "$SRC")" = "$(readlink -f "$PRIV/erp/photos")" ] || rsync -a --ignore-existing "$SRC"/ "$PRIV/erp/photos"/
    cd "$PRIV"
    ( cd erp/photos && find . -maxdepth 1 -type f -name '*.jpg' -printf '%f\n' | sort | xargs -r sha256sum ) > erp/manifests/erp_photos.sha256
    total=$(find erp/photos -type f -name '*.jpg' | wc -l)
    # batch commits so no single push exceeds GitHub's 2 GB limit
    acc=0; batch=1
    git add erp/manifests
    while IFS= read -r -d '' f; do
      sz=$(stat -c %s "$f"); git add "$f"; acc=$((acc+sz))
      if [ $acc -ge $BATCH_BYTES ]; then
        git commit -q -m "data(erp): photos batch $batch ($(numfmt --to=iec $acc))" && git push -q origin main && echo "[private] pushed batch $batch"
        batch=$((batch+1)); acc=0
      fi
    done < <(git ls-files -o --exclude-standard -z erp/photos)
    manifest_row "erp/photos/" "صور ERP مسمّاة (تدريب/تحقق)" "$total ملف، $(du -sh erp/photos | cut -f1)" "erp/manifests/erp_photos.sha256"
    no_secrets
    git add -A && git commit -q -m "data(erp): photos batch $batch + manifest ($total files total)" && git push -q origin main
    echo "[private] erp photos in repo: $total"
    ;;
  push-dir)
    SRC=${1:?src}; DST=${2:?dst (e.g. weights_archive/ft5)}; ensure
    mkdir -p "$PRIV/$DST" && rsync -a "$SRC"/ "$PRIV/$DST"/
    manifest_row "$DST/" "$(basename "$SRC")" "$(find "$PRIV/$DST" -type f | wc -l) ملف، $(du -sh "$PRIV/$DST" | cut -f1)" "—"
    no_secrets
    (cd "$PRIV" && git add -A && git commit -q -m "data: $DST <- $(basename "$SRC")" && git push -q origin main) && echo "[private] pushed $DST"
    ;;
  status)
    ensure; cd "$PRIV"
    for d in photos_49 erp/photos weights_archive logs_archive results_archive phone synth_samples; do
      printf "%-18s %6s files  %s\n" "$d" "$(find $d -type f ! -name .gitkeep | wc -l)" "$(du -sh $d | cut -f1)"
    done
    git log --oneline -5
    ;;
  *) sed -n '2,12p' "$0"; exit 1;;
esac
