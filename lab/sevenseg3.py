"""Seven-segment reader v3: lattice fit from vertical strokes + pixel-level segment scoring (no ML).

Why: v1/v2 group "pieces" into digits; stray blobs (frame, glare, kWh) chain digits together. v3 instead uses the
most reliable evidence on any 7-seg display — the VERTICAL strokes (segments b, c, e, f):
1. ink mask (v1) -> deskew -> connected pieces.
2. vertical strokes = pieces taller than wide, with consistent length L (robust median). Decimals have shorter
   strokes and are excluded automatically.
3. digit top/bottom from upper/lower stroke groups.
4. column lattice: every digit has a left bar at x0 + n*P and a right bar at x0 + W + n*P. Brute-force (P, W, x0)
   maximising how many stroke centres sit on the lattice.
5. each lattice cell -> 7 stroke masks -> darkness measured pixel by pixel (v2.measure) -> per-photo ON/OFF
   threshold (v2.two_cluster_threshold) -> nearest digit pattern (v2.classify).
"""
import cv2
import numpy as np

import sevenseg as v1
import sevenseg2 as v2

VERT_ASPECT = 1.8          # piece h/w above this = vertical stroke
LEN_TOL = 0.35             # stroke length within +-35% of the median length
LATTICE_TOL = 0.22         # a stroke centre is "on" the lattice if within 22% of L
PITCH_RANGE = (0.55, 1.6)  # digit pitch in units of digit height
WIDTH_RANGE = (0.30, 0.75) # inner left->right bar distance in units of digit height
GRID_STEPS = 40


def vertical_strokes(mask):
    n, _, st, _ = cv2.connectedComponentsWithStats(mask, 8)
    cand = [(int(st[i][0]), int(st[i][1]), int(st[i][2]), int(st[i][3])) for i in range(1, n)
            if st[i][3] >= VERT_ASPECT * st[i][2] and st[i][3] >= 6]
    if len(cand) < 2:
        return [], 0.0
    L = float(np.median([c[3] for c in cand]))
    return [c for c in cand if abs(c[3] - L) <= LEN_TOL * L], L


def vertical_extent(strokes):
    cy = np.array([s[1] + s[3] / 2 for s in strokes])
    mid = np.median(cy)
    up = [s for s, y in zip(strokes, cy) if y <= mid] or strokes
    lo = [s for s, y in zip(strokes, cy) if y > mid] or strokes
    top = float(np.median([s[1] for s in up]))
    bot = float(np.median([s[1] + s[3] for s in lo]))
    if bot - top < 1.4 * np.median([s[3] for s in strokes]):   # only one row of strokes found
        L = np.median([s[3] for s in strokes])
        top, bot = (top, top + 2.1 * L) if np.median(cy) < mid + 1 else (bot - 2.1 * L, bot)
    return top, bot


def fit_lattice(xs, h, L):
    """Find (pitch, width, x0) maximising stroke centres on {x0+nP} U {x0+W+nP}."""
    xs = np.sort(np.asarray(xs, float))
    tol = LATTICE_TOL * L
    best = (-1, 0.0, None)
    for P in np.linspace(PITCH_RANGE[0] * h, PITCH_RANGE[1] * h, GRID_STEPS):
        for W in np.linspace(WIDTH_RANGE[0] * h, WIDTH_RANGE[1] * h, GRID_STEPS // 2):
            if W >= P - tol:
                continue
            for x0 in xs:                                  # anchor the lattice on an observed stroke
                for anchor in (x0, x0 - W):
                    r = (xs - anchor) % P
                    hit = (np.minimum(r, P - r) < tol) | (np.abs(r - W) < tol)
                    score = int(hit.sum())
                    err = float(np.sum(np.minimum(np.minimum(r, P - r), np.abs(r - W))[hit]))
                    if score > best[0] or (score == best[0] and err < best[1]):
                        best = (score, err, (P, W, anchor))
    return best[2], best[0]


def cells(xs, lattice):
    """Lattice cells (left bar x) that contain at least one stroke, contiguous from first to last."""
    P, W, a = lattice
    idx = sorted({int(np.floor((x - a + 0.3 * P) / P)) for x in xs})
    if not idx:
        return []
    return [a + i * P for i in range(idx[0], idx[-1] + 1)]


def read_line(bgr):
    mask, k = v1.deskew(v1.clean_mask(v1.ink_map(bgr)))
    strokes, L = vertical_strokes(mask)
    if len(strokes) < 2:
        return "", [], {"why": "no vertical strokes"}
    top, bot = vertical_extent(strokes)
    h = bot - top
    xs = [s[0] + s[2] / 2 for s in strokes]
    lattice, score = fit_lattice(xs, h, L)
    if lattice is None:
        return "", [], {"why": "no lattice"}
    P, W, _ = lattice
    lefts = cells(xs, lattice)[: v1.INT_DIGITS]
    stroke = v2.STROKE_FRAC * h
    dark = v1.shear(v2.darkness(bgr, v1.WORK_H), k)
    cell_w = W + stroke                      # outer width = bar-centre distance + one stroke
    segs = []
    for xl in lefts:
        x_right = xl - stroke / 2 + cell_w
        segs.append({s: v2.measure(dark, r) for s, r in v2.stroke_rects(x_right, top, cell_w, h).items()})
    thr, contrast, lo, hi = v2.two_cluster_threshold([v for sg in segs for v in sg.values()])
    if contrast < v2.MIN_CONTRAST:
        return "", [], {"why": "low contrast", "contrast": round(contrast, 2)}
    digits, confs = zip(*(v2.classify(sg, thr, hi - lo) for sg in segs))
    text = "".join(digits)
    return str(int(text)), list(confs), {"raw": text, "n": len(lefts), "P/h": round(P / h, 2),
                                          "W/h": round(W / h, 2), "hits": score, "strokes": len(strokes)}
