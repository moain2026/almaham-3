"""Fault attribution on the 49 (mode A): locator IoU vs oracle line box, and reader on oracle crop (mode L)."""
import csv, json, sys, cv2, numpy as np
import paths
from eval_e2e import Engine, PAD_X, PAD_Y
md = sys.argv[1]
eng = Engine(md)
gt = {r["filename"]: r for r in csv.DictReader(open(paths.GROUND_TRUTH, encoding="utf-8"))}
boxes = json.load(open(paths.METER_BOXES)); lines = json.load(open(paths.LINE_BOXES))
def iou(a, b):
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    return inter / ((a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter + 1e-9)
rows = []
for fn, g in sorted(gt.items()):
    truth = g["reading"]
    if not truth: continue
    im = cv2.imread(paths.photo(fn)); H, W = im.shape[:2]
    x1, y1, x2, y2 = boxes[fn]
    ax, ay = int(x1 * W), int(y1 * H)
    crop = im[ay:int(y2 * H), ax:int(x2 * W)]
    r, rect, score, _, _ = eng.read(crop)
    io = None; rl_val = None
    if fn in lines:
        lx1, ly1, lx2, ly2 = lines[fn]
        orc = (lx1 * W - ax, ly1 * H - ay, lx2 * W - ax, ly2 * H - ay)
        io = iou(rect, orc) if rect else 0.0
        lw, lh = (lx2-lx1)*W, (ly2-ly1)*H
        line_l = im[int(max(0, ly1*H - PAD_Y*lh)):int(min(H, ly2*H + PAD_Y*lh)), int(max(0, lx1*W - PAD_X*lw)):int(min(W, lx2*W + PAD_X*lw))]
        rl = eng.read_line_only(line_l) if hasattr(eng, "read_line_only") else eng.read(line_l)
        rl_val = rl[0].value if isinstance(rl, tuple) else rl.value
    rows.append(dict(file=fn, type=g["meter_type"], truth=truth, A=r.value, A_ok=r.value == truth, iou=io, L=rl_val, L_ok=(rl_val == truth) if rl_val is not None else None))
ok = sum(r["A_ok"] for r in rows)
print(f"A exact {ok}/{len(rows)}")
cats = {"A_ok": 0, "loc_fault(iou<0.5)": 0, "reader_fault(iou>=0.5,L wrong)": 0, "crop_fault(iou>=0.5,L ok)": 0, "no_oracle": 0}
for r in rows:
    if r["A_ok"]: cats["A_ok"] += 1; continue
    if r["iou"] is None: cats["no_oracle"] += 1; continue
    if r["iou"] < 0.5: cats["loc_fault(iou<0.5)"] += 1
    elif not r["L_ok"]: cats["reader_fault(iou>=0.5,L wrong)"] += 1
    else: cats["crop_fault(iou>=0.5,L ok)"] += 1
print(cats)
print("L (oracle line) exact:", sum(1 for r in rows if r["L_ok"]), "/", sum(1 for r in rows if r["L_ok"] is not None))
for r in rows:
    if not r["A_ok"]:
        print(f"  {r['file']} {r['type']:13s} gt={r['truth']:6s} A={r['A']:7s} iou={r['iou'] if r['iou'] is None else round(r['iou'],2)} L={r['L']}")
json.dump(rows, open(sys.argv[2], "w"), indent=1)
