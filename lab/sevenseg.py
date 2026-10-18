"""Deterministic seven-segment reader (no ML, no training). Quick prototype to measure the idea on real photos.

Input: a BGR crop that contains the main reading line. Output: integer part (str) + per-digit confidence.
Steps (each a pure function): ink map -> deskew (italic shear) -> digit boxes -> drop decimals -> segments -> lookup.
"""
import cv2
import numpy as np

WORK_H = 96                 # resize line crop to this height
BG_KERNEL_FRAC = 0.45       # background estimate kernel, fraction of height
SHEAR_RANGE = np.linspace(-0.35, 0.35, 29)
MIN_DIGIT_H_FRAC = 0.55     # component must be at least this tall vs image height to be a main digit
DECIMAL_H_RATIO = 0.80      # digits shorter than this * tallest are decimals (ignored)
ONE_W_RATIO = 0.55          # width below this * typical digit width => '1'
SEG_ON = 0.38               # fraction of ink in a segment window to call it ON

# segments: a top, b top-right, c bottom-right, d bottom, e bottom-left, f top-left, g middle
DIGITS = {
    "0": "abcdef", "1": "bc", "2": "abdeg", "3": "abcdg", "4": "bcfg",
    "5": "acdfg", "6": "acdefg", "7": "abc", "8": "abcdefg", "9": "abcdfg",
}
ALT = {"7": "abcf", "9": "abcfg", "6": "cdefg"}  # common display variants
SEG_ORDER = "abcdefg"
# windows (x0, y0, x1, y1) in digit-box fractions
WIN = {
    "a": (0.25, 0.00, 0.75, 0.16), "d": (0.25, 0.84, 0.75, 1.00), "g": (0.25, 0.42, 0.75, 0.58),
    "f": (0.00, 0.15, 0.30, 0.42), "b": (0.70, 0.15, 1.00, 0.42),
    "e": (0.00, 0.58, 0.30, 0.85), "c": (0.70, 0.58, 1.00, 0.85),
}


