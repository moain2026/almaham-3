"""Build the text_locate-format input for m4 from agent R's verdicts (2026-10-24).
  ok   -> proposal (text_locate v2) as-is
  fix  -> R's box (EXIF-upright photo px). Digit boxes: try the reader on R's box (+ small jitters) and accept if
          the assembled text == label (score 0.8*minconf); else fall back to equal-width cells (score 0.5, 'cells').
  reject / 'not boxed by R' -> dropped. Reader-digit-count mismatches (owner's domain) -> dropped from m4 entirely.
Output: ../data/erp/ft/text_locate_m4.json (+ _report.json). Photos are never written anywhere.
"""
import csv, json, sys, cv2, numpy as np
import erp_finetune as ef, assemble
from eval_e2e import RD_W, RD_H, RD_PEAK_MIN, letterbox
from det_model import decode
PRIV = "/home/user/almaham-3-private-data/erp/review/line_boxes_v2_2026-10-24/"
DROP_READER = {"93cbc282-d4a4-4bf6-bde3-0e6b0e2fbe11.jpg", "document-f60bd56f-f813-5ef5-9852-56b92c99137f.jpg", "345ef2a1-3389-448c-a3df-4e1268ff2f67.jpg"}
R = list(csv.DictReader(open(PRIV + "verdicts_R.csv")))
P = {p["filename"]: p for p in json.load(open(PRIV + "proposals.json"))}
U = {u["filename"]: u for u in csv.DictReader(open(PRIV + "unlocated_need_manual_box.csv"))}
v2 = json.load(open("../data/erp/ft/text_locate_v2.json"))
rd = ef.load_net(ef.READER_PT if hasattr(ef, "READER_PT") else "weights/reader_ft6m2_s1.pt", "reader") if hasattr(ef, "load_net") else None
if rd is None:
    import torch; from det_model import DigitNet, READER_CLASSES
    rd = DigitNet(READER_CLASSES); rd.load_state_dict(torch.load("weights/reader_ft6m2_s1.pt", map_location="cpu")); rd.eval()
def read_box(im, text, box):
    H, W = im.shape[:2]; x1, y1, x2, y2 = box; bw, bh = x2 - x1, y2 - y1
    best = None
    for px, py in ((0.18, 0.45), (0.1, 0.3), (0.3, 0.6)):
        sx1, sy1 = int(max(0, x1 - bw * px)), int(max(0, y1 - bh * py)); sx2, sy2 = int(min(W, x2 + bw * px)), int(min(H, y2 + bh * py))
        crop = im[sy1:sy2, sx1:sx2]
        if crop.size == 0: continue
        ri, s, ox, oy = letterbox(crop, RD_W, RD_H, centre_x=False)
        dets = decode(*ef.run_net(rd, ri), RD_PEAK_MIN)
        r = assemble.assemble(dets, RD_W, RD_H)
        if r.text == text and r.digits:
            conf = 0.8 * min(d.score for d in r.digits)
            if best is None or conf > best[0]:
                best = (conf, [[d.cls, sx1 + (d.x1 - ox) / s, sy1 + (d.y1 - oy) / s, sx1 + (d.x2 - ox) / s, sy1 + (d.y2 - oy) / s] for d in r.digits])
    return best
out, rep = {}, {"ok": 0, "fix_reader": 0, "fix_cells": 0, "dropped_reject": 0, "dropped_notboxed": 0, "dropped_reader_mismatch": 0, "fix_fail": 0}
for r in R:
    fn, v = r["filename"], r["verdict"]
    if fn in DROP_READER: rep["dropped_reader_mismatch"] += 1; continue
    if v == "reject":
        rep["dropped_notboxed" if "not boxed" in r["note"].lower() else "dropped_reject"] += 1; continue
    if v == "ok":
        out[fn] = dict(v2[fn], R="ok"); rep["ok"] += 1; continue
    meta = P.get(fn) or U.get(fn); text = meta["reading"]
    im = cv2.imread(str(ef.ERP / "photos" / fn))
    box = [float(r[k]) for k in ("x1", "y1", "x2", "y2")]
    got = read_box(im, text, box)
    if got:
        conf, bx = got
        arr = np.array([b[1:] for b in bx])
        out[fn] = {"line": [float(arr[:, 0].min()), float(arr[:, 1].min()), float(arr[:, 2].max()), float(arr[:, 3].max())], "score": round(float(conf), 3),
                   "digits": [[int(b[0])] + [round(float(x), 1) for x in b[1:]] for b in bx], "v2": True, "R": "fix_reader"}
        rep["fix_reader"] += 1
    else:
        n = len(text); x1, y1, x2, y2 = box; cw = (x2 - x1) / n
        out[fn] = {"line": box, "score": 0.5, "digits": [[int(text[i]), round(x1 + i * cw, 1), round(y1, 1), round(x1 + (i + 1) * cw, 1), round(y2, 1)] for i in range(n)], "v2": True, "R": "fix_cells"}
        rep["fix_cells"] += 1
json.dump(out, open("../data/erp/ft/text_locate_m4.json", "w")); json.dump(rep, open("../data/erp/ft/text_locate_m4_report.json", "w"), indent=1)
print(rep, "total", len(out))
