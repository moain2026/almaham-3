"""Seven-segment reader v5: "ghost lattice" — locate cells from ALL segments (lit + unlit ghosts), then read.

Forensic idea: on most meter LCDs the unlit segments are faintly visible ("ghost 8s"). Readers v1-v4 suppress them
(max-RGB) and then struggle to cut digits. v5 uses them: every cell looks like a faint "8", so a regular lattice of
6 identical 8-shaped cells can be fitted with pixel precision (integral images, exhaustive search, no segmentation).
Displays without ghosts still work: the lit segments of each digit fall on the same lattice.

Then each segment is measured on the strong ink map (lit only) and split ON/OFF by a per-photo two-cluster
threshold (lit vs ghost are two populations). Digit = nearest 7-bit pattern. Decimal digits are never read:
they are smaller than the main lattice and right of it.
"""
import cv2
import numpy as np

import sevenseg2 as v2

WORK_H = 64
INT_DIGITS = 6
SHEARS = np.linspace(-0.30, 0.30, 13)
H_FRACS = np.linspace(0.45, 0.95, 11)
W_RATIOS = np.linspace(0.38, 0.72, 12)
P_RATIOS = np.linspace(1.02, 1.60, 18)
T_FRAC = 0.15
SEG_ORDER = "abcdefg"


def ink(lum, h):
    k = max(3, int(h * 0.45)) | 1
    bg = cv2.morphologyEx(lum, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    d = np.clip(bg - lum, 0, None)
    return np.clip(d / max(np.percentile(d, 99.5), 1e-3), 0, 1).astype(np.float32)


def maps(bgr):
    h, w = bgr.shape[:2]
    s = WORK_H / h
    img = cv2.resize(bgr, (max(8, int(w * s)), WORK_H), interpolation=cv2.INTER_AREA).astype(np.float32)
    weak = ink(img.min(2), WORK_H)          # min channel: ghosts (bluish/grey) stay visible
    strong = ink(img.max(2), WORK_H)        # max channel: ghosts suppressed, lit segments only
    return weak, strong


def shear(img, k):
    h, w = img.shape
    return cv2.warpAffine(img, np.float32([[1, k, -k * h / 2], [0, 1, 0]]), (w, h),
                          flags=cv2.INTER_LINEAR, borderValue=0)


def deskew(img):
    gx = np.abs(cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3))
    return float(max(SHEARS, key=lambda k: float(np.var(shear(gx, k).sum(0)))))


def rects(w, h, top, t):
    ym = top + h / 2.0
    li, lv = 0.15 * w, 0.12 * h / 2
    seg = {
        "a": (li, w - li, top, top + t), "g": (li, w - li, ym - t / 2, ym + t / 2),
        "d": (li, w - li, top + h - t, top + h),
        "f": (0, t, top + lv, ym - lv), "b": (w - t, w, top + lv, ym - lv),
        "e": (0, t, ym + lv, top + h - lv), "c": (w - t, w, ym + lv, top + h - lv),
    }
    holes = [(t * 1.4, w - t * 1.4, top + t * 1.4, ym - t * 0.9),
             (t * 1.4, w - t * 1.4, ym + t * 0.9, top + h - t * 1.4)]
    return seg, holes


def rmean(ii, xs, x0, x1, y0, y1):
    H, Wp = ii.shape[0] - 1, ii.shape[1] - 1
    y0 = int(np.clip(round(y0), 0, H - 1)); y1 = int(np.clip(round(y1), y0 + 1, H))
    a = np.clip(np.round(xs + x0).astype(int), 0, Wp - 1)
    b = np.clip(np.maximum(np.round(xs + x1).astype(int), a + 1), 1, Wp)
    return (ii[y1, b] - ii[y0, b] - ii[y1, a] + ii[y0, a]) / np.maximum((b - a) * (y1 - y0), 1)


def band(img):
    """(top, height) of the tallest run of rows that carry ink (main digit row)."""
    prof = (img > 0.4).mean(1)
    on = prof > 0.3 * prof.max()
    runs, st = [], None
    for i, v in enumerate(list(on) + [False]):
        if v and st is None:
            st = i
        elif not v and st is not None:
            runs.append((st, i)); st = None
    y0, y1 = max(runs, key=lambda r: r[1] - r[0]) if runs else (0, img.shape[0])
    return y0, y1 - y0


def fit_lattice(weak, strong=None):
    """Exhaustive pixel lattice search on score map M = max(weak, strong).
    cell = mean ink on 7 segment strokes - mean ink in 2 holes; minus ink in inter-cell gaps."""
    M = weak if strong is None else np.maximum(weak, strong)
    H, W = M.shape
    ii = cv2.integral(M.astype(np.float64))
    cand = {(round(t), round(h)) for h in np.linspace(0.35 * H, 0.97 * H, 10) for t in np.linspace(0, H - h, 7)}
    best = _search(ii, W, cand)
    if best is None:
        return None
    f = best[1]
    fine = {(f["top"] + dt, f["h"] + dh) for dt in range(-3, 4) for dh in range(-4, 5)
            if f["top"] + dt >= 0 and f["top"] + dt + f["h"] + dh <= H and f["h"] + dh >= 0.3 * H}
    best2 = _search(ii, W, fine)
    return best2 if best2 and best2[0] >= best[0] else best


