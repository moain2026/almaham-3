"""Evaluate seven-segment readers on reference line crops (mode L) for all 46 readable photos.

DEV = the 10 photos looked at while writing the code; HOLDOUT = the other 36 (honest number).
Usage: python3 eval_sevenseg.py sevenseg2
"""
import importlib
import json
import sys
import time

import cv2

import gt
import paths

DEV = {"23066", "23113", "23070", "23082", "23068", "23069", "23078", "23090", "23102", "23107"}


def main(module):
    reader = importlib.import_module(module)
    lines = json.load(open(paths.LINE_BOXES))
    rows = []
    for it in gt.load():
        if not it.readable:
            continue
        im = cv2.imread(gt.PHOTOS + it.name)
        H, W = im.shape[:2]
        x1, y1, x2, y2 = lines[it.name]
        crop = im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)]
        t0 = time.perf_counter()
        value, confs, info = reader.read_line(crop)
        ms = (time.perf_counter() - t0) * 1000
        rows.append({"file": it.name, "truth": it.reading, "value": value, "ok": value == it.reading,
                     "min_conf": round(min(confs), 2) if confs else None, "ms": round(ms, 1),
                     "dev": it.name[:5] in DEV, "difficulty": it.difficulty, "info": info})
    for name, sel in (("DEV", True), ("HOLDOUT", False)):
        r = [x for x in rows if x["dev"] == sel]
        print(f"{name}: {sum(x['ok'] for x in r)}/{len(r)}")
    ok = sum(x["ok"] for x in rows)
    wrong_conf = sum(1 for x in rows if not x["ok"] and x["value"] and (x["min_conf"] or 0) >= 0.5)
    empty = sum(1 for x in rows if not x["value"])
    print(f"ALL: {ok}/{len(rows)}  empty {empty}  wrong&conf>=0.5 {wrong_conf}  "
          f"p50 {sorted(x['ms'] for x in rows)[len(rows)//2]}ms (sandbox)")
    paths.ensure_dirs()
    json.dump(rows, open(paths.RESULTS_ENGINES / f"{module}_lineL.json", "w"), ensure_ascii=False, indent=0)
    for x in rows:
        if not x["ok"]:
            print(f"  {x['file'][:5]} {x['difficulty']:5s} truth={x['truth']:>6s} got={x['value']:>7s} "
                  f"conf={x['min_conf']} {x['info']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "sevenseg2")
