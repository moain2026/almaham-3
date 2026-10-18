"""Forensic (deterministic, no-ML) seven-segment line reader — contract docs/agent-contract.md §2.

read_line(crop_bgr) -> {"text", "digits": [{"cls", "conf", "box", "segments"}], "status", "ms"}

Integer part only (decimals are never read). Self-contained: numpy + cv2 only for I/O-free primitives
that are re-implemented here in plain numpy so the Kotlin port (app/meterocr/.../ForensicReader.kt)
can match it number-for-number:
  box-average resize, max/min (morphological close) filters, Otsu on a 256-bin histogram,
  8-connected components, nearest-neighbour shear, rectangular window means.

Pipeline (per image variant: max(RGB), gray, green):
  1. ink map  : resize to WORK_H rows; background = closing(lum, K x K); dark = bg - lum; Otsu -> mask.
  2. clean    : drop components that look like the LCD frame (touch border and are long/hollow) or thin lines.
  3. deskew   : shear in SHEARS maximising the variance of the column projection.
  4. digits   : group components whose x-ranges overlap; reference height = the most common height (+-15%);
                frame-merged tall groups are rebuilt without the tall pieces; the integer part is the run of
                main-height groups that starts left and ends at the first small item (decimal digits / dot / unit).
  5. segments : 7 windows per digit box; per-photo ON/OFF threshold by 2-cluster split of all segment values.
  6. classify : nearest 7-bit pattern; margin to the 2nd pattern = geometric confidence.
Voting over the 3 variants (forensic "independent examinations"). Confidence rule (measured, not felt):
  HIGH (CONF_HIGH) only when all 3 examinations give the same class at that position, the line has >= MIN_LEN_HIGH
  digits (a short line means digits were lost), and the digit is not a non-zero leftmost digit (on these meters the
  leftmost cell is a leading zero; a non-zero there is usually the LCD frame read as "1"/"6").
  Otherwise conf = geometric margin x agreement share, capped at CONF_LOW_CAP (< 0.8).
  NOTE: the rule was derived on the same 46 photos it is measured on (in-sample) — re-check on ERP photos.
"""
import time

import numpy as np

WORK_H = 96
BG_K_FRAC = 0.45
SHEARS = [(-350 + 25 * i) / 1000.0 for i in range(29)]   # same doubles in Kotlin
INT_DIGITS = 6
H_TOL = 0.15
ONE_W = 0.45
MAX_PIECE_W_TO_H = 1.6
MIN_PIECE_AREA_FRAC = 0.002
THR_MIN, THR_MAX, SPREAD_MIN = 0.2, 0.6, 0.3
VARIANTS = ("max", "gray", "green")
SEG_ORDER = "abcdefg"
PATTERNS = [  # (cls, segments a..g)
    (0, "abcdef"), (1, "bc"), (2, "abdeg"), (3, "abcdg"), (4, "bcfg"), (5, "acdfg"), (6, "acdefg"), (7, "abc"),
    (8, "abcdefg"), (9, "abcdfg"), (7, "abcf"), (9, "abcfg"), (6, "cdefg"),
]
PAT_BITS = [(c, [1 if s in p else 0 for s in SEG_ORDER]) for c, p in PATTERNS]
WIN = {  # segment windows (x0, y0, x1, y1) as fractions of the digit box
    "a": (0.25, 0.00, 0.75, 0.16), "b": (0.70, 0.15, 1.00, 0.42), "c": (0.70, 0.58, 1.00, 0.85),
    "d": (0.25, 0.84, 0.75, 1.00), "e": (0.00, 0.58, 0.30, 0.85), "f": (0.00, 0.15, 0.30, 0.42),
    "g": (0.25, 0.42, 0.75, 0.58),
}
CONF_ONE = 0.9          # geometric confidence of a narrow "1" box (no segment pattern to compare)
CONF_HIGH = 0.95
CONF_LOW_CAP = 0.79
MIN_LEN_HIGH = 5


