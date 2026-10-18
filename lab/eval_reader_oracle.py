"""Reader-only check on the 46 readable photos using the reference line crops (line_boxes.json) — the recogniser's
ceiling given a perfect locator. NOT an end-to-end number. Usage: python3 eval_reader_oracle.py weights/reader_v1.pt
"""
import csv
import json
import sys

import cv2
import numpy as np
import torch

import assemble
import paths
from det_model import DigitNet, READER_CLASSES, decode
from eval_e2e import RD_H, RD_W, RD_PEAK_MIN, letterbox

torch.set_num_threads(2)


def main(ckpt):
    m = DigitNet(READER_CLASSES)
    m.load_state_dict(torch.load(ckpt, map_location="cpu"))
    m.eval()
    gt = {r["filename"]: r for r in csv.DictReader(open(paths.GROUND_TRUTH, encoding="utf-8"))}
    lines = json.load(open(paths.LINE_BOXES))
    ok, wrong_conf, n, rows = 0, 0, 0, []
    for fn, (x1, y1, x2, y2) in sorted(lines.items()):
        truth = gt[fn]["reading"]
        if not truth:
            continue
        im = cv2.imread(paths.photo(fn))
        H, W = im.shape[:2]
        # pad like the app does around a located line
        lw, lh = (x2 - x1) * W, (y2 - y1) * H
        crop = im[int(max(0, y1 * H - 0.45 * lh)):int(min(H, y2 * H + 0.45 * lh)), int(max(0, x1 * W - 0.18 * lw)):int(min(W, x2 * W + 0.18 * lw))]
        ri, _, _, _ = letterbox(crop, RD_W, RD_H, centre_x=False)
        x = torch.from_numpy(cv2.cvtColor(ri, cv2.COLOR_BGR2RGB).astype(np.float32)[None])
        with torch.no_grad():
            p, s, o = m.forward_export(x)
        r = assemble.assemble(decode(p[0].numpy(), s[0].numpy(), o[0].numpy(), RD_PEAK_MIN), RD_W, RD_H)
        n += 1
        ok += r.value == truth
        wrong_conf += (r.value != "" and r.value != truth and r.confident)
        rows.append((fn, truth, r.text, r.value, r.status, r.confident, round(r.min_conf, 2)))
    for row in rows:
        print(*row, "OK" if row[3] == row[1] else "")
    print(f"reader-only (oracle line crop): exact {ok}/{n}, wrong&confident {wrong_conf}, ckpt {ckpt}")


if __name__ == "__main__":
    main(sys.argv[1])
