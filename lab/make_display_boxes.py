"""Build reference display boxes (normalized) per image: baseline detector box inside the meter box, else manual."""
import paths
import json, csv
base = json.load(open(paths.ERP_LCD_BOXES))
meter = json.load(open(paths.METER_BOXES))
gt = {r["filename"]: r for r in csv.DictReader(open(paths.GROUND_TRUTH))}
W, H = 1920, 2560
MANUAL = {
 "23065.jpg": [0.18,0.19,0.75,0.32], "23067.jpg": [0.17,0.31,0.73,0.45], "23071.jpg": [0.18,0.19,0.75,0.33],
 "23072.jpg": [0.18,0.30,0.82,0.45], "23073.jpg": [0.25,0.33,0.66,0.46], "23074.jpg": [0.26,0.27,0.72,0.39],
 "23075.jpg": [0.27,0.31,0.73,0.42], "23077.jpg": [0.23,0.20,0.68,0.36], "23079.jpg": [0.29,0.34,0.71,0.47],
 "23080.jpg": [0.28,0.13,0.79,0.28], "23086.jpg": [0.18,0.22,0.86,0.37], "23088.jpg": [0.07,0.27,0.92,0.44],
 "23092.jpg": [0.03,0.17,0.97,0.38], "23110.jpg": [0.42,0.22,0.97,0.47], "23109.jpg": [0.46,0.545,0.585,0.595],
 "23104.jpg": [0.32,0.425,0.44,0.475],
}
out = {}
for fn in sorted(gt):
    if not gt[fn]["reading"]: continue
    if fn in MANUAL: out[fn] = MANUAL[fn]; continue
    w = 1440 if fn in {f"230{n}.jpg" for n in range(87, 98)} else W
    mx1, my1, mx2, my2 = meter[fn]; best = None
    for x1, y1, x2, y2, c, _ in base.get(fn, []):
        cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / H
        if mx1 <= cx <= mx2 and my1 <= cy <= my2 and (best is None or c > best[4]):
            best = (x1, y1, x2, y2, c)
    if best: out[fn] = [round(best[0]/w,4), round(best[1]/H,4), round(best[2]/w,4), round(best[3]/H,4)]
    else: print("MISSING", fn)
json.dump(out, open(paths.DISPLAY_BOXES, "w"), indent=0)
print(len(out))