# ------------------------------------------------------------------ portable primitives
def resize_box(img, out_w, out_h):
    """Box-average resize with integer source bins [floor(i*s), max(floor((i+1)*s), floor(i*s)+1))."""
    h, w = img.shape
    ys = [(i * h // out_h, max((i + 1) * h // out_h, i * h // out_h + 1)) for i in range(out_h)]
    xs = [(j * w // out_w, max((j + 1) * w // out_w, j * w // out_w + 1)) for j in range(out_w)]
    ii = np.zeros((h + 1, w + 1), np.float64)
    ii[1:, 1:] = img.astype(np.float64).cumsum(0).cumsum(1)
    out = np.empty((out_h, out_w), np.float64)
    for i, (y0, y1) in enumerate(ys):
        for j, (x0, x1) in enumerate(xs):
            s = ii[y1, x1] - ii[y0, x1] - ii[y1, x0] + ii[y0, x0]
            out[i, j] = s / ((y1 - y0) * (x1 - x0))
    return out


def _filter1d(a, k, axis, fn):
    r = k // 2
    n = a.shape[axis]
    out = np.empty_like(a)
    for i in range(n):
        lo, hi = max(0, i - r), min(n, i + r + 1)
        sl = [slice(None)] * a.ndim
        sl[axis] = slice(lo, hi)
        o = [slice(None)] * a.ndim
        o[axis] = i
        out[tuple(o)] = fn(a[tuple(sl)], axis=axis)
    return out


def close_rect(a, k):
    """Morphological closing with a k x k square (window clipped at the border)."""
    d = _filter1d(_filter1d(a, k, 0, np.max), k, 1, np.max)
    return _filter1d(_filter1d(d, k, 0, np.min), k, 1, np.min)


def otsu(u8):
    hist = np.bincount(u8.ravel(), minlength=256).astype(np.float64)
    total = hist.sum()
    sum_all = float(np.dot(np.arange(256), hist))
    w0 = s0 = 0.0
    best, thr = -1.0, 0
    for t in range(256):
        w0 += hist[t]
        if w0 == 0:
            continue
        w1 = total - w0
        if w1 == 0:
            break
        s0 += t * hist[t]
        m0, m1 = s0 / w0, (sum_all - s0) / w1
        v = w0 * w1 * (m0 - m1) ** 2
        if v > best:
            best, thr = v, t
    return thr


def components(mask):
    """8-connected components -> list of (x, y, w, h, area), scan order of first pixel."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    out = []
    for y in range(h):
        for x in range(w):
            if mask[y, x] and not lab[y, x]:
                n = len(out) + 1
                stack = [(y, x)]
                lab[y, x] = n
                x0 = x1 = x
                y0 = y1 = y
                area = 0
                while stack:
                    cy, cx = stack.pop()
                    area += 1
                    x0, x1, y0, y1 = min(x0, cx), max(x1, cx), min(y0, cy), max(y1, cy)
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and not lab[ny, nx]:
                                lab[ny, nx] = n
                                stack.append((ny, nx))
                out.append((x0, y0, x1 - x0 + 1, y1 - y0 + 1, area))
    return out, lab


def shear(mask, k):
    """Nearest-neighbour shear: out[y, x] = mask[y, round(x - k*(y - h/2))]."""
    h, w = mask.shape
    out = np.zeros_like(mask)
    for y in range(h):
        off = k * (y - h / 2.0)
        src = np.floor(np.arange(w) - off + 0.5).astype(int)
        ok = (src >= 0) & (src < w)
        out[y, ok] = mask[y, src[ok]]
    return out


def median(v):
    s = sorted(v)
    n = len(s)
    return float(s[n // 2]) if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def percentile(v, q):
    """numpy 'linear' percentile."""
    s = sorted(v)
    pos = (len(s) - 1) * q / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


# ------------------------------------------------------------------ pipeline
def channel(bgr, variant):
    b, g, r = (bgr[..., i].astype(np.int32) for i in range(3))
    if variant == "max":
        return np.maximum(np.maximum(b, g), r)
    if variant == "gray":
        return (299 * r + 587 * g + 114 * b) // 1000
    return g


def ink_mask(lum_full):
    h, w = lum_full.shape
    out_w = max(1, w * WORK_H // h)
    lum = resize_box(lum_full, out_w, WORK_H)
    k = max(3, int(WORK_H * BG_K_FRAC)) | 1
    dark = np.clip(close_rect(lum, k) - lum, 0, None)
    lo, hi = float(dark.min()), float(dark.max())
    u8 = np.zeros(dark.shape, np.uint8) if hi <= lo else np.floor((dark - lo) * 255.0 / (hi - lo)).astype(np.uint8)
    return (u8 > otsu(u8)).astype(np.uint8)


def clean(mask):
    h, w = mask.shape
    comps, lab = components(mask)
    keep = np.zeros(len(comps) + 1, np.uint8)
    for i, (x, y, bw, bh, area) in enumerate(comps, 1):
        touches = x == 0 or y == 0 or x + bw >= w or y + bh >= h
        frame_like = touches and (bw > 0.6 * h or bh > 0.95 * h or area < 0.2 * bw * bh or bw < 0.12 * bh)
        thin_line = bw > MAX_PIECE_W_TO_H * h * 0.5 and area < 0.25 * bw * bh
        keep[i] = 1 if (not frame_like and not thin_line and area >= MIN_PIECE_AREA_FRAC * h * h) else 0
    return keep[lab]


def deskew(mask):
    """argmax over SHEARS of the column-projection variance, computed exactly in integers: n*sum(x^2) - (sum x)^2."""
    best, bk = -1, 0.0
    for k in SHEARS:
        col = shear(mask, k).sum(0).astype(np.int64)
        v = int(col.size * int((col * col).sum()) - int(col.sum()) ** 2)
        if v > best:
            best, bk = v, k
    return shear(mask, bk), bk


def group(pieces):
    groups = []
    for x, y, w, h in sorted(pieces):
        if groups and x < groups[-1][2] - 1:
            g = groups[-1]
            groups[-1] = [min(g[0], x), min(g[1], y), max(g[2], x + w), max(g[3], y + h)]
        else:
            groups.append([x, y, x + w, y + h])
    return [(g[0], g[1], g[2] - g[0], g[3] - g[1]) for g in groups]


def ref_height(boxes, H):
    hs = [b[3] for b in boxes if b[3] >= 0.25 * H]
    if not hs:
        return None
    votes = [(sum(1 for o in hs if abs(o - h) <= H_TOL * h), h) for h in hs]
    top = max(v[0] for v in votes)
    return median([h for c, h in votes if c == top])


def main_boxes(mask):
    H = mask.shape[0]
    pieces = [(x, y, w, h) for x, y, w, h, a in components(mask)[0] if a >= 4]
    boxes = group(pieces)
    ref = ref_height(boxes, H)
    if ref is None:
        return [], None
    if any(b[3] > (1 + 2 * H_TOL) * ref for b in boxes):
        boxes = group([p for p in pieces if p[3] <= (1 + 2 * H_TOL) * ref and p[2] <= 2.5 * ref])
        ref = ref_height(boxes, H) or ref
    main, started = [], False
    for x, y, w, h in boxes:
        if abs(h - ref) <= H_TOL * ref and not (x <= 1 and w < ONE_W * ref * 0.3):
            main.append((x, y, w, h))
            started = True
        elif started and 0.2 * ref < h < (1 - H_TOL) * ref:
            break
    if not main:
        return [], ref
    wide = [b[2] for b in main if b[2] > ONE_W * ref * 0.55] or [main[0][2]]
    wmed = median(wide)
    runs, cur = [], [main[0]]
    for a, b in zip(main, main[1:]):
        if b[0] - (a[0] + a[2]) > 1.6 * wmed:
            runs.append(cur)
            cur = [b]
        else:
            cur.append(b)
    runs.append(cur)
    return max(runs, key=len)[:INT_DIGITS], ref


def seg_values(mask, box, typical_w):
    x, y, bw, bh = box
    if bw < ONE_W * typical_w:
        x, bw = x + bw - typical_w, typical_w
    out = []
    for s in SEG_ORDER:
        a, b, c, d = WIN[s]
        x0, x1 = int(x + a * bw), int(x + c * bw)          # int() truncates toward zero (same as Kotlin toInt())
        y0, y1 = int(y + b * bh), int(y + d * bh)
        xs, xe = max(0, x0), min(mask.shape[1], max(x0 + 1, x1))
        ys, ye = max(0, y0), min(mask.shape[0], max(y0 + 1, y1))
        out.append(float(mask[ys:ye, xs:xe].sum()) / ((ye - ys) * (xe - xs)) if ye > ys and xe > xs else 0.0)
    return out


def two_cluster(vals):
    v = sorted(vals)
    best, thr = -1.0, sum(v) / len(v)
    for i in range(1, len(v)):
        lo, hi = v[:i], v[i:]
        ml, mh = sum(lo) / len(lo), sum(hi) / len(hi)
        sc = len(lo) * len(hi) * (mh - ml) ** 2
        if sc > best:
            best, thr = sc, (v[i - 1] + v[i]) / 2
    lo = [x for x in v if x <= thr]
    hi = [x for x in v if x > thr]
    return thr, (sum(lo) / len(lo) if lo else 0.0), (sum(hi) / len(hi) if hi else 1.0)


def classify(seg, thr, spread):
    soft = [min(1.0, max(0.0, (s - thr) / spread + 0.5)) for s in seg]
    dists = [(sum(abs(b - x) for b, x in zip(bits, soft)), c) for c, bits in PAT_BITS]
    dists.sort(key=lambda t: t[0])
    best_d, best_c = dists[0]
    second_d = next(d for d, c in dists[1:] if c != best_c)
    return best_c, min(1.0, (second_d - best_d) / 2.0), [1 if x >= 0.5 else 0 for x in soft]


def read_variant(bgr, variant):
    """One independent examination. Returns list of digits (cls, conf, box_crop, segments) and shear."""
    h_full = bgr.shape[0]
    mask = clean(ink_mask(channel(bgr, variant)))
    mask, k = deskew(mask)
    boxes, _ = main_boxes(mask)
    if not boxes:
        return []
    typical_w = percentile([b[2] for b in boxes], 75)
    segs = [None if b[2] < ONE_W * typical_w else seg_values(mask, b, typical_w) for b in boxes]
    vals = [v for s in segs if s for v in s]
    thr, lo, hi = two_cluster(vals) if vals else (0.4, 0.0, 1.0)
    thr = min(max(thr, THR_MIN), THR_MAX)
    spread = max(hi - lo, SPREAD_MIN)
    s = h_full / WORK_H
    out = []
    for b, sg in zip(boxes, segs):
        x, y, w, h = b
        cy = y + h / 2.0                                   # undo the shear at the box centre for crop coordinates
        dx = k * (cy - WORK_H / 2.0)
        box = [(x + dx) * s, y * s, (x + w + dx) * s, (y + h) * s]
        if sg is None:
            out.append((1, CONF_ONE, box, [0, 1, 1, 0, 0, 0, 0]))
        else:
            c, conf, bits = classify(sg, thr, spread)
            out.append((c, conf, box, bits))
    return out


def read_line(crop_bgr):
    t0 = time.perf_counter()
    exams = [read_variant(crop_bgr, v) for v in VARIANTS]
    texts = ["".join(str(d[0]) for d in e) for e in exams]
    nonempty = [t for t in texts if t]
    if not nonempty:
        return {"text": "", "digits": [], "status": "EMPTY", "ms": round((time.perf_counter() - t0) * 1000, 1)}
    # winning examination = the text most variants agree on (ties: the first variant, max(RGB))
    win = max(nonempty, key=lambda t: (texts.count(t), -texts.index(t)))
    base = exams[texts.index(win)]
    same_len = [e for e in exams if len(e) == len(base)]
    digits = []
    for i, (c, conf, box, bits) in enumerate(base):
        n_agree = sum(1 for e in same_len if e[i][0] == c)
        if n_agree == len(VARIANTS) and len(base) >= MIN_LEN_HIGH and not (i == 0 and c != 0):
            p = CONF_HIGH
        else:
            p = min(CONF_LOW_CAP, conf * n_agree / len(VARIANTS))
        digits.append({"cls": int(c), "conf": float(p), "box": box, "segments": bits})
    unanimous = texts.count(win) == len(VARIANTS)
    if unanimous and all(d["conf"] >= 0.8 for d in digits):
        status = "OK"
    elif len(base) < MIN_LEN_HIGH:
        status = "MISSING_DIGIT"
    else:
        status = "UNSURE"
    return {"text": win, "digits": digits, "status": status, "ms": round((time.perf_counter() - t0) * 1000, 1)}
