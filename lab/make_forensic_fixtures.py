"""Fixtures for the Kotlin port test (app/meterocr/src/test/.../ForensicReaderTest.kt).

Writes 5 fixed line crops as raw ARGB (.argb) + expected.txt produced by lab/forensic_reader.py on the PNG-decoded pixels.
These 5 test photos are used only as a code-equivalence check (Python == Kotlin), never for training or tuning.
Format per line: name|text|status|cls:conf:x1,y1,x2,y2:abcdefg;...   (floats with 6 decimals)
Usage: python3 make_forensic_fixtures.py
"""
import json

import cv2
import numpy as np

import forensic_reader as fr
import gt
import paths

NAMES = ["23066.jpg", "23070.jpg", "23082.jpg", "23091.jpg", "23108.jpg"]
FIX_H = 144                        # fixtures are downscaled (small repo); the reader is size-independent
OUT = paths.REPO / "app/meterocr/src/test/resources/forensic"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lines = json.load(open(paths.LINE_BOXES))
    rows = []
    for n in NAMES:
        im = cv2.imread(gt.PHOTOS + n)
        H, W = im.shape[:2]
        x1, y1, x2, y2 = lines[n]
        crop = im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)]
        crop = cv2.resize(crop, (crop.shape[1] * FIX_H // crop.shape[0], FIX_H), interpolation=cv2.INTER_AREA)
        # raw fixture: int32 w, int32 h (big-endian), then h*w big-endian ARGB ints (no image codec in unit tests)
        raw = OUT / n.replace(".jpg", ".argb")
        h, w = crop.shape[:2]
        argb = (0xFF << 24) | (crop[..., 2].astype(np.uint32) << 16) | (crop[..., 1].astype(np.uint32) << 8) | crop[..., 0]
        raw.write_bytes(np.array([w, h], ">i4").tobytes() + argb.astype(">u4").tobytes())
        png = raw
        r = fr.read_line(crop)
        ds = ";".join(f"{d['cls']}:{d['conf']:.6f}:{','.join(f'{v:.6f}' for v in d['box'])}:{''.join(map(str, d['segments']))}"
                      for d in r["digits"])
        rows.append(f"{png.name}|{r['text']}|{r['status']}|{ds}")
        print(rows[-1][:120])
    (OUT / "expected.txt").write_text("\n".join(rows) + "\n")


if __name__ == "__main__":
    main()
