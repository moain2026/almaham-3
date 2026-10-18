"""Seven-segment reader v4: analysis-by-synthesis lattice search (no ML, no training, no digit segmentation).

Why: v1-v3 fail at *cutting the line into digits* (glare, scratches, frame, kWh text). v4 never cuts.
It renders a hypothesis "N digit cells of width w, pitch p, starting at x0, height h, top y0, stroke t"
and scores it directly against the continuous darkness map, pixel by pixel, using integral images.
The best-explaining lattice wins; each cell's digit is the template that best explains its pixels.

Forensic-style multi-hypothesis: the same search runs on several independent image variants
(colour channels, max/min channel, retinex ratio, CLAHE, inverted). Final value = vote.
Agreement between variants = confidence; disagreement = leave the field empty (never confident-wrong).
"""
import cv2
import numpy as np

WORK_H = 64
SHEARS = np.linspace(-0.30, 0.30, 13)
W_RATIOS = np.linspace(0.42, 0.72, 9)          # cell width / digit height
P_RATIOS = np.linspace(1.00, 1.55, 12)         # pitch / cell width
T_FRACS = (0.13, 0.18)                          # stroke thickness / digit height
INT_DIGITS = 6
ACTIVE_FRAC = 0.30                              # cell is a digit if score >= this * best cell score
SEG_ORDER = "abcdefg"
DIGITS = {"0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg",
          "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg"}
ALT = {"7": "abcf", "9": "abcfg", "6": "cdefg"}
TEMPL = [(d, p) for d, p in DIGITS.items()] + [(d, p) for d, p in ALT.items()]
# feature order: a b c d e f g holeU holeL
T_ON = np.array([[1.0 if s in p else 0.0 for s in SEG_ORDER] + [0.0, 0.0] for _, p in TEMPL])
T_OFF = 1.0 - T_ON
T_ON_N = T_ON / T_ON.sum(1, keepdims=True)
T_OFF_N = T_OFF / T_OFF.sum(1, keepdims=True)
T_LABEL = [d for d, _ in TEMPL]


# ---------------------------------------------------------------- image variants (all -> "ink" in [0,1])
def _ink_from_lum(lum, h):
    """dark strokes on light background -> high. black-hat with a kernel bigger than a stroke."""
    k = max(3, int(h * 0.45)) | 1
    bg = cv2.morphologyEx(lum, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    d = np.clip(bg - lum, 0, None)
    hi = np.percentile(d, 99.5)
    return np.clip(d / max(hi, 1e-3), 0, 1).astype(np.float32)


def variants(bgr):
    h, w = bgr.shape[:2]
    s = WORK_H / h
    img = cv2.resize(bgr, (max(8, int(w * s)), WORK_H), interpolation=cv2.INTER_AREA).astype(np.float32)
    b, g, r = img[..., 0], img[..., 1], img[..., 2]
    mx, mn = img.max(2), img.min(2)
    gray = 0.114 * b + 0.587 * g + 0.299 * r
    out = {"max": mx, "gray": gray, "min": mn, "r": r, "g": g, "b": b}
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(2, 8))
    out["clahe"] = clahe.apply(np.clip(mx, 0, 255).astype(np.uint8)).astype(np.float32)
    blur = cv2.GaussianBlur(mx, (0, 0), WORK_H * 0.8) + 1.0
    out["retinex"] = np.clip(mx / blur * 128.0, 0, 255)
    inks = {k: _ink_from_lum(v, WORK_H) for k, v in out.items()}
    inks["inverted"] = _ink_from_lum(255.0 - mx, WORK_H)     # light strokes on dark (backlit / negative)
    return inks


def shear(img, k):
    h, w = img.shape
    m = np.float32([[1, k, -k * h / 2], [0, 1, 0]])
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_LINEAR, borderValue=0)


def deskew(ink):
    gx = np.abs(cv2.Sobel(ink, cv2.CV_32F, 1, 0, ksize=3))
    best = max(SHEARS, key=lambda k: float(np.var(shear(gx, k).sum(0))))
    return float(best)


def band(ink):
    """Candidate (top, height) of the main digits from the row profile."""
    prof = (ink > 0.35).mean(1)
    on = prof > 0.25 * prof.max()
    runs, st = [], None
    for i, v in enumerate(list(on) + [False]):
        if v and st is None:
            st = i
        elif not v and st is not None:
            runs.append((st, i)); st = None
    y0, y1 = max(runs, key=lambda r: r[1] - r[0]) if runs else (0, ink.shape[0])
    return y0, y1 - y0


# ---------------------------------------------------------------- pixel-exact cell features via integral image
def rect_means(ii, xs, x0f, x1f, y0, y1):
    """mean of ink in rect [xs+x0f, xs+x1f) x [y0, y1) for every start column xs (vectorised)."""
    H = ii.shape[0] - 1
    y0, y1 = int(np.clip(round(y0), 0, H - 1)), int(np.clip(round(y1), 1, H))
    if y1 <= y0:
        y1 = y0 + 1
    a = np.clip(np.round(xs + x0f).astype(int), 0, ii.shape[1] - 1)
    b = np.clip(np.round(xs + x1f).astype(int), 0, ii.shape[1] - 1)
    b = np.maximum(b, a + 1).clip(max=ii.shape[1] - 1)
    s = ii[y1, b] - ii[y0, b] - ii[y1, a] + ii[y0, a]
    area = np.maximum((b - a) * (y1 - y0), 1)
    return s / area


