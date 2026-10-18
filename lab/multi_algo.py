"""Multi-algorithm deterministic reader (agent B, owner request 2026-10-18: "add all algorithms, colours and movements").

No ML. For each crop we run MANY independent examinations and vote:
  colours   : max(RGB), gray, R, G, B, HSV-V, Lab-L, 1-saturation, CLAHE(gray), gamma 0.6 / 1.6 on gray
  polarity  : dark digits on light LCD (default) and inverted (light digits on dark/backlit)
  binarizers: tophat+Otsu (forensic_reader), adaptive-mean, Sauvola-like local, global Otsu on raw
  movements : crop jitter (shift left/right/up/down 6%, shrink 6%, grow 8%) and small rotations (-4, +4 deg)
Each examination reuses the forensic_reader segment logic (deskew -> digit boxes -> 7-segment classify).
Vote: most frequent text among 6-digit texts starting with 0 (meter prior); if none, among texts with >= 4 digits.

Usage: python3 multi_algo.py [line|meter]   (line = line_boxes.json crops, meter = meter_boxes.json rectangle)
Writes benchmark/results/engines/multi_algo_<mode>.json. Prints exact / oracle (any examination right) / DEV-HOLDOUT.
Calibration warning: algorithm list chosen by agent B looking at failures on DEV photos; HOLDOUT is the honest number.
"""
import collections
import json
import sys
import time

import cv2
import numpy as np

import forensic_reader as fr
import gt
import paths
from eval_sevenseg import DEV

W_H = fr.WORK_H


# ---------------------------------------------------------------- fast cv2 versions of the forensic primitives
def _components(mask):
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    return [tuple(int(v) for v in st[i]) for i in range(1, n)], lab


def _shear(mask, k):
    h, w = mask.shape
    M = np.float32([[1, k, -k * h / 2.0], [0, 1, 0]])
    return cv2.warpAffine(mask.astype(np.uint8), M, (w, h), flags=cv2.INTER_NEAREST, borderValue=0)


fr.components = _components
fr.shear = _shear


# ---------------------------------------------------------------- colours
def colours(bgr):
    b, g, r = cv2.split(bgr)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    clahe = cv2.createCLAHE(2.0, (4, 4)).apply(gray)
    lut = lambda gm: cv2.LUT(gray, np.array([((i / 255.0) ** gm) * 255 for i in range(256)], np.uint8))
    return {"max": np.maximum(np.maximum(b, g), r), "gray": gray, "R": r, "G": g, "B": b, "V": hsv[..., 2],
            "L": lab[..., 0], "unsat": 255 - hsv[..., 1], "clahe": clahe, "gam06": lut(0.6), "gam16": lut(1.6)}


