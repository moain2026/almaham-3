"""Agent D — review sheets for the human/agent visual layer (layer 5 = my own eyes), WITHOUT showing VLM answers.

Usage: python3 review_sheet.py <list.txt> <out_dir> [per_sheet=6] [y0=0.05] [y1=0.60]
  For each photo: CLAHE-enhanced crop of rows y0..y1 of the photo (where the LCD is), 640 px wide, numbered #k.
  Writes out_dir/sheet_NNN.jpg and out_dir/index.csv (k,filename).
"""
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[4]
PH = REPO / "data" / "erp" / "photos"


def view(img, y0, y1, w=640):
    H = img.shape[0]
    c = img[int(H * y0): int(H * y1)]
    s = w / c.shape[1]
    c = cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    lab = cv2.cvtColor(c, cv2.COLOR_BGR2LAB)
    lab[..., 0] = cv2.createCLAHE(2.0, (8, 8)).apply(lab[..., 0])
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def main():
    names = [Path(x.strip()).name for x in open(sys.argv[1]) if x.strip()]
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    per = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    y0 = float(sys.argv[4]) if len(sys.argv) > 4 else 0.05
    y1 = float(sys.argv[5]) if len(sys.argv) > 5 else 0.60
    idx = []
    for si in range(0, len(names), per):
        tiles = []
        for k, n in enumerate(names[si:si + per]):
            img = cv2.imread(str(PH / n))
            if img is None:
                continue
            v = view(img, y0, y1)
            v = cv2.copyMakeBorder(v, 34, 4, 2, 2, cv2.BORDER_CONSTANT, value=(0, 0, 0))
            cv2.putText(v, f"#{si + k}", (6, 26), 0, 0.9, (0, 255, 255), 2)
            tiles.append(v)
            idx.append((si + k, n))
        h = max(t.shape[0] for t in tiles)
        tiles = [cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT) for t in tiles]
        while len(tiles) % 3:
            tiles.append(np.zeros_like(tiles[0]))
        rows = [np.hstack(tiles[i:i + 3]) for i in range(0, len(tiles), 3)]
        cv2.imwrite(str(out / f"sheet_{si // per:03d}.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])
    with open(out / "index.csv", "w", newline="") as f:
        csv.writer(f).writerows([("k", "filename")] + idx)
    print(f"{(len(names) + per - 1) // per} sheets -> {out}")


if __name__ == "__main__":
    main()
