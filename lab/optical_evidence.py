"""Experimental no-training reader: local illumination cancellation + erasure decoding.

Not a production confidence estimator. Geometry proposals reuse v1/v6, not their
predicted digits. All per-capture fits are unsupervised; no truth or file IDs enter
inference. A singleton codeword is conditional evidence, NOT a calibrated 99% claim.
"""
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
import math

import cv2
import numpy as np

import sevenseg as v1
import sevenseg2 as v2
import sevenseg6 as v6


@dataclass(frozen=True)
class Config:
    patch_width: int = 40
    patch_height: int = 72
    min_boxes: int = 3
    lattice_tolerance: float = 0.24
    max_cells: int = 10
    min_contrast: float = 0.06
    ambiguity_fraction: float = 0.18
    segment_quantile: float = 65.0
    background_floor: float = 16.0
    jitter: tuple = (-1.0, 0.0, 1.0)
    # Reference windows lie in the holes, NOT on an inactive segment assumed OFF.
    background_windows: tuple = ((.34, .22, .66, .36), (.34, .64, .66, .78))


DEFAULT = Config()
PATTERNS = tuple((d, tuple(int(s in p) for s in v1.SEG_ORDER))
                 for d, p in list(v1.DIGITS.items()) + list(v1.ALT.items()))


def decode_erasure(states):
    """All legal digits matching known bits; None/-1 means unobserved, not OFF.

    We NEVER flip a known bit to force a digit, unlike nearest-pattern matching.
    Multiple physical glyphs for the same digit count once.
    """
    if len(states) != 7 or any(s not in (-1, None, 0, 1) for s in states):
        raise ValueError('expected seven ternary segment states')
    return sorted({d for d, bits in PATTERNS
                   if all(s in (-1, None) or s == b for s, b in zip(states, bits))})


def code_distance():
    return min(sum(a != b for a, b in zip(p, q))
               for (d, p), (e, q) in combinations(PATTERNS, 2) if d != e)


def zero_error_upper_bound(n, alpha=0.05):
    """One-sided exact binomial bound, ONLY for n independent zero-error trials."""
    if n < 0 or not 0 < alpha < 1:
        raise ValueError('invalid sample count or alpha')
    return 1.0 if n == 0 else -math.expm1(math.log(alpha) / n)


def _unique_winner(values, min_share):
    if not values:
        return '', 0.0
    counts = Counter(values)
    ranked = counts.most_common()
    text, votes = ranked[0]
    share = votes / len(values)  # empty predictions remain in the denominator
    tied = len(ranked) > 1 and ranked[1][1] == votes
    return (text if text and not tied and share >= min_share else ''), share


def family_consensus(examinations, required_families=2, min_share=0.5):
    """One vote per reader family; repeated transformations never add votes.

    examinations = iterable of (family, variant_id, text). Duplicate variant IDs
    are idempotent; conflicting results for one ID are rejected. Reader families
    can STILL share systematic errors, so agreement is NOT a probability.
    """
    if required_families < 1 or not 0 < min_share <= 1:
        raise ValueError('invalid consensus configuration')
    groups = defaultdict(dict)
    for family, variant, text in examinations:
        if variant in groups[family] and groups[family][variant] != text:
            raise ValueError('conflicting duplicate examination')
        groups[family][variant] = text
    winners = {f: _unique_winner(list(v.values()), min_share)[0]
               for f, v in groups.items()}
    nonempty = [v for v in winners.values() if v]
    accepted = (len(nonempty) >= required_families and len(set(nonempty)) == 1)
    return {'value': nonempty[0] if accepted else '', 'family_winners': winners,
            'supporting_families': len(nonempty) if accepted else 0}


def _robust_line(xs, ys):
    slopes = [(ys[j] - ys[i]) / (xs[j] - xs[i])
              for i, j in combinations(range(len(xs)), 2) if abs(xs[j] - xs[i]) > 1]
    slope = float(np.median(slopes)) if slopes else 0.0
    return slope, float(np.median(ys - slope * xs))


