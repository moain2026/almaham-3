"""Ghost-detection study (training audit 2026-10-24 §3b). No retraining: cache raw reader detections on the oracle
line crops of the 49 (38 with a human line box) and on the real end-to-end crops (mode A, located by the locator),
then measure candidate post-processing rules against display_text / truth.
Usage: python3 ghost_study.py <models_dir> cache   -> ../data/ghost_cache.json (dets per photo, both crops)
       python3 ghost_study.py <models_dir> eval    -> table of rules
Rules are pure functions over dets (cls, score, x1, y1, x2, y2) in 64x448 px so they can be mirrored in Kotlin.
"""
import csv, json, sys, cv2, numpy as np
import paths, assemble
from eval_e2e import Engine, PAD_X, PAD_Y, RD_W, RD_H, RD_PEAK_MIN, letterbox
from det_model import decode
CACHE = "../data/ghost_cache.json"

def cache(md):
    eng = Engine(md)
    gt = {r["filename"]: r for r in csv.DictReader(open(paths.GROUND_TRUTH, encoding="utf-8"))}
    lines = json.load(open(paths.LINE_BOXES)); boxes = json.load(open(paths.METER_BOXES))
    out = {}
    for fn, g in sorted(gt.items()):
        if not g["reading"]: continue
        im = cv2.imread(paths.photo(fn)); H, W = im.shape[:2]
        rec = {"truth": g["reading"], "display": g.get("display_text", ""), "type": g["meter_type"]}
        # oracle crop
        if fn in lines:
            lx1, ly1, lx2, ly2 = lines[fn]; lw, lh = (lx2 - lx1) * W, (ly2 - ly1) * H
            crop = im[int(max(0, ly1 * H - PAD_Y * lh)):int(min(H, ly2 * H + PAD_Y * lh)), int(max(0, lx1 * W - PAD_X * lw)):int(min(W, lx2 * W + PAD_X * lw))]
            ri, _, _, _ = letterbox(crop, RD_W, RD_H, centre_x=False)
            peaks, size, offs = eng.run(eng.rd, ri)
            rec["L"] = [[int(d[0]), float(d[1])] + [float(v) for v in d[2:]] for d in decode(peaks, size, offs, 0.15)]  # low thr: rules may raise it
        # end-to-end crop (mode A): reuse Engine.read's crop logic by calling read and recomputing dets
        x1, y1, x2, y2 = boxes[fn]
        crop_a = im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)]
        r, rect, score, ms, ri = eng.read(crop_a)
        peaks, size, offs = eng.run(eng.rd, ri)
        rec["A"] = [[int(d[0]), float(d[1])] + [float(v) for v in d[2:]] for d in decode(peaks, size, offs, 0.15)]
        rec["A_rect"] = rect; rec["A_value_shipped"] = r.value; rec["A_status_shipped"] = r.status
        out[fn] = rec
    json.dump(out, open(CACHE, "w")); print("cached", len(out))

# ---------- candidate rules ----------
def thr(dets, t): return [d for d in dets if d[1] >= t]
def nms_x(dets, frac=0.6):
    """1-D NMS along x among digit dets: if two centres are closer than frac*median pitch, keep the higher score."""
    dg = sorted([d for d in dets if d[0] < 10], key=lambda d: -d[1]); others = [d for d in dets if d[0] >= 10]
    if len(dg) < 2: return dets
    cx = sorted((d[2] + d[4]) / 2 for d in dg); pitch = float(np.median(np.diff(cx))) if len(cx) > 1 else 0
    w = float(np.median([d[4] - d[2] for d in dg]))
    lim = frac * max(pitch, w) if pitch > 0 else frac * w
    keep = []
    for d in dg:
        c = (d[2] + d[4]) / 2
        if all(abs(c - (k[2] + k[4]) / 2) >= lim for k in keep): keep.append(d)
    return keep + others
def nms_x_w(dets, frac=0.6):
    """same but limit = frac * median box WIDTH only (independent of pitch, robust when ghosts corrupt the pitch)."""
    dg = sorted([d for d in dets if d[0] < 10], key=lambda d: -d[1]); others = [d for d in dets if d[0] >= 10]
    if len(dg) < 2: return dets
    w = float(np.median([d[4] - d[2] for d in dg])); lim = frac * w; keep = []
    for d in dg:
        c = (d[2] + d[4]) / 2
        if all(abs(c - (k[2] + k[4]) / 2) >= lim for k in keep): keep.append(d)
    return keep + others
def run(dets, rule):
    r = assemble.assemble(rule(dets), RD_W, RD_H); return r

def evaluate():
    C = json.load(open(CACHE))
    rules = {
        "shipped(thr.30)": lambda d: thr(d, 0.30),
        "thr.35": lambda d: thr(d, 0.35),
        "thr.40": lambda d: thr(d, 0.40),
        "thr.30+nmsx.5": lambda d: nms_x(thr(d, 0.30), 0.5),
        "thr.30+nmsx.6": lambda d: nms_x(thr(d, 0.30), 0.6),
        "thr.30+nmsx.7": lambda d: nms_x(thr(d, 0.30), 0.7),
        "thr.30+nmsw.6": lambda d: nms_x_w(thr(d, 0.30), 0.6),
        "thr.30+nmsw.8": lambda d: nms_x_w(thr(d, 0.30), 0.8),
        "thr.25+nmsw.8": lambda d: nms_x_w(thr(d, 0.25), 0.8),
        "thr.35+nmsw.8": lambda d: nms_x_w(thr(d, 0.35), 0.8),
    }
    print(f"{'rule':18s} | A exact  A wrong&conf  A empty | L exact  L seq==display | A strict-gate acc/wrong")
    for name, rule in rules.items():
        ae = aw = aemp = le = lseq = acc = accw = 0; nA = nL = 0
        for fn, rec in C.items():
            t = rec["truth"]
            r = run(rec["A"], rule); nA += 1
            ae += r.value == t; aw += (r.value != t and r.value != "" and r.confident); aemp += r.value == ""
            strict = r.status == "OK" and r.value != "" and r.min_conf >= 0.55 and all(d.alt_score < 0.5 * d.score for d in r.digits)
            if strict: acc += 1; accw += r.value != t
            if "L" in rec:
                nL += 1; rl = run(rec["L"], rule); le += rl.value == t
                dg = sorted([d for d in rule(rec["L"]) if d[0] < 10], key=lambda d: (d[2] + d[4]) / 2)
                disp = "".join(ch for ch in rec["display"] if ch.isdigit())
                lseq += ("".join(str(d[0]) for d in dg) == disp)
        print(f"{name:18s} | {ae:2d}/{nA}   {aw:2d}          {aemp:2d}     | {le:2d}/{nL}    {lseq:2d}/{nL}            | {acc:2d}/{accw}")

if __name__ == "__main__":
    {"cache": lambda: cache(sys.argv[1]), "eval": evaluate}[sys.argv[2]]()
