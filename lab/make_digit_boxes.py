"""Regenerate benchmark/data/digit_boxes.json (contract §3, eval only) from the manual spans.

benchmark/data/digit_spans_manual.json: per photo [a, b, c, d, n] = left, top, right, bottom of the integer-digit run as
fractions of the line_boxes.json crop, n = number of integer digits (len of display_text before the dot). The run is split
into n equal-pitch cells. Spans were read by eye on a CLAHE view of each crop (lab/_render.py), agent B 2026-10-18.
Usage: python3 make_digit_boxes.py
"""
import csv
import json

import paths

DOC = ("per-digit boxes of the INTEGER part, normalised to the upright full photo (cv2.imread, EXIF applied) [x1,y1,x2,y2]; "
       "eval only — never train on these. Method: manual span per photo on the line_boxes.json crop (CLAHE view), split into "
       "equal-pitch cells; axis-aligned, so tilted displays (23106, 23110) are approximate (~±1/4 cell). Agent B, 2026-10-18. "
       "Generator: lab/make_digit_boxes.py")


def main():
    spans = json.load(open(paths.REPO / "benchmark/data/digit_spans_manual.json"))
    lines = json.load(open(paths.LINE_BOXES))
    gt = {r["filename"]: r for r in csv.DictReader(open(paths.GROUND_TRUTH))}
    out = {"_doc": DOC}
    for f, (a, b, c, d, n) in spans.items():
        text = gt[f]["display_text"].split(".")[0].replace("?", "")
        assert len(text) == n, (f, text, n)
        X1, Y1, X2, Y2 = lines[f]
        W, H = X2 - X1, Y2 - Y1
        boxes = [[round(X1 + (a + (c - a) * k / n) * W, 4), round(Y1 + b * H, 4),
                  round(X1 + (a + (c - a) * (k + 1) / n) * W, 4), round(Y1 + d * H, 4)] for k in range(n)]
        out[f] = {"text": text, "boxes": boxes}
    json.dump(out, open(paths.REPO / "benchmark/data/digit_boxes.json", "w"), indent=1, ensure_ascii=False)
    print(len(out) - 1, "photos")


if __name__ == "__main__":
    main()
