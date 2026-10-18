"""Real-photo recall of the LINE locator (PyTorch checkpoint) — the M3 metric for the locator.

Usage: python3 eval_locator_real.py <locator.pt> [tag]
For every photo in benchmark/data/line_boxes.json: crop the mode-A rectangle (meter_boxes.json) exactly like
eval_e2e.py, letterbox to 256x256 (mid-grey, centred), run DigitNet(1).forward_export, decode with the app
thresholds (LOC_PEAK_MIN, LINE_MIN_H from eval_e2e.py), take the TOP peak and compute IoU against the reference
main-line box mapped into the crop. Hit = IoU > 0.5. Target (M3): >= 95%.
Secondary metric recall_tight_iou50: IoU vs the union of the integer-digit boxes in digit_boxes.json — the same
definition synth2.py uses for the LINE box (line_boxes.json is a looser band, median 1.25x digit height).
The 49 photos are evaluation only — nothing here feeds training or threshold tuning.
Writes benchmark/results/engines/locator_<tag>_real.json (per-image IoU + summary).
"""
import json
import statistics as st
import sys
import time

import cv2
import numpy as np
import torch

import assemble
import paths
from det_model import DigitNet, LOCATOR_CLASSES, decode
from eval_e2e import LOC_IN, LOC_PEAK_MIN, LINE_MIN_H, letterbox, load_upright


def main(ckpt, tag):
    torch.set_num_threads(1)
    m = DigitNet(LOCATOR_CLASSES)
    m.load_state_dict(torch.load(ckpt, map_location="cpu"))
    m.eval()
    mb = json.load(open(paths.METER_BOXES))
    lb = {k: v for k, v in json.load(open(paths.LINE_BOXES)).items() if not k.startswith("_")}
    db = json.load(open(paths.BENCH_DATA / "digit_boxes.json"))  # eval-only tight per-digit boxes (contract §3)
    rows = []
    for fn, (lx1, ly1, lx2, ly2) in sorted(lb.items()):
        im = load_upright(fn)
        H, W = im.shape[:2]
        x1, y1, x2, y2 = mb[fn]
        ox, oy = int(x1 * W), int(y1 * H)
        crop = im[oy:int(y2 * H), ox:int(x2 * W)]
        ref = (lx1 * W - ox, ly1 * H - oy, lx2 * W - ox, ly2 * H - oy)
        li, s, px, py = letterbox(crop, LOC_IN, LOC_IN)
        t0 = time.perf_counter()
        with torch.no_grad():
            p, sz, of = m.forward_export(torch.from_numpy(cv2.cvtColor(li, cv2.COLOR_BGR2RGB)).float()[None])
        ms = (time.perf_counter() - t0) * 1e3
        dets = [d for d in decode(p[0].numpy(), sz[0].numpy(), of[0].numpy(), LOC_PEAK_MIN) if d[5] - d[3] >= LINE_MIN_H]
        best = max(dets, key=lambda d: d[1], default=None)
        tb = np.array(db[fn]["boxes"]) if fn in db else None
        tight = None if tb is None else (tb[:, 0].min() * W - ox, tb[:, 1].min() * H - oy, tb[:, 2].max() * W - ox, tb[:, 3].max() * H - oy)
        iou, score, iou_t, top3_t = 0.0, 0.0, 0.0, 0.0
        if best:
            box = [(v - (px if i % 2 == 0 else py)) / s for i, v in enumerate(best[2:])]
            iou, score = assemble.iou(box, ref), best[1]
            iou_t = assemble.iou(box, tight) if tight is not None else 0.0
            for dd in sorted(dets, key=lambda d: -d[1])[:3]:  # top-3 peaks: what a post-reader line choice could reach
                bb = [(v - (px if i % 2 == 0 else py)) / s for i, v in enumerate(dd[2:])]
                top3_t = max(top3_t, assemble.iou(bb, tight) if tight is not None else 0.0)
        rows.append({"file": fn, "iou": round(float(iou), 3), "iou_tight": round(float(iou_t), 3), "iou_tight_top3": round(float(top3_t), 3), "score": round(float(score), 3), "found": best is not None,
                     "ms": round(ms, 2)})
    hit = sum(r["iou"] > 0.5 for r in rows)
    summ = {"ckpt": ckpt, "argv": sys.argv, "n": len(rows), "recall_iou50": hit, "recall_pct": round(100 * hit / len(rows), 1),
            "recall_tight_iou50": sum(r["iou_tight"] > 0.5 for r in rows),
            "recall_tight_top3": sum(r["iou_tight_top3"] > 0.5 for r in rows),
            "found": sum(r["found"] for r in rows), "iou_median": round(st.median(r["iou"] for r in rows), 3),
            "ms_p50": round(st.median(r["ms"] for r in rows), 2),
            "miss": [r["file"] for r in rows if r["iou"] <= 0.5]}
    out = paths.RESULTS_ENGINES / f"locator_{tag}_real.json"
    json.dump({"summary": summ, "rows": rows}, open(out, "w"), indent=1)
    print(json.dumps(summ, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "t")
