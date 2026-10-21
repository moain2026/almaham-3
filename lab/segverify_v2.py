"""Independent geometric second opinion; no model, training, or original-file edits.

Seven analytic stroke masks are fitted to each cell after removing a planar
illumination field. Fixed shear/tilt/thickness and ghost-strength hypotheses are
searched, independent of the reader's proposed class. Both polarities are fitted;
absolute image brightness is NOT a polarity decision. The 7-with-upper-left
stroke used by DSEG is a supported topology, not a new digit class.

IMPORTANT API difference from segverify.py: segment_ink returns SegmentEvidence,
not an occupancy ndarray. agreement is a normalized image/template correlation
in [0,1], NOT a seven-bit match fraction or a calibrated probability. Do not reuse
the old 6/7 confidence gate. on_pattern is only a measured-strength diagnostic.
No automatic correction of d.cls, no Reading.confident integration, no Kotlin.
"""
from dataclasses import dataclass
from functools import lru_cache

import cv2
import numpy as np

ALL = "abcdefg"
SEG = {0: "abcdef", 1: "bc", 2: "abged", 3: "abgcd", 4: "fgbc",
       5: "afgcd", 6: "afgedc", 7: "abc", 8: "abcdefg", 9: "abcdfg"}
PATTERN = {c: np.array([s in SEG[c] for s in ALL], dtype=np.float32) for c in SEG}
MIN_SIZE = 16
NARROW_RATIO = 0.28  # ordinary full cells can have w/h around .46; .55 is not '1'
WIDTH, HEIGHT = 28, 40
MIN_RMS_CONTRAST = 1.5  # observation floor, not an acceptance/production threshold


@dataclass(frozen=True)
class SegmentEvidence:
    strengths: np.ndarray
    class_scores: np.ndarray
    contrast_rms: float
    polarity: str
    geometry: tuple
    narrow: bool
    fit: float
    margin: float


def segment_zones(thickness=0.12, gap=0.025):
    """Return seven analytic polygons in normalized full-cell coordinates.

    These are stroke supports, not rectangles averaging background with ink.
    Physical thickness is relative to cell height; nominal cell aspect is .55.
    """
    t, tx = thickness, thickness / .55
    g = gap

    def horizontal(y):
        return [(tx / 2 + g, y), (tx + g, y - t / 2),
                (1 - tx - g, y - t / 2), (1 - tx / 2 - g, y),
                (1 - tx - g, y + t / 2), (tx + g, y + t / 2)]

    def vertical(x, top, bottom):
        return [(x, top + t / 2 + g), (x + tx / 2, top + t + g),
                (x + tx / 2, bottom - t - g), (x, bottom - t / 2 - g),
                (x - tx / 2, bottom - t - g), (x - tx / 2, top + t + g)]

    return {"a": horizontal(t / 2), "b": vertical(1 - tx / 2, 0, .5),
            "c": vertical(1 - tx / 2, .5, 1), "d": horizontal(1 - t / 2),
            "e": vertical(tx / 2, .5, 1), "f": vertical(tx / 2, 0, .5),
            "g": horizontal(.5)}


def _masks(shear, tilt, thickness, gap):
    masks = []
    for polygon in segment_zones(thickness, gap).values():
        points = np.asarray(polygon, np.float32)
        x, y = points[:, 0], points[:, 1]
        # Fit a sheared/tilted cell into its axis-aligned detection rectangle.
        xx = (x + shear * (1 - y) - min(0, shear)) / (1 + abs(shear))
        yy = (y + tilt * (x - .5) + abs(tilt) / 2) / (1 + abs(tilt))
        pts = np.round(np.c_[xx * (WIDTH - 1), yy * (HEIGHT - 1)] * 8).astype(np.int32)
        im = np.zeros((HEIGHT, WIDTH), np.uint8)
        cv2.fillPoly(im, [pts], 255, cv2.LINE_AA, shift=3)
        masks.append(im.ravel().astype(np.float32) / 255)
    return np.asarray(masks).T


@lru_cache(maxsize=1)
def _bank():
    """Deterministic geometric dictionary, constructed once; never data-fitted."""
    y, x = np.mgrid[:HEIGHT, :WIDTH]
    plane = np.stack([np.ones_like(x), x / WIDTH - .5, y / HEIGHT - .5], -1)
    q = np.linalg.qr(plane.reshape(-1, 3).astype(np.float32))[0]
    templates, classes, geometry, masks = [], [], [], []
    patterns = [(c, PATTERN[c]) for c in range(10)]
    patterns.append((7, np.array([s in "abcf" for s in ALL], np.float32)))
    for shear in (-.4, -.2, 0., .2, .4, .6):
        for tilt in (-.18, 0., .18):
            for thickness in (.07, .11, .15, .19):
                for gap in (.0, .035):
                    m = _masks(shear, tilt, thickness, gap)
                    m -= q @ (q.T @ m)
                    index = len(masks)
                    masks.append(m)
                    geometry.append((shear, tilt, thickness, gap))
                    for c, pattern in patterns:
                        for ghost in (0., .25):
                            v = m @ (pattern + ghost * (1 - pattern))
                            v /= max(float(np.linalg.norm(v)), 1e-8)
                            templates.append(v)
                            classes.append((c, index))
    return (np.asarray(templates, np.float32), np.asarray(classes, np.int32),
            q, tuple(geometry), np.asarray(masks, np.float32))


