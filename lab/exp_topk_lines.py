"""Experiment (eval only): for each of the 46 photos, read the top-K locator candidates separately and report
(a) oracle: is the correct reading among the K candidate readings? (ceiling of any selection rule)
(b) a few deterministic selection rules, measured exact / wrong_confident."""
import csv, json, sys
import cv2, numpy as np
import assemble, paths, segverify
from det_model import decode
from eval_e2e import Engine, letterbox, LOC_IN, RD_H, RD_W, LOC_PEAK_MIN, LINE_MIN_H, PAD_X, PAD_Y, RD_PEAK_MIN, LATTICE_PEAK_MIN

K = int(sys.argv[2]) if len(sys.argv) > 2 else 3
eng = Engine(sys.argv[1])

def read_rect(crop, rect):
    H, W = crop.shape[:2]
    if rect is None:
        sx1, sy1, sx2, sy2 = 0, 0, W, H
    else:
        x1, y1, x2, y2 = rect
        px, py = (x2 - x1) * PAD_X, (y2 - y1) * PAD_Y
        sx1, sy1 = int(np.clip(x1 - px, 0, W - 1)), int(np.clip(y1 - py, 0, H - 1))
        sx2, sy2 = int(np.clip(x2 + px, sx1 + 1, W)), int(np.clip(y2 + py, sy1 + 1, H))
    ri, _, _, _ = letterbox(crop[sy1:sy2, sx1:sx2], RD_W, RD_H, centre_x=False)
    peaks, size, offs = eng.run(eng.rd, ri)
    dets = decode(peaks, size, offs, RD_PEAK_MIN)
    r = assemble.assemble(dets, RD_W, RD_H)
    if r.status == "MISSING_DIGIT":
        extra = []
        for (x1, y1, x2, y2) in assemble.missing_cells(r.digits):
            cx, cy = int(((x1 + x2) / 2) / 4), int(((y1 + y2) / 2) / 4)
            win = peaks[:10, max(0, cy - 1):min(peaks.shape[1], cy + 2), max(0, cx - 1):min(peaks.shape[2], cx + 2)]
            if win.size and win.max() > LATTICE_PEAK_MIN:
                extra.append((int(np.unravel_index(win.argmax(), win.shape)[0]), float(win.max()), x1, y1, x2, y2))
        if extra:
            r = assemble.assemble(dets + extra, RD_W, RD_H)
    segverify.verify(cv2.cvtColor(ri, cv2.COLOR_BGR2GRAY), r.digits)
    return r

def candidates(crop):
    li, s, ox, oy = letterbox(crop, LOC_IN, LOC_IN)
    lines = decode(*eng.run(eng.loc, li), LOC_PEAK_MIN)
    lines = [l for l in lines if l[5] - l[3] >= LINE_MIN_H]
    lines.sort(key=lambda l: -l[1])
    out = []
    for l in lines[:K]:
        x1, y1, x2, y2 = [(v - (ox if i % 2 == 0 else oy)) / s for i, v in enumerate(l[2:])]
        out.append((l[1], (x1, y1, x2, y2)))
    return out

def quality(r):
    """Deterministic score of a reading: prefer OK status, 6 integer cells, then mean digit score, few uncertain."""
    if not r.digits:
        return (-1, 0, 0, 0)
    n = len(r.digits)
    ok = r.status == "OK"
    cells6 = 1 if n == 6 else 0
    unc = sum(d.uncertain for d in r.digits)
    mean = sum(min(d.score, 1.0) for d in r.digits) / n
    return (int(ok), cells6, -unc, mean)

gt = list(csv.DictReader(open(paths.GROUND_TRUTH, encoding="utf-8")))
boxes = json.load(open(paths.METER_BOXES))
rows = []
for g in gt:
    if not g["reading"]:
        continue
    im = cv2.imread(paths.photo(g["filename"]))
    H, W = im.shape[:2]
    x1, y1, x2, y2 = boxes[g["filename"]]
    crop = im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)]
    cands = candidates(crop)
    reads = [(sc, read_rect(crop, rect)) for sc, rect in cands] or [(0.0, read_rect(crop, None))]
    rows.append((g["filename"], g["reading"], reads))

def report(name, pick):
    ex = wc = 0
    for fn, truth, reads in rows:
        r = pick(reads)
        v = r.value
        ex += v == truth
        wc += bool(v) and v != truth and r.confident
    print(f"{name:<34} exact {ex:2d}/46  wrong&confident {wc}")
    return ex

print(f"K={K}")
report("top1 (current)", lambda reads: reads[0][1])
oracle = sum(any(r.value == truth for _, r in reads) for fn, truth, reads in rows)
print(f"{'ORACLE any-of-K correct':<34} exact {oracle:2d}/46")
report("rule: best quality()", lambda reads: max(reads, key=lambda t: quality(t[1]))[1])
report("rule: 6 cells else top1", lambda reads: next((r for _, r in reads if len(r.digits) == 6 and r.status == "OK"), reads[0][1]))
report("rule: OK else top1", lambda reads: next((r for _, r in reads if r.status == "OK" and r.digits), reads[0][1]))
report("rule: quality but top1 if OK&6", lambda reads: reads[0][1] if (reads[0][1].status == "OK" and len(reads[0][1].digits) == 6) else max(reads, key=lambda t: quality(t[1]))[1])
print()
for fn, truth, reads in rows:
    vals = [(round(sc, 2), r.value or "-", r.status[:4], len(r.digits)) for sc, r in reads]
    mark = "OK" if reads[0][1].value == truth else ("ok@K" if any(r.value == truth for _, r in reads) else "XX")
    print(f"{mark:5s} {fn} truth={truth:<6} cands={vals}")
