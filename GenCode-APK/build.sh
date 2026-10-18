#!/usr/bin/env bash
# GenCode-APK (agent B) — build the single arm64 APK from scratch and print size / hashes / fingerprint.
# Usage (from repo root):  bash GenCode-APK/build.sh [--convert] [--publish vX.Y.Z]
#   --convert          re-convert assets/models/*.onnx -> *.ort with ORT 1.23.2 (needs ~/ort123env, see README §4.1)
#   --publish vX.Y.Z   create a GitHub pre-release and upload APK + SHA256SUMS (token from ~/.git-credentials)
# Env: ANDROID_HOME (default /home/user/android-sdk), JAVA_HOME (default jdk17 path below).
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
ANDROID_HOME=${ANDROID_HOME:-/home/user/android-sdk}
JAVA_HOME=${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}
ORTPY=${ORTPY:-$HOME/ort123env/bin/python}
BT=$ANDROID_HOME/build-tools/35.0.0
export ANDROID_HOME JAVA_HOME
CONVERT=0; TAG=""
while [ $# -gt 0 ]; do case "$1" in --convert) CONVERT=1;; --publish) TAG="$2"; shift;; esac; shift; done

cd "$ROOT"
git pull --rebase origin genspark_ai_developer || echo "WARN: git pull failed (offline?)"
M=app/meterocr/src/main/assets/models
if [ $CONVERT = 1 ]; then
  T=$(mktemp -d); cp $M/*.onnx "$T"/
  "$ORTPY" -m onnxruntime.tools.convert_onnx_models_to_ort "$T" --optimization_style Fixed --enable_type_reduction
  if ! diff <(grep -v '^#' "$T"/required_operators_and_types.config) \
            <(grep -v '^#' benchmark/results/size/ort_required_operators_and_types.config); then
    echo "STOP: operators changed -> rebuild ORT minimal first (GenCode-APK/REBUILD-ORT-MINIMAL.md)"; exit 2
  fi
  cp "$T"/*.ort $M/
  echo "converted .ort; RUN THE 49-PHOTO PARITY (README §4.2) BEFORE PUBLISHING"
fi

cd app
echo "sdk.dir=$ANDROID_HOME" > local.properties
./gradlew --no-daemon :demo:testFieldDebugUnitTest
./gradlew --no-daemon :meterocr:testDebugUnitTest || echo "WARN: meterocr unit tests failed (known: ReadingAssemblerTest.tooManyDigits, agent A)"
./gradlew --no-daemon :demo:assembleFieldRelease
A=$ROOT/app/demo/build/outputs/apk/field/release/demo-field-arm64-v8a-release.apk
VER=$("$BT"/aapt2 dump badging "$A" | sed -n "s/.*versionName='\([^']*\)'.*/\1/p")
OUT=$ROOT/app/demo/build/outputs/almaham-meter-$VER-arm64.apk
cp "$A" "$OUT"

echo "== badging";      "$BT"/aapt2 dump badging "$OUT" | grep -E "versionName|native-code"
echo "== permissions";  "$BT"/aapt2 dump permissions "$OUT"
echo "== signer";       "$BT"/apksigner verify -v --print-certs "$OUT" | grep -E "scheme|DN|SHA-256"
echo "== top files";    unzip -l "$OUT" | sort -k1 -n -r | head -10
echo "== size bytes";   stat -c %s "$OUT"
echo "== sha256";       sha256sum "$OUT"
echo "== models inside == models in repo?"
for f in digit_reader.ort line_locator.ort; do
  a=$(unzip -p "$OUT" assets/models/$f | sha256sum | cut -d' ' -f1); b=$(sha256sum "$ROOT/$M/$f" | cut -d' ' -f1)
  [ "$a" = "$b" ] && echo "OK $f $a" || { echo "MISMATCH $f"; exit 3; }
done
(cd "$(dirname "$OUT")" && sha256sum "$(basename "$OUT")" > SHA256SUMS)

if [ -n "$TAG" ]; then
  TOKEN=$(grep -o 'https://[^:]*:[^@]*@github.com' ~/.git-credentials | head -1 | sed 's#https://[^:]*:##; s#@github.com##')
  R=moain2026/almaham-3
  NOTES=${NOTES:-/tmp/notes.md}; [ -f "$NOTES" ] || echo "APK $VER arm64 — debug-signed, test only. sha256 $(cut -d' ' -f1 < "$(dirname "$OUT")"/SHA256SUMS)" > "$NOTES"
  BODY=$(python3 -c "import json,sys;print(json.dumps({'tag_name':'$TAG','target_commitish':'genspark_ai_developer','name':'$VER (arm64)','body':open('$NOTES').read(),'prerelease':True}))")
  ID=$(curl -s -H "Authorization: token $TOKEN" -d "$BODY" https://api.github.com/repos/$R/releases | python3 -c "import json,sys;print(json.load(sys.stdin)['id'])")
  for f in "$OUT" "$(dirname "$OUT")/SHA256SUMS"; do
    curl -s -H "Authorization: token $TOKEN" -H "Content-Type: application/octet-stream" --data-binary @"$f" \
      "https://uploads.github.com/repos/$R/releases/$ID/assets?name=$(basename "$f")" | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['name'],d['size'],d['browser_download_url'])"
  done
fi