def _extract(gray, box):
    if not isinstance(gray, np.ndarray) or gray.ndim != 2 or gray.size == 0:
        raise ValueError("expected a nonempty grayscale image")
    if gray.dtype != np.uint8:
        raise ValueError("expected uint8 grayscale; convert explicitly before verification")
    values = np.asarray(box, dtype=float)
    if values.shape != (4,) or not np.isfinite(values).all():
        return None
    a, b, c, d = values
    if c <= a or d <= b:
        return None
    h, w = gray.shape
    a, c = max(0., a), min(float(w), c)
    b, d = max(0., b), min(float(h), d)
    if c - a < 2 or d - b < MIN_SIZE:
        return None
    narrow = (c - a) / (d - b) < NARROW_RATIO
    if narrow:
        # Expand only a genuinely narrow observation. Never infer a '1' solely
        # from aspect ratio; the same image evidence still has to fit its strokes.
        a = max(0., c - .55 * (d - b))
    width, height = max(2, round(c - a)), max(2, round(d - b))
    cell = cv2.getRectSubPix(gray, (width, height), ((a + c - 1) / 2, (b + d - 1) / 2))
    cell = cv2.resize(cell, (WIDTH, HEIGHT), interpolation=cv2.INTER_LINEAR)
    return cell.astype(np.float32).ravel(), narrow


def segment_ink(gray_crop, x1, y1, x2, y2):
    """Return measured evidence, or None for invalid/too-small/flat observations.

    Unknown is never represented as perfect agreement. A high correlation is not
    sufficient for production acceptance: glare, occlusion and wrong boxes can
    still resemble a legal pattern. The measured margin is diagnostic only.
    """
    extracted = _extract(gray_crop, (x1, y1, x2, y2))
    if extracted is None:
        return None
    cell, narrow = extracted
    templates, labels, q, geometry, masks = _bank()
    cell -= q @ (q.T @ cell)
    norm = float(np.linalg.norm(cell))
    rms = norm / np.sqrt(cell.size)
    if rms < MIN_RMS_CONTRAST:
        return None
    signed = templates @ (cell / norm)
    scores = np.clip(np.abs(signed), 0, 1)
    class_scores = np.zeros(10, np.float32)
    np.maximum.at(class_scores, labels[:, 0], scores)
    winner = int(np.argmax(scores))
    geom_index = int(labels[winner, 1])
    m = masks[geom_index]
    # Independent continuous stroke measurements, NOT the winning class pattern.
    coeff = np.linalg.lstsq(m, cell, rcond=None)[0]
    polarity = 1 if signed[winner] >= 0 else -1
    contrast = max(float(np.max(polarity * coeff)), MIN_RMS_CONTRAST)
    strengths = np.clip(polarity * coeff / contrast, 0, 1)
    ordered = np.sort(class_scores)
    return SegmentEvidence(strengths, class_scores, float(rms),
                           "light_on_dark" if polarity == 1 else "dark_on_light",
                           geometry[geom_index], narrow, float(ordered[-1]),
                           float(ordered[-1] - ordered[-2]))


def on_pattern(evidence):
    """Diagnostic only: fixed contrast threshold, no per-cell min/max midpoint."""
    return None if evidence is None else evidence.strengths >= .5


def agreement(evidence, cls):
    """Class-specific geometric correlation, not the old seven-bit fraction."""
    if cls not in PATTERN:
        raise ValueError("digit class must be an integer in 0..9")
    return 0.0 if evidence is None else float(evidence.class_scores[cls])


def best_pattern_class(evidence):
    if evidence is None:
        return -1, 0.0
    cls = int(np.argmax(evidence.class_scores))
    return cls, float(evidence.class_scores[cls])


def verify(gray_crop, digits):
    """Annotate without changing the reader's class; return class mismatches.

    Unlike v1, missing evidence is seg_cls=-1, seg_agree=0, seg_valid=False.
    This function does not authorize a Reading.confident policy or autofill.
    """
    mismatches = 0
    for d in digits:
        evidence = segment_ink(gray_crop, d.x1, d.y1, d.x2, d.y2)
        d.seg_agree = agreement(evidence, d.cls)
        d.seg_cls, _ = best_pattern_class(evidence)
        d.seg_valid = evidence is not None
        mismatches += d.seg_cls != d.cls
    return int(mismatches)
