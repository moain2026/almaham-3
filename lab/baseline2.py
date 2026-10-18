"""Baseline ERP two-stage (lcd-detector-v1 + digit-reader-v3, AGPL) on modes A (meter box), B (full), C (oracle display)."""
import paths
import cv2, json, csv, time, statistics as st
from yolo_onnx import YoloDetector
V = paths.ERP_VISION_S; S = paths.PHOTOS_S
gt = {r["filename"]: r for r in csv.DictReader(open(paths.GROUND_TRUTH))}
mb = json.load(open(paths.METER_BOXES)); db = json.load(open(paths.DISPLAY_BOXES))
lcd = YoloDetector(V + "lcd-detector-v1.onnx", 8); dig = YoloDetector(V + "digit-reader-v3.onnx", 10)
def read_digits(crop):
    ds = dig.detect(crop, 0.3, 0.35)
    if not ds: return ""
    hmax = max(d.y2 - d.y1 for d in ds)
    main = [d for d in ds if (d.y2 - d.y1) >= 0.7 * hmax]
    main.sort(key=lambda d: d.x1)
    s = "".join(str(d.cls) for d in main)
    return str(int(s[:6])) if s else ""
def crop_pad(im, x1, y1, x2, y2, px=0.06, py=0.15):
    H, W = im.shape[:2]; w, h = x2 - x1, y2 - y1
    return im[max(0, int(y1 - py*h)):min(H, int(y2 + py*h)), max(0, int(x1 - px*w)):min(W, int(x2 + px*w))]
res = {"A": [0, []], "B": [0, []], "C": [0, []]}
for fn, g in sorted(gt.items()):
    if not g["reading"]: continue
    im = cv2.imread(S + fn); H, W = im.shape[:2]
    x1, y1, x2, y2 = mb[fn]; A = im[int(y1*H):int(y2*H), int(x1*W):int(x2*W)]
    for m, img in (("A", A), ("B", im)):
        t = time.perf_counter(); b = lcd.detect(img, 0.4, 0.5)
        v = read_digits(crop_pad(img, b[0].x1, b[0].y1, b[0].x2, b[0].y2)) if b else ""
        res[m][1].append((time.perf_counter() - t) * 1000); res[m][0] += v == g["reading"]
    x1, y1, x2, y2 = db[fn]; C = im[int(y1*H):int(y2*H), int(x1*W):int(x2*W)]
    t = time.perf_counter(); v = read_digits(C); res["C"][1].append((time.perf_counter() - t) * 1000); res["C"][0] += v == g["reading"]
for m, (ok, tm) in res.items(): print(m, f"{ok}/46", f"p50 {st.median(tm):.0f}ms")
