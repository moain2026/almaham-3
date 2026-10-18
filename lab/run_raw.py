"""Run engines on all 49 images in two modes (A=meter box crop, B=full) and dump raw outputs + timings."""
import paths
import cv2, json, time, sys, csv
from engines import ENGINES
SRC = paths.PHOTOS_S
boxes = json.load(open(paths.METER_BOXES))
gt = {r["filename"]: r for r in csv.DictReader(open(paths.GROUND_TRUTH))}
out = {}
for name in sys.argv[1:]:
    eng = ENGINES[name](); res = {}
    for fn in sorted(gt):
        im = cv2.imread(SRC + fn); H, W = im.shape[:2]
        x1, y1, x2, y2 = boxes[fn]
        crop = im[int(y1*H):int(y2*H), int(x1*W):int(x2*W)]
        for mode, img in (("A", crop), ("B", im)):
            t = time.perf_counter(); r = eng(img); ms = (time.perf_counter() - t) * 1000
            res[f"{fn}|{mode}"] = {"ms": ms, "items": [(a, s, b.tolist()) for a, s, b in r]}
    out[name] = res
    json.dump(res, open(paths.RESULTS_RAW / f"raw_{name}.json", "w"))
    print(name, "done")
