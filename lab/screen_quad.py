"""CamScanner-style LCD screen finder: no learning. Inside the user's rectangle, find the largest bright,
low-saturation quadrilateral (the LCD glass), order its corners and perspective-warp it to a flat canonical
screen. Then the reading line is simply the tallest digit row of that flat screen.

    quad, warped = find_screen(crop_bgr)      # quad: 4x2 float (tl,tr,br,bl) in crop pixels or None
Design: pure OpenCV, ~5 ms. Mirrors line-by-line to Kotlin later if it measures well on the 49.
"""
import cv2
import numpy as np

CFG = {"MIN_AREA_FRAC": 0.04, "MAX_AREA_FRAC": 0.95, "ASPECT_MIN": 1.2, "ASPECT_MAX": 6.0,
       "APPROX_EPS": 0.03, "OUT_W": 448, "SAT_MAX": 120, "VAL_MIN": 70}


def _order(pts):
    pts = np.asarray(pts, np.float32).reshape(4, 2)
    s = pts.sum(1); d = np.diff(pts, axis=1).ravel()
    return np.array([pts[s.argmin()], pts[d.argmin()], pts[s.argmax()], pts[d.argmax()]], np.float32)


def _candidates(mask, area):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    out = []
    for c in cnts:
        a = cv2.contourArea(c)
        if a < CFG["MIN_AREA_FRAC"] * area or a > CFG["MAX_AREA_FRAC"] * area:
            continue
        peri = cv2.arcLength(c, True)
        ap = cv2.approxPolyDP(c, CFG["APPROX_EPS"] * peri, True)
        if len(ap) == 4 and cv2.isContourConvex(ap):
            q = _order(ap)
        else:  # fall back to the min-area rectangle of the blob
            q = _order(cv2.boxPoints(cv2.minAreaRect(c)))
        w = max(np.linalg.norm(q[1] - q[0]), np.linalg.norm(q[2] - q[3]))
        h = max(np.linalg.norm(q[3] - q[0]), np.linalg.norm(q[2] - q[1]))
        if h < 8 or not (CFG["ASPECT_MIN"] <= w / h <= CFG["ASPECT_MAX"]):
            continue
        rect_fill = a / max(1.0, w * h)   # how rectangular the blob is
        out.append((a * rect_fill, q, w, h))
    return out


def _masks(bgr):
    """Several views of 'where could the LCD glass be'. Measured on the 49: no single cue works for all
    meter types (MT10 glass is DARK grey on yellow; TOMAS glass is as bright as its white housing; Emeter glass
    is grey inside a green PCB) so we try bright-unsaturated, dark-unsaturated, Otsu both polarities and closed edges."""
    H, W = bgr.shape[:2]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    s, v = hsv[..., 1], hsv[..., 2]
    low_sat = s <= CFG["SAT_MAX"]
    v_hi = max(CFG["VAL_MIN"], int(np.percentile(v, 55)))
    v_lo = int(np.percentile(v, 45))
    g = cv2.GaussianBlur(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), (5, 5), 0)
    _, otsu = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    med = np.median(g)
    edges = cv2.Canny(g, max(10, 0.66 * med), min(255, 1.33 * med))
    ke = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, W // 40), max(3, H // 40)))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, ke)
    # regions enclosed by edges: fill holes of the edge map
    filled = edges.copy(); ff = np.zeros((H + 2, W + 2), np.uint8)
    cv2.floodFill(filled, ff, (0, 0), 255); enclosed = cv2.bitwise_not(filled) | edges
    return [((v >= v_hi) & low_sat).astype(np.uint8) * 255,
            ((v <= v_lo) & low_sat).astype(np.uint8) * 255,
            otsu, cv2.bitwise_not(otsu), enclosed]