def _lattice(boxes, shape, cfg):
    if len(boxes) < cfg.min_boxes:
        return None
    boxes = np.asarray(boxes, dtype=float)
    top, height, width, pitch, right0, n = v2.geometry(boxes)
    if width < 3 or height < 8 or pitch <= width * .8 or not 2 <= n <= cfg.max_cells:
        return None
    rights = boxes[:, 0] + boxes[:, 2]
    indices = np.rint((rights - right0) / pitch).astype(int)
    residual = np.abs(rights - (right0 + indices * pitch)) / pitch
    if residual.max() > cfg.lattice_tolerance or len(set(indices)) != len(indices):
        return None
    # A robust baseline accommodates tilted displays. Narrow 1 and shortened 4
    # must not drag the common top/bottom estimates down.
    full = (boxes[:, 3] >= .9 * height) & (boxes[:, 2] >= .65 * width)
    if full.sum() < 2:
        full = np.ones(len(boxes), dtype=bool)
    xt = rights[full]
    st, bt = _robust_line(xt, boxes[full, 1])
    sb, bb = _robust_line(xt, boxes[full, 1] + boxes[full, 3])
    cells = []
    for i in range(n):
        right = right0 + i * pitch
        hits = np.where(indices == i)[0]
        if hits.size:
            right = float(rights[hits[0]])
        y0, y1 = st * right + bt, sb * right + bb
        cells.append([right - width, y0, right, y1])
    h, w = shape
    if any(x0 < 0 or y0 < 0 or x1 > w or y1 > h for x0, y0, x1, y1 in cells):
        return None
    return {'cells': cells, 'pitch': pitch, 'residual': float(residual.mean()),
            'observed': len(boxes), 'inserted': n - len(boxes)}


def propose_geometry(bgr, cfg=DEFAULT):
    h, w = bgr.shape[:2]
    # Proposal coordinates are fixed by the existing v1 geometry implementation.
    im = cv2.resize(bgr, (max(1, round(w * v1.WORK_H / h)), v1.WORK_H))
    mask, shear = v1.deskew(v1.clean_mask(v1.ink_map(im)))
    aligned = cv2.merge([v1.shear(channel, shear) for channel in cv2.split(im)])
    proposals = []
    for source, boxes in [('v1', v1.digit_boxes(mask)), ('v6', v6.main_boxes(mask)[0])]:
        p = _lattice(boxes, mask.shape, cfg)
        if p is not None:
            p.update(source=source, shear=shear)
            proposals.append(p)
    if not proposals:
        return aligned, None
    # Geometry only; no numeral likelihood or reference answer influences selection.
    best = max(proposals, key=lambda p: (p['observed'], -p['residual'], -p['inserted']))
    return aligned, best