def cell_features(ii, xs, w, top, h, t):
    ym = top + h / 2.0
    li, lv = 0.18 * w, 0.18 * h / 2
    R = [  # a b c d e f g holeU holeL
        (li, w - li, top, top + t),
        (w - t, w, top + lv, ym - lv),
        (w - t, w, ym + lv, top + h - lv),
        (li, w - li, top + h - t, top + h),
        (0, t, ym + lv, top + h - lv),
        (0, t, top + lv, ym - lv),
        (li, w - li, ym - t / 2, ym + t / 2),
        (t * 1.3, w - t * 1.3, top + t * 1.3, ym - t * 0.8),
        (t * 1.3, w - t * 1.3, ym + t * 0.8, top + h - t * 1.3),
    ]
    return np.stack([rect_means(ii, xs, a, b, y0, y1) for a, b, y0, y1 in R])   # (9, N)


INK_MID = 0.30                                  # ink level that counts as "half on" (ink map is 0..1)
OFF_W = 1.0                                     # weight of "should be off but is inked"
GAP_W = 1.0                                     # weight of ink between cells / left of the first cell
N_CHOICES = (1, 2, 3, 4, 5, 6)


def feature_areas(w, h, t):
    li, lv = 0.18 * w, 0.18 * h / 2
    hl = max(w - 2 * li, 1) * t
    vl = t * max(h / 2 - 2 * lv, 1)
    hole = max(w - 2.6 * t, 1) * max(h / 2 - 2.1 * t, 1)
    return np.array([hl, vl, vl, hl, vl, vl, hl, hole, hole])


def score_cells(F, areas):
    """Pixel-level agreement per start column. F: (9,N) means. returns best score, label, margin."""
    X = (F - INK_MID) * areas[:, None]            # signed ink mass per feature
    S = T_ON @ X - OFF_W * (T_OFF @ X)
    k = S.argmax(0)
    best = S[k, np.arange(S.shape[1])]
    srt = np.sort(S, axis=0)
    second = srt[-2]
    return best, k, best - second


def fit(ink):
    """Search lattice hypotheses (shear, top, height, width, pitch, offset, count)."""
    k = deskew(ink)
    D = shear(ink, k)
    H, W = D.shape
    ii = cv2.integral(D.astype(np.float64))
    best = None
    for h in np.linspace(0.40 * H, 0.95 * H, 8):
        for top in np.linspace(0, H - h, 6):
            t = 0.15 * h
            areas = feature_areas(1, h, t)
            for wr in W_RATIOS:
                w = wr * h
                areas = feature_areas(w, h, t)
                xs = np.arange(0, max(1, int(W - w)))
                if xs.size < 2:
                    continue
                F = cell_features(ii, xs, w, top, h, t)
                sc, lab, mar = score_cells(F, areas)
                for pr in P_RATIOS:
                    p = pr * w
                    gap = p - w
                    # ink mass in the gap right after each start column (between this cell and the next)
                    gm = (rect_means(ii, xs, w, max(p, w + 1), top + 0.1 * h, top + 0.9 * h) - INK_MID * 0.0) \
                        * max(gap, 1) * 0.8 * h
                    for n in N_CHOICES:
                        span = w + (n - 1) * p
                        x0max = int(W - span)
                        if x0max < 0:
                            continue
                        x0s = np.arange(0, x0max + 1)
                        IDX = np.round(x0s[:, None] + p * np.arange(n)[None, :]).astype(int).clip(0, xs.size - 1)
                        cell = sc[IDX].sum(1)
                        gaps = gm[IDX[:, :-1]].sum(1) if n > 1 else 0.0
                        left = ii[int(top + 0.9 * h), x0s] - ii[int(top + 0.1 * h), x0s]   # ink left of cell 0
                        left = left - (ii[int(top + 0.9 * h), 0] - ii[int(top + 0.1 * h), 0])
                        TOT = cell - GAP_W * gaps - GAP_W * left
                        j = int(TOT.argmax())
                        if best is None or TOT[j] > best[0]:
                            idx = IDX[j]
                            best = (float(TOT[j]), dict(shear=k, top=top, h=h, t=t, w=w, p=p, x0=int(x0s[j]),
                                                        n=n, idx=idx, cs=sc[idx].copy(), lab=lab[idx].copy(),
                                                        mar=mar[idx].copy()))
    return best


def decode(fitres):
    if fitres is None:
        return "", [], {}
    tot, f = fitres
    cs, lab, mar = f["cs"], f["lab"], f["mar"]
    if cs.max() <= 0:
        return "", [], {"why": "no digit"}
    run = list(range(len(cs)))
    text = "".join(T_LABEL[lab[i]] for i in run)
    confs = [float(min(1.0, mar[i] / max(abs(cs[i]), 1e-6))) for i in run]
    value = str(int(text)) if text else ""
    return value, confs, {"raw": text, "score": round(tot, 2), "n": len(run),
                          "w": round(f["w"], 1), "p": round(f["p"], 1), "h": f["h"]}


def read_variant(bgr, name):
    ink = variants(bgr)[name]
    return decode(fit(ink))


VOTE_VARIANTS = ("max", "gray", "min", "clahe", "retinex", "r", "b")


def read_line(bgr, names=VOTE_VARIANTS):
    """Multi-variant vote. conf per digit = fraction of variants agreeing on the winning value."""
    inks = variants(bgr)
    votes = {}
    details = {}
    for n in names:
        v, c, info = decode(fit(inks[n]))
        details[n] = v
        if v:
            votes.setdefault(v, []).append(n)
    if not votes:
        return "", [], {"votes": details}
    win = max(votes, key=lambda v: len(votes[v]))
    agree = len(votes[win]) / len(names)
    return win, [agree] * len(win), {"agree": round(agree, 2), "votes": details}