def ink_map(bgr):
    """Dark strokes -> 1. Uses max(R,G,B) so coloured 'ghost' segments (light blue/grey) read as background."""
    h, w = bgr.shape[:2]
    s = WORK_H / h
    img = cv2.resize(bgr, (max(1, int(w * s)), WORK_H), interpolation=cv2.INTER_AREA)
    lum = img.max(axis=2).astype(np.float32)
    k = max(3, int(WORK_H * BG_KERNEL_FRAC)) | 1
    bg = cv2.morphologyEx(lum, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    dark = np.clip(bg - lum, 0, 255)
    dark = cv2.normalize(dark, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    _, bw = cv2.threshold(dark, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return (bw > 0).astype(np.uint8)


def shear(mask, k):
    h, w = mask.shape
    m = np.float32([[1, k, -k * h / 2], [0, 1, 0]])
    return cv2.warpAffine(mask, m, (w, h), flags=cv2.INTER_NEAREST)


def deskew(mask):
    """Pick the shear that makes vertical strokes most vertical (sharpest column projection)."""
    best = max(SHEAR_RANGE, key=lambda k: np.var(shear(mask, k).sum(0)))
    return shear(mask, best), float(best)


INT_DIGITS = 6             # 42/46 test meters show exactly 6 integer digits (CRYSTAL shows fewer)
GAP_CLOSE_FRAC = 0.22      # max inner gap inside one digit, fraction of line height
MIN_PIECE_H_FRAC = 0.30     # pieces shorter than this * tallest piece are not main-digit segments
DOT_MAX_H = 0.22           # decimal point: tiny blob (<22% of digit height)
DOT_BASE_TOL = 0.12        # ... sitting on the digit baseline
MAX_PIECE_W_TO_H = 1.6      # a segment piece is never much wider than tall*1.6 (rejects LCD frame lines)
MIN_PIECE_AREA_FRAC = 0.002


def clean_mask(mask):
    """Remove pieces that touch the crop border (LCD frame, bezel) and long thin lines."""
    h, w = mask.shape
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask, 8)
    keep = np.zeros(n, bool)
    for i in range(1, n):
        x, y, bw, bh, area = st[i]
        touches = x == 0 or y == 0 or x + bw >= w or y + bh >= h
        frame_like = touches and (bw > 0.6 * h or bh > 0.95 * h or area < 0.2 * bw * bh or bw < 0.12 * bh)
        thin_line = bw > MAX_PIECE_W_TO_H * h * 0.5 and area < 0.25 * bw * bh
        keep[i] = not frame_like and not thin_line and area >= MIN_PIECE_AREA_FRAC * h * h
    return keep[lab].astype(np.uint8)


def line_band(mask):
    """Rows of the main reading line = the tallest run of rows with ink (drops secondary lines / labels)."""
    rows = mask.sum(1) > 0
    runs, start = [], None
    for i, r in enumerate(list(rows) + [False]):
        if r and start is None:
            start = i
        elif not r and start is not None:
            runs.append((start, i)); start = None
    return max(runs, key=lambda r: r[1] - r[0]) if runs else (0, mask.shape[0])


def digit_boxes(mask):
    """Main-digit boxes, left->right, stopping at the first short item (decimal point, decimals, unit text)."""
    y0, y1 = line_band(mask)
    band = np.zeros_like(mask)
    band[y0:y1] = mask[y0:y1]
    n, _, st, _ = cv2.connectedComponentsWithStats(band, 8)
    pieces = sorted((st[i][0], st[i][1], st[i][0] + st[i][2], st[i][1] + st[i][3]) for i in range(1, n))
    groups = []
    for x0, py0, x1, py1 in pieces:           # segment pieces whose x-ranges overlap = same digit
        if groups and x0 < groups[-1][2] - 1:
            g = groups[-1]
            groups[-1] = [min(g[0], x0), min(g[1], py0), max(g[2], x1), max(g[3], py1)]
        else:
            groups.append([x0, py0, x1, py1])
    boxes = [(g[0], g[1], g[2] - g[0], g[3] - g[1]) for g in groups]
    if not boxes:
        return []
    hmax = max(b[3] for b in boxes)
    out = []
    for b in boxes:
        if b[3] < DECIMAL_H_RATIO * hmax:
            if out:
                break
            continue
        out.append(b)
    return out[:INT_DIGITS] if len(out) > INT_DIGITS else out


def segments(mask, box, typical_w):
    x, y, bw, bh = box
    if bw < ONE_W_RATIO * typical_w:   # narrow -> only right segments; widen box leftwards
        x, bw = x + bw - typical_w, typical_w
    out = {}
    for s, (a, b, c, d) in WIN.items():
        x0, x1 = int(x + a * bw), int(x + c * bw)
        y0, y1 = int(y + b * bh), int(y + d * bh)
        win = mask[max(0, y0):max(y0 + 1, y1), max(0, x0):max(x0 + 1, x1)]
        out[s] = float(win.mean()) if win.size else 0.0
    return out


def classify(seg):
    on = "".join(s for s in SEG_ORDER if seg[s] >= SEG_ON)
    table = {**{k: v for k, v in DIGITS.items()}, **{k + "'": v for k, v in ALT.items()}}
    def dist(pattern):
        return sum(abs((1.0 if s in pattern else 0.0) - min(1.0, seg[s] / (2 * SEG_ON))) for s in SEG_ORDER)
    ranked = sorted(table.items(), key=lambda kv: dist(kv[1]))
    best, second = ranked[0], ranked[1]
    margin = dist(second[1]) - dist(best[1])
    conf = float(min(1.0, margin / 1.5))
    return best[0][0], conf, on


def read_line(bgr):
    mask, k = deskew(clean_mask(ink_map(bgr)))
    boxes = digit_boxes(mask)
    if not boxes:
        return "", [], {"shear": k, "n": 0}
    typical_w = int(np.percentile([b[2] for b in boxes], 75))
    digits, confs = [], []
    for b in boxes:
        if b[2] < ONE_W_RATIO * typical_w:
            digits.append("1"); confs.append(1.0)
            continue
        d, c, _ = classify(segments(mask, b, typical_w))
        digits.append(d); confs.append(c)
    text = "".join(digits)
    value = str(int(text)) if text else ""
    return value, confs, {"shear": k, "n": len(boxes), "raw": text}