def _search(ii, W, cand):
    best = None
    for top, h in cand:
        t = T_FRAC * h
        for wr in W_RATIOS:
            w = wr * h
            xs = np.arange(0, max(2, int(W - w) + 1))
            seg, holes = rects(w, h, top, t)
            S = np.mean([rmean(ii, xs, *r) for r in seg.values()], 0)
            Ho = np.mean([rmean(ii, xs, *r) for r in holes], 0)
            cell = S - Ho
            for pr in P_RATIOS:
                p = pr * w
                gapm = rmean(ii, xs, w + 0.15 * (p - w), w + 0.85 * (p - w) + 1, top + 0.15 * h, top + 0.85 * h)
                span = w + (INT_DIGITS - 1) * p
                if span > W + 0.5 * w:
                    continue
                x0s = np.arange(0, max(1, int(W - span) + 1))
                IDX = np.round(x0s[:, None] + p * np.arange(INT_DIGITS)[None, :]).astype(int).clip(0, xs.size - 1)
                TOT = cell[IDX].mean(1) - 0.7 * gapm[IDX[:, :-1]].mean(1)
                j = int(TOT.argmax())
                if best is None or TOT[j] > best[0]:
                    best = (float(TOT[j]), dict(h=h, t=t, top=top, w=w, p=p, idx=IDX[j]))
    return best


PATTERNS = [(d, frozenset(p)) for d, p in v2.PATTERNS.items()] + [(d, p) for d, p in v2.PATTERNS_ALT.items()]
PATTERNS.append((" ", frozenset()))           # blank cell (meters without leading zeros)


def lit_threshold(vals):
    """Three populations: background, ghost (unlit but visible), lit. ON = lit only.
    1-D 3-means by exhaustive split search; falls back to 2 clusters when the middle one is empty."""
    v = np.sort(vals)
    n = len(v)
    cs = np.concatenate([[0], np.cumsum(v)]); cs2 = np.concatenate([[0], np.cumsum(v * v)])
    def sse(i, j):
        m = j - i
        return 0.0 if m <= 0 else cs2[j] - cs2[i] - (cs[j] - cs[i]) ** 2 / m
    best = None
    for i in range(1, n - 1):
        for j in range(i + 1, n):
            e = sse(0, i) + sse(i, j) + sse(j, n)
            if best is None or e < best[0]:
                best = (e, i, j)
    _, i, j = best
    lo, mid, hi = v[:i].mean(), v[i:j].mean(), v[j:].mean()
    thr2, _, lo2, hi2 = v2.two_cluster_threshold(vals)
    # use 3 clusters only if the middle cluster is a real population (ghosts) clearly below lit
    if (hi - mid) > 0.15 and (mid - lo) > 0.05 and (j - i) >= 3:
        return float((v[j - 1] + v[j]) / 2), float(mid), float(hi)
    return thr2, lo2, hi2


def classify(seg, thr, spread):
    soft = {s: float(np.clip((seg[s] - thr) / max(spread, 1e-6) + 0.5, 0, 1)) for s in SEG_ORDER}
    def dist(p):
        return sum(abs((1.0 if s in p else 0.0) - soft[s]) for s in SEG_ORDER)
    ranked = sorted(PATTERNS, key=lambda kv: dist(kv[1]))
    best = ranked[0]
    second = next(kv for kv in ranked[1:] if kv[0] != best[0])
    return best[0], float(min(1.0, (dist(second[1]) - dist(best[1])) / 2.0))


def read_line(bgr):
    weak, strong = maps(bgr)
    k = deskew(weak)
    weak, strong = shear(weak, k), shear(strong, k)
    fit = fit_lattice(weak, strong)
    if fit is None:
        return "", [], {"why": "no lattice"}
    _, f = fit
    segs = []
    for x in f["idx"]:
        seg, _ = rects(f["w"], f["h"], f["top"], f["t"])
        segs.append({s: float(np.percentile(strong[max(0, int(y0)):max(int(y0) + 1, int(y1)),
                                                   max(0, int(x + a)):max(int(x + a) + 1, int(x + b))], 70))
                     for s, (a, b, y0, y1) in seg.items()})
    vals = np.array([v for sg in segs for v in sg.values()])
    thr, lo, hi = lit_threshold(vals)
    if hi - lo < v2.MIN_CONTRAST:
        return "", [], {"why": "low contrast"}
    digits, confs = zip(*(classify(sg, thr, hi - lo) for sg in segs))
    text = "".join(digits).lstrip(" ")
    if not text or " " in text:
        return "", [], {"why": "blank inside number", "raw": "".join(digits)}
    return str(int(text)), list(confs), {"raw": text, "shear": round(k, 2), "h": round(f["h"], 1),
                                          "w": round(f["w"], 1), "p": round(f["p"], 1), "x": [int(i) for i in f["idx"]],
                                          "top": round(f["top"], 1)}