def _patch(im, cell, dx, dy, cfg):
    x0, y0, x1, y1 = cell
    xs = np.linspace(x0 + dx, x1 + dx, cfg.patch_width, endpoint=False)
    ys = np.linspace(y0 + dy, y1 + dy, cfg.patch_height, endpoint=False)
    mx, my = np.meshgrid(xs.astype('float32'), ys.astype('float32'))
    return cv2.remap(im, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def local_contrast(patch, cfg=DEFAULT):
    """Cancel a robust RGB illumination plane using both internal blank holes.

    Each RGB channel has its own plane; the minimum relative darkening suppresses
    coloured ghosts. This is a nuisance fit to ONE capture, not trained OCR.
    """
    h, w = patch.shape[:2]
    yy, xx = np.mgrid[:h, :w].astype(float)
    xx, yy = xx / w, yy / h
    design = np.stack([np.ones_like(xx), xx, yy], axis=-1)
    holes = np.zeros((h, w), dtype=bool)
    for x0, y0, x1, y1 in cfg.background_windows:
        holes |= (xx >= x0) & (xx < x1) & (yy >= y0) & (yy < y1)
    a, y = design[holes], patch[holes].astype(float)
    coef = np.linalg.lstsq(a, y, rcond=None)[0]
    # Two deterministic robust reweighting steps limit scratches in reference holes.
    for _ in range(2):
        residual = np.linalg.norm(y - a @ coef, axis=1)
        scale = max(float(np.median(residual)), 1.0)
        weights = np.minimum(1.0, 2 * scale / np.maximum(residual, 1e-9))[:, None]
        coef = np.linalg.lstsq(a * np.sqrt(weights), y * np.sqrt(weights), rcond=None)[0]
    bg = design @ coef
    relative = (bg - patch.astype(float)) / np.maximum(bg, cfg.background_floor)
    return np.clip(relative.min(axis=2), 0, 1)


def measure_segments(contrast, cfg=DEFAULT):
    h, w = contrast.shape
    values = []
    for s in v1.SEG_ORDER:
        x0, y0, x1, y1 = v1.WIN[s]
        win = contrast[int(y0 * h):max(int(y0 * h) + 1, int(y1 * h)),
                       int(x0 * w):max(int(x0 * w) + 1, int(x1 * w))]
        values.append(float(np.percentile(win, cfg.segment_quantile)))
    return values


def read_evidence(bgr, expected_cells=None, cfg=DEFAULT):
    """Return a top-1 diagnostic and a conservative, geometry-conditional reading.

    expected_cells must come from independently known meter metadata. Unknown
    format never auto-accepts. Ambiguity at any cell leaves the field empty.
    """
    if (not isinstance(bgr, np.ndarray) or bgr.dtype != np.uint8
            or bgr.ndim != 3 or bgr.shape[2] != 3 or min(bgr.shape[:2]) < 8):
        raise ValueError('expected a nonempty uint8 BGR line crop, at least 8x8')
    if expected_cells is not None and not 1 <= expected_cells <= cfg.max_cells:
        raise ValueError('unsupported expected cell count')
    aligned, geometry = propose_geometry(bgr, cfg)
    base = {'value': '', 'top1': '', 'status': 'no_geometry', 'geometry': geometry,
            'calibrated_probability': None}
    if geometry is None:
        return base
    observations = []
    for dx, dy in [(0, 0)] + [(d, 0) for d in cfg.jitter if d] + [(0, d) for d in cfg.jitter if d]:
        observations.append([measure_segments(local_contrast(_patch(aligned, c, dx, dy, cfg), cfg), cfg)
                             for c in geometry['cells']])
    observations = np.asarray(observations)
    central = observations[0]
    _, spread, low, high = v2.two_cluster_threshold(central.ravel())
    base['contrast'] = float(spread)
    if spread < cfg.min_contrast:
        base['status'] = 'low_contrast'
        return base
    threshold = (low + high) / 2
    lower, upper = observations.min(0), observations.max(0)
    guard = cfg.ambiguity_fraction * spread
    states = np.where(lower > threshold + guard, 1,
                      np.where(upper < threshold - guard, 0, -1))
    candidates = [decode_erasure(s.tolist()) for s in states]
    top1 = ''.join(v2.classify(dict(zip(v1.SEG_ORDER, row)), threshold, spread)[0] for row in central)
    base.update(top1=str(int(top1)), raw_top1=top1, candidates=candidates,
                states=states.tolist(), segment_scores=central.round(5).tolist(),
                threshold=float(threshold), status='ambiguous')
    if any(not c for c in candidates):
        base['status'] = 'inconsistent_segments'
    elif expected_cells is None:
        base['status'] = 'unknown_meter_format'
    elif len(candidates) != expected_cells:
        base['status'] = 'format_mismatch'
    elif all(len(c) == 1 for c in candidates):
        base.update(value=str(int(''.join(c[0] for c in candidates))), status='conditional_singleton')
    return base
