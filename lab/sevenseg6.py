"""Seven-segment reader v6: v1 masks + robust digit-row logic (fixes found by looking at v1 failures pixel by pixel).

Failure analysis of v1 on CLEAR photos (docs/research/forensic-lab-2026-10-18.md):
  * the LCD frame / a bezel line merges with the first digit -> that box is too tall -> every real digit is
    "shorter than 0.8 * tallest" -> treated as decimals -> output = 1 digit.
  * a narrow frame line left of the first digit is taken as digit "1".
Fixes (no ML):
  1. reference height = the height shared by most groups (mode within +-15%), not the max.
  2. groups much taller than the reference are frame merges: drop border-touching pieces from them and regroup.
  3. integer part is RIGHT-anchored: take the main-height groups that end before the first small group
     (decimal digits / dot) and keep the LAST six (a frame line on the left falls off).
  4. per-photo ON/OFF threshold (two clusters) on per-segment ink fraction.
"""
import cv2
import numpy as np

import sevenseg as v1
import sevenseg2 as v2

INT_DIGITS = 6
H_TOL = 0.15
ONE_W = 0.45


def pieces(mask):
    n, _, st, _ = cv2.connectedComponentsWithStats(mask, 8)
    return [tuple(int(v) for v in st[i][:4]) for i in range(1, n) if st[i][4] >= 4]


def group(ps):
    ps = sorted(ps)
    groups = []
    for x, y, w, h in ps:
        if groups and x < groups[-1][2] - 1:
            g = groups[-1]
            groups[-1] = [min(g[0], x), min(g[1], y), max(g[2], x + w), max(g[3], y + h)]
        else:
            groups.append([x, y, x + w, y + h])
    return [(g[0], g[1], g[2] - g[0], g[3] - g[1]) for g in groups]


def ref_height(boxes, H):
    hs = np.array([b[3] for b in boxes if b[3] >= 0.25 * H], float)
    if hs.size == 0:
        return None
    votes = [(np.sum(np.abs(hs - h) <= H_TOL * h), h) for h in hs]
    best = max(votes)[0]
    return float(np.median([h for c, h in votes if c == best]))


def main_boxes(mask):
    H, W = mask.shape
    ps = pieces(mask)
    boxes = group(ps)
    ref = ref_height(boxes, H)
    if ref is None:
        return [], None
    # drop pieces that make a group too tall (frame/bezel lines), then regroup
    tall = [b for b in boxes if b[3] > (1 + 2 * H_TOL) * ref]
    if tall:
        keep = []
        for p in ps:
            x, y, w, h = p
            if h > (1 + 2 * H_TOL) * ref or (w > 2.5 * ref):
                continue
            keep.append(p)
        boxes = group(keep)
        ref = ref_height(boxes, H) or ref
    main, started = [], False
    for b in boxes:
        x, y, w, h = b
        is_main = abs(h - ref) <= H_TOL * ref and not (x <= 1 and w < ONE_W * ref * 0.3)
        if is_main:
            main.append(b); started = True
        elif started and h < (1 - H_TOL) * ref and h > 0.2 * ref:
            break                       # first small item after the digits = decimals / unit
    if not main:
        return [], ref
    # keep a run with regular pitch: split where the gap is > 1.6 * median width
    wmed = float(np.median([b[2] for b in main if b[2] > ONE_W * ref * 0.55] or [main[0][2]]))
    runs, cur = [], [main[0]]
    for a, b in zip(main, main[1:]):
        if b[0] - (a[0] + a[2]) > 1.6 * wmed:
            runs.append(cur); cur = [b]
        else:
            cur.append(b)
    runs.append(cur)
    run = max(runs, key=len)
    return run[:INT_DIGITS], ref


def seg_values(mask, box, typical_w):
    x, y, bw, bh = box
    if bw < ONE_W * typical_w:
        x, bw = x + bw - typical_w, typical_w
    out = {}
    for s, (a, b, c, d) in v1.WIN.items():
        x0, x1 = int(x + a * bw), int(x + c * bw)
        y0, y1 = int(y + b * bh), int(y + d * bh)
        win = mask[max(0, y0):max(y0 + 1, y1), max(0, x0):max(x0 + 1, x1)]
        out[s] = float(win.mean()) if win.size else 0.0
    return out


def read_mask(mask):
    boxes, ref = main_boxes(mask)
    if not boxes:
        return "", [], {"why": "no digits"}
    typical_w = float(np.percentile([b[2] for b in boxes], 75))
    digits, confs, segs = [], [], []
    for b in boxes:
        if b[2] < ONE_W * typical_w:
            digits.append("1"); confs.append(1.0); segs.append(None)
            continue
        segs.append(seg_values(mask, b, typical_w)); digits.append(None); confs.append(None)
    vals = [v for s in segs if s for v in s.values()]
    if vals:
        thr, contrast, lo, hi = v2.two_cluster_threshold(vals)
        thr = min(max(thr, 0.2), 0.6)
        for i, s in enumerate(segs):
            if s:
                d, c = v2.classify(s, thr, max(hi - lo, 0.3))
                digits[i], confs[i] = d, c
    text = "".join(digits)
    return str(int(text)), confs, {"raw": text, "n": len(boxes), "ref_h": round(ref, 1)}


def read_line(bgr):
    mask, k = v1.deskew(v1.clean_mask(v1.ink_map(bgr)))
    v, c, info = read_mask(mask)
    info["shear"] = round(k, 3)
    return v, c, info