def find_screen(bgr):
    H, W = bgr.shape[:2]
    area = H * W
    k = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, W // 60), max(3, H // 60)))
    cands = []
    for m in _masks(bgr):
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)
        m = cv2.morphologyEx(m, cv2.MORPH_OPEN, k)
        cands += _candidates(m, area)
    if not cands:
        return None, None
    if CFG.get("SCORE", "digits") == "digits":
        # Prefer the rectangle that contains digit-like strokes: dense vertical edges (7-segment stems) inside,
        # relative to its area. Pure size picks the housing/label too often (measured: 11/46).
        g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        sob = cv2.convertScaleAbs(cv2.Sobel(g, cv2.CV_16S, 1, 0, ksize=3))
        rescored = []
        for a, q, w, h in cands:
            m = np.zeros((H, W), np.uint8); cv2.fillConvexPoly(m, q.astype(np.int32), 255)
            dens = float(cv2.mean(sob, m)[0])
            rescored.append((dens * np.sqrt(a), q, w, h))
        cands = rescored
    score, q, w, h = max(cands, key=lambda t: t[0])
    ow = CFG["OUT_W"]; oh = max(16, int(round(ow * h / w)))
    M = cv2.getPerspectiveTransform(q, np.array([[0, 0], [ow, 0], [ow, oh], [0, oh]], np.float32))
    warped = cv2.warpPerspective(bgr, M, (ow, oh), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(128, 128, 128))
    return q, warped


if __name__ == "__main__":
    import json, sys, csv
    import paths
    gt = list(csv.DictReader(open(paths.GROUND_TRUTH, encoding="utf-8")))
    boxes = json.load(open(paths.METER_BOXES)); disp = json.load(open(paths.DISPLAY_BOXES))
    found = hit = 0; rows = []
    for g in gt:
        fn = g["filename"]; im = cv2.imread(paths.photo(fn)); H, W = im.shape[:2]
        x1, y1, x2, y2 = boxes[fn]; ox, oy = int(x1 * W), int(y1 * H)
        crop = im[oy:int(y2 * H), ox:int(x2 * W)]
        q, warped = find_screen(crop)
        # reference display box (eval only) in crop coords
        d = disp.get(fn)   # unreadable photos have no reference display box
        ref = (d[0] * W - ox, d[1] * H - oy, d[2] * W - ox, d[3] * H - oy) if d else None
        iou = 0.0
        if q is not None and ref is not None:
            found += 1
            bx = (q[:, 0].min(), q[:, 1].min(), q[:, 0].max(), q[:, 1].max())
            ix = max(0, min(bx[2], ref[2]) - max(bx[0], ref[0])); iy = max(0, min(bx[3], ref[3]) - max(bx[1], ref[1]))
            inter = ix * iy; ua = (bx[2] - bx[0]) * (bx[3] - bx[1]) + (ref[2] - ref[0]) * (ref[3] - ref[1]) - inter
            iou = inter / ua if ua > 0 else 0
            hit += iou > 0.5
            vis = crop.copy(); cv2.polylines(vis, [q.astype(int)], True, (0, 255, 0), 3)
            cv2.rectangle(vis, (int(ref[0]), int(ref[1])), (int(ref[2]), int(ref[3])), (0, 0, 255), 2)
            s = 300 / vis.shape[1]; vis = cv2.resize(vis, (300, int(vis.shape[0] * s)))
            wv = cv2.resize(warped, (300, int(300 * warped.shape[0] / warped.shape[1])))
            pane = np.full((max(vis.shape[0], wv.shape[0]) + 20, 620, 3), 128, np.uint8)
            pane[:vis.shape[0], :300] = vis; pane[:wv.shape[0], 320:620] = wv
            cv2.putText(pane, f"{fn} iou={iou:.2f} truth={g['reading']}", (4, pane.shape[0] - 5), 0, 0.5, (0, 0, 255) if iou <= 0.5 else (0, 160, 0), 1)
            rows.append(pane)
        print(f"{fn} found={q is not None} iou={iou:.2f} {g['meter_type']}")
    print(f"\nscreen quad found {found}/49, IoU>0.5 vs reference display box: {hit}/{len(disp)}")
    if rows:
        hmax = max(r.shape[0] for r in rows)
        sheet = np.vstack([np.vstack([r, np.full((hmax - r.shape[0], 620, 3), 128, np.uint8)]) for r in rows])
        cv2.imwrite("/tmp/screen_quad_sheet.jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 70])