# ---------------------------------------------------------------- binarizers (all return ink=1 at WORK_H height)
def _work(lum):
    h, w = lum.shape
    return cv2.resize(lum, (max(1, w * W_H // h), W_H), interpolation=cv2.INTER_AREA)


def bin_tophat(lum):
    l = _work(lum).astype(np.float32)
    k = max(3, int(W_H * fr.BG_K_FRAC)) | 1
    dark = cv2.morphologyEx(l, cv2.MORPH_CLOSE, np.ones((k, k), np.uint8)) - l
    u8 = cv2.normalize(dark, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    return (u8 > cv2.threshold(u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[0]).astype(np.uint8)


def bin_adapt(lum):
    l = _work(lum)
    return (cv2.adaptiveThreshold(l, 1, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 31, 8)).astype(np.uint8)


def bin_sauvola(lum):
    l = _work(lum).astype(np.float32)
    m = cv2.blur(l, (31, 31))
    s = np.sqrt(np.maximum(cv2.blur(l * l, (31, 31)) - m * m, 0))
    return (l < m * (1 + 0.2 * (s / 128.0 - 1))).astype(np.uint8)


def bin_otsu(lum):
    l = cv2.GaussianBlur(_work(lum), (3, 3), 0)
    return (cv2.threshold(l, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]).astype(np.uint8)


BINS = {"tophat": bin_tophat, "adapt": bin_adapt, "sauvola": bin_sauvola, "otsu": bin_otsu}


# ---------------------------------------------------------------- movements
def moves(crop):
    h, w = crop.shape[:2]
    out = {"orig": crop}
    dx, dy = int(0.06 * w), int(0.06 * h)
    pad = cv2.copyMakeBorder(crop, dy, dy, dx, dx, cv2.BORDER_REPLICATE)
    out["left"] = pad[dy:dy + h, 0:w]
    out["right"] = pad[dy:dy + h, 2 * dx:2 * dx + w]
    out["up"] = pad[0:h, dx:dx + w]
    out["down"] = pad[2 * dy:2 * dy + h, dx:dx + w]
    out["shrink"] = crop[dy:h - dy, dx:w - dx] if h > 4 * dy and w > 4 * dx else crop
    g = int(0.08 * h)
    out["grow"] = cv2.copyMakeBorder(crop, g, g, g, g, cv2.BORDER_REPLICATE)
    for a in (-4, 4):
        M = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0)
        out[f"rot{a:+d}"] = cv2.warpAffine(crop, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    return out


# ---------------------------------------------------------------- one examination on a mask (forensic logic)
def read_mask(mask):
    mask = fr.clean(mask)
    mask, _ = fr.deskew(mask)
    boxes, _ = fr.main_boxes(mask)
    if not boxes:
        return ""
    tw = fr.percentile([b[2] for b in boxes], 75)
    segs = [None if b[2] < fr.ONE_W * tw else fr.seg_values(mask, b, tw) for b in boxes]
    vals = [v for s in segs if s for v in s]
    thr, lo, hi = fr.two_cluster(vals) if vals else (0.4, 0.0, 1.0)
    thr = min(max(thr, fr.THR_MIN), fr.THR_MAX)
    spread = max(hi - lo, fr.SPREAD_MIN)
    return "".join("1" if s is None else str(fr.classify(s, thr, spread)[0]) for s in segs)


def examinations(crop):
    out = []
    for mv, img in moves(crop).items():
        for cn, lum in colours(img).items():
            for pol in ("dark", "light"):
                l = lum if pol == "dark" else 255 - lum
                for bn, fn in BINS.items():
                    out.append((f"{mv}|{cn}|{pol}|{bn}", read_mask(fn(l))))
    return out


def vote(exams):
    # physical prior of these meters: the integer line has 6 cells and the leftmost is a leading 0 -> prefer those
    six0 = [t for _, t in exams if len(t) == 6 and t[0] == "0"]
    texts = six0 or [t for _, t in exams if len(t) >= 4]
    if not texts:
        return "", 0, 0
    c = collections.Counter(texts)
    best = max(c.items(), key=lambda kv: (kv[1], len(kv[0])))
    return best[0], best[1], len(texts)


def value(t):
    return str(int(t)) if t else ""


def main(mode="line"):
    boxes = json.load(open(paths.LINE_BOXES if mode == "line" else paths.METER_BOXES))
    rows = []
    per_exam_ok = collections.Counter()
    t_all = time.perf_counter()
    for it in gt.load():
        if not it.readable:
            continue
        im = cv2.imread(gt.PHOTOS + it.name)
        H, W = im.shape[:2]
        x1, y1, x2, y2 = boxes[it.name]
        crop = im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)]
        t0 = time.perf_counter()
        ex = examinations(crop)
        txt, n_win, n_valid = vote(ex)
        ms = (time.perf_counter() - t0) * 1000
        right = [n for n, t in ex if value(t) == it.reading]
        for n in right:
            per_exam_ok[n] += 1
        ok = value(txt) == it.reading
        rows.append({"file": it.name, "truth": it.reading, "vote": txt, "value": value(txt), "ok": ok,
                     "agree": n_win, "valid": n_valid, "n_exams": len(ex), "n_right": len(right),
                     "dev": it.name[:5] in DEV, "ms": round(ms, 1)})
        print(("OK " if ok else "   ") + it.name[:5], it.reading, "vote", value(txt), f"{n_win}/{n_valid}",
              "right-exams", len(right), f"{ms:.0f}ms", flush=True)
    n = len(rows)
    # agreement-gated: only answer when >= X% of valid examinations agree (precision vs coverage)
    gates = {}
    for g in (0.2, 0.3, 0.4, 0.5):
        ans = [r for r in rows if r["valid"] and r["agree"] / r["valid"] >= g]
        gates[str(g)] = {"answered": len(ans), "correct": sum(r["ok"] for r in ans)}
    summ = {"mode": mode, "n": n, "exact": sum(r["ok"] for r in rows),
            "exact_dev": sum(r["ok"] for r in rows if r["dev"]), "n_dev": sum(r["dev"] for r in rows),
            "exact_holdout": sum(r["ok"] for r in rows if not r["dev"]), "n_holdout": sum(not r["dev"] for r in rows),
            "oracle_any_exam_right": sum(r["n_right"] > 0 for r in rows),
            "exams_per_photo": rows[0]["n_exams"] if rows else 0,
            "best_single_exams": per_exam_ok.most_common(10),
            "agreement_gate": gates,
            "ms_p50": sorted(r["ms"] for r in rows)[n // 2], "total_s": round(time.perf_counter() - t_all, 1),
            "hardware": "sandbox x86 4-core, python+opencv (NOT a phone)",
            "note": "best_single_exams is chosen on the same photos (in-sample) — do not quote it as accuracy"}
    print(json.dumps(summ, ensure_ascii=False, indent=1))
    paths.ensure_dirs()
    json.dump({"summary": summ, "rows": rows}, open(paths.RESULTS_ENGINES / f"multi_algo_{mode}.json", "w"),
              ensure_ascii=False, indent=0)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "line")
