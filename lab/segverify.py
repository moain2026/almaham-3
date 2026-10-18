"""Seven-segment consistency verifier (no learning). Mirrors app/meterocr SegmentVerifier.kt.

Given a digit box predicted by DigitNet, we measure the ink of the seven segments geometrically and compare the
ON/OFF pattern with the pattern of the predicted class. This is the "second opinion" that catches the classic
confusions on ghosted / glared LCDs (0↔8, 6↔8, 9↔8, 5↔6, 3↔9, 1↔7) which a CNN scores confidently.

  agreement(box, cls) in [0,1]   -> 1.0 when every segment matches the class pattern
  best_pattern_class(box)        -> the class whose pattern is closest to the measured ink, with its agreement

Measurement: the box is split into 7 segment zones (a top, b upper-right, c lower-right, d bottom, e lower-left,
f upper-left, g middle). Ink = fraction of "dark" pixels in the zone, where dark is defined per box by Otsu on the
box itself (robust to the per-display contrast). A segment is ON when its ink exceeds the midpoint between the
darkest and lightest segment ink of that box (so ghost segments, which are uniformly faint, stay OFF).
Digit '1' is special: its box is narrow, so the zones for a, d, g, e, f are taken from a virtual full-width cell
anchored at the right edge.
"""
import cv2
import numpy as np

SEG = {0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc", 5: "afgcd", 6: "afgedc", 7: "abc", 8: "abcdefg", 9: "abcdfg"}
ALL = "abcdefg"
PATTERN = {c: np.array([s in SEG[c] for s in ALL], float) for c in SEG}
NARROW_RATIO = 0.55   # w/h below this -> treat as a '1'-shaped box, use virtual full cell
MIN_SIZE = 8          # px; smaller boxes cannot be measured


def segment_zones(w, h):
    """Return 7 zones (x0,y0,x1,y1) in a w x h cell, fractions of the cell."""
    t = 0.22  # segment thickness fraction
    m = 0.5
    return {
        "a": (0.2, 0.0, 0.8, t),
        "d": (0.2, 1 - t, 0.8, 1.0),
        "g": (0.2, m - t / 2, 0.8, m + t / 2),
        "f": (0.0, 0.12, t, m - 0.08),
        "b": (1 - t, 0.12, 1.0, m - 0.08),
        "e": (0.0, m + 0.08, t, 1 - 0.12),
        "c": (1 - t, m + 0.08, 1.0, 1 - 0.12),
    }


def segment_ink(gray_crop, x1, y1, x2, y2):
    """Measured ink per segment (7 floats in [0,1]) for the box in a grayscale image, or None if too small."""
    H, W = gray_crop.shape
    x1, y1, x2, y2 = int(max(0, x1)), int(max(0, y1)), int(min(W, x2)), int(min(H, y2))
    w, h = x2 - x1, y2 - y1
    if w < 3 or h < MIN_SIZE:
        return None
    if w / h < NARROW_RATIO:  # '1'-like: virtual full cell to the left
        cw = int(round(h * 0.6))
        x1 = max(0, x2 - cw)
        w = x2 - x1
    cell = gray_crop[y1:y2, x1:x2]
    if cell.size == 0:
        return None
    # dark-on-light assumed; if the cell is light-on-dark (LED), invert
    if cell.mean() < 100:
        cell = 255 - cell
    thr, _ = cv2.threshold(cell, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    dark = (cell < thr).astype(np.float32)
    ink = []
    for s in ALL:
        fx0, fy0, fx1, fy1 = segment_zones(w, h)[s]
        zx0, zy0 = int(fx0 * w), int(fy0 * h)
        zx1, zy1 = max(zx0 + 1, int(fx1 * w)), max(zy0 + 1, int(fy1 * h))
        ink.append(float(dark[zy0:zy1, zx0:zx1].mean()))
    return np.array(ink)


def on_pattern(ink):
    """Binarise segment ink with a per-box midpoint threshold (ghost segments stay OFF)."""
    lo, hi = ink.min(), ink.max()
    if hi - lo < 0.15:  # all segments similar: either everything on (8) or nothing measurable
        return (ink > 0.5).astype(float)
    return (ink > (lo + hi) / 2).astype(float)


def agreement(ink, cls):
    """Fraction of the 7 segments whose measured state matches the class pattern."""
    return float((on_pattern(ink) == PATTERN[cls]).mean())


def best_pattern_class(ink):
    pat = on_pattern(ink)
    scores = {c: float((pat == PATTERN[c]).mean()) for c in PATTERN}
    c = max(scores, key=scores.get)
    return c, scores[c]


def verify(gray_crop, digits):
    """Annotate assembled digits: sets d.seg_agree (float) and d.seg_cls (int). Does not change d.cls.
    Returns the number of digits whose pattern disagrees with the predicted class (agreement < 6/7)."""
    disagreements = 0
    for d in digits:
        ink = segment_ink(gray_crop, d.x1, d.y1, d.x2, d.y2)
        if ink is None:
            d.seg_agree, d.seg_cls = 1.0, d.cls
            continue
        d.seg_agree = agreement(ink, d.cls)
        d.seg_cls, _ = best_pattern_class(ink)
        if d.seg_agree < 6 / 7:
            disagreements += 1
    return disagreements
