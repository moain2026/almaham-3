"""Seven-segment reader v2: pixel-level grid fit (no ML, no training).

Idea (analysis-by-synthesis): all main digits on a meter share ONE geometry (height, slant, pitch, stroke).
1. darkness map D in [0,1] per pixel (continuous, not binarised) — ghost segments stay low because we use max(R,G,B).
2. estimate the shared geometry from the digit pieces (robust medians), then place a fixed grid of digit cells.
3. for every cell and every segment, measure darkness pixel-by-pixel inside the segment's stroke mask
   (upper quantile -> robust to glare that wipes part of a stroke).
4. ON/OFF threshold is learned per photo from all segment values of the line (two-cluster split),
   so faint displays and bright displays are judged relative to themselves.
5. digit = nearest 7-bit pattern; confidence = distance of the weakest segment from the threshold.
"""
import cv2
import numpy as np

import sevenseg as v1

SEG_ORDER = "abcdefg"
PATTERNS = {d: frozenset(p) for d, p in v1.DIGITS.items()}
PATTERNS_ALT = {"7": frozenset("abcf"), "9": frozenset("abcfg"), "6": frozenset("cdefg")}
STROKE_FRAC = 0.16          # stroke thickness as fraction of digit height (typical meter LCD fonts 0.12-0.18)
SEG_QUANTILE = 70           # percentile of darkness inside a stroke mask (robust to partial glare)
SEG_INSET = 0.18            # shrink each stroke along its length (avoid corners shared with other segments)
MIN_CONTRAST = 0.12         # on/off clusters closer than this => unreadable (empty field)
INT_DIGITS = v1.INT_DIGITS


def darkness(bgr, work_h):
    h, w = bgr.shape[:2]
    s = work_h / h
    img = cv2.resize(bgr, (max(1, int(w * s)), work_h), interpolation=cv2.INTER_AREA)
    lum = img.max(axis=2).astype(np.float32)
    k = max(3, int(work_h * v1.BG_KERNEL_FRAC)) | 1
    bg = cv2.morphologyEx(lum, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    d = np.clip(bg - lum, 0, None)
    hi = np.percentile(d, 99.5)
    return np.clip(d / max(hi, 1.0), 0, 1)


def geometry(boxes):
    """Shared digit geometry from v1 boxes: top, height, cell width, pitch, x of first cell."""
    hs = np.array([b[3] for b in boxes]); tops = np.array([b[1] for b in boxes])
    ws = np.array([b[2] for b in boxes]); xs = np.array([b[0] + b[2] for b in boxes])  # right edges
    h = float(np.median(hs)); top = float(np.median(tops))
    cell_w = float(np.percentile(ws, 75))
    if len(xs) >= 2:
        d = np.diff(np.sort(xs))
        d = d[d > 0.5 * cell_w]
        pitch = float(np.median(d)) if d.size else cell_w * 1.25
    else:
        pitch = cell_w * 1.25
    right0 = float(np.min(xs))
    n_cells = int(round((np.max(xs) - right0) / pitch)) + 1
    return top, h, cell_w, pitch, right0, n_cells


def stroke_rects(x_right, top, cell_w, h):
    """Axis-aligned stroke rectangles for one cell (right-aligned at x_right). Mask is on the deskewed image."""
    t = STROKE_FRAC * h
    x0, x1 = x_right - cell_w, x_right
    y0, y1, ym = top, top + h, top + h / 2
    li, lv = SEG_INSET * cell_w, SEG_INSET * h / 2
    return {
        "a": (x0 + li, y0, x1 - li, y0 + t),
        "g": (x0 + li, ym - t / 2, x1 - li, ym + t / 2),
        "d": (x0 + li, y1 - t, x1 - li, y1),
        "f": (x0, y0 + lv, x0 + t, ym - lv),
        "b": (x1 - t, y0 + lv, x1, ym - lv),
        "e": (x0, ym + lv, x0 + t, y1 - lv),
        "c": (x1 - t, ym + lv, x1, y1 - lv),
    }


def measure(dark, rect):
    x0, y0, x1, y1 = (int(round(v)) for v in rect)
    h, w = dark.shape
    win = dark[max(0, y0):min(h, max(y0 + 1, y1)), max(0, x0):min(w, max(x0 + 1, x1))]
    return float(np.percentile(win, SEG_QUANTILE)) if win.size else 0.0


def two_cluster_threshold(values):
    """1-D 2-means (Otsu on the line's own segment values)."""
    v = np.sort(np.asarray(values))
    best, thr = -1.0, float(v.mean())
    for i in range(1, len(v)):
        lo, hi = v[:i], v[i:]
        score = len(lo) * len(hi) * (hi.mean() - lo.mean()) ** 2
        if score > best:
            best, thr = score, float((v[i - 1] + v[i]) / 2)
    lo, hi = v[v <= thr], v[v > thr]
    contrast = float(hi.mean() - lo.mean()) if lo.size and hi.size else 0.0
    return thr, contrast, (float(lo.mean()) if lo.size else 0.0), (float(hi.mean()) if hi.size else 1.0)


def classify(seg, thr, spread):
    """Nearest pattern by soft distance; confidence = min margin of segments that decided the digit."""
    soft = {s: float(np.clip((seg[s] - thr) / max(spread, 1e-6) + 0.5, 0, 1)) for s in SEG_ORDER}
    table = list(PATTERNS.items()) + list(PATTERNS_ALT.items())
    def dist(p):
        return sum(abs((1.0 if s in p else 0.0) - soft[s]) for s in SEG_ORDER)
    ranked = sorted(table, key=lambda kv: dist(kv[1]))
    best = ranked[0]
    second = next(kv for kv in ranked[1:] if kv[0] != best[0])
    margin = dist(second[1]) - dist(best[1])
    return best[0], float(min(1.0, margin / 2.0))


def read_line(bgr):
    mask, k = v1.deskew(v1.clean_mask(v1.ink_map(bgr)))
    boxes = v1.digit_boxes(mask)
    if not boxes:
        return "", [], {"why": "no digits"}
    dark = v1.shear(darkness(bgr, v1.WORK_H), k)
    top, h, cell_w, pitch, right0, n = geometry(boxes)
    n = min(n, INT_DIGITS)
    cells = [right0 + i * pitch for i in range(n)]
    segs = [{s: measure(dark, r) for s, r in stroke_rects(xr, top, cell_w, h).items()} for xr in cells]
    thr, contrast, lo, hi = two_cluster_threshold([v for sg in segs for v in sg.values()])
    if contrast < MIN_CONTRAST:
        return "", [], {"why": "low contrast", "contrast": contrast}
    digits, confs = zip(*(classify(sg, thr, hi - lo) for sg in segs))
    text = "".join(digits)
    return str(int(text)), list(confs), {"raw": text, "contrast": round(contrast, 2), "cells": n,
                                          "pitch": round(pitch, 1), "shear": round(k, 3)}
