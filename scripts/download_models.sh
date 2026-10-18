#!/usr/bin/env bash
# Download the third-party PP-OCR ONNX models used by the lab benchmarks into $METER_MODELS_DIR
# (default: data/models). Every file is verified against a pinned SHA256. Apache-2.0 (PaddleOCR/RapidOCR).
set -euo pipefail
cd "$(dirname "$0")/.."
DEST="${METER_MODELS_DIR:-data/models}"; mkdir -p "$DEST"
BASE="https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.10.0/onnx"
while read -r sha rel name; do
  [ -z "$sha" ] && continue
  out="$DEST/$name"
  if [ ! -f "$out" ] || ! echo "$sha  $out" | sha256sum -c --quiet - 2>/dev/null; then
    echo "downloading $name"; curl -fL --retry 3 -o "$out" "$BASE/$rel"
  fi
  echo "$sha  $out" | sha256sum -c -
done <<'LIST'
4d97c44a20d30a81aad087d6a396b08f786c4635742afc391f6621f5c6ae78ae PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx ch_PP-OCRv5_det_mobile.onnx
5825fc7ebf84ae7a412be049820b4d86d77620f204a041697b0494669b1742c5 PP-OCRv5/rec/ch_PP-OCRv5_rec_mobile.onnx ch_PP-OCRv5_rec_mobile.onnx
c3461add59bb4323ecba96a492ab75e06dda42467c9e3d0c18db5d1d21924be8 PP-OCRv5/rec/en_PP-OCRv5_rec_mobile.onnx en_PP-OCRv5_rec_mobile.onnx
f42c0fbd294d95eac1a550e131b277dac97462c8025fa4b6c3cec1b7894bd3d5 PP-OCRv6/det/PP-OCRv6_det_tiny.onnx PP-OCRv6_det_tiny.onnx
090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f PP-OCRv6/det/PP-OCRv6_det_small.onnx PP-OCRv6_det_small.onnx
e16e242de5937ad92609223f19bc2aff3727ee40b095f996907c24749bad251b PP-OCRv6/rec/PP-OCRv6_rec_tiny.onnx PP-OCRv6_rec_tiny.onnx
6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884 PP-OCRv6/rec/PP-OCRv6_rec_small.onnx PP-OCRv6_rec_small.onnx
LIST
