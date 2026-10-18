"""Recall of locate.candidates vs reference line boxes (mode A crops)."""
import paths
import cv2, json, numpy as np
import locate
S = paths.PHOTOS_S
mb = json.load(open(paths.METER_BOXES)); lb = json.load(open(paths.LINE_BOXES))
hit = 0; ranks = []; miss = []
for fn, (lx1, ly1, lx2, ly2) in sorted(lb.items()):
    im = cv2.imread(S + fn); H, W = im.shape[:2]; x1, y1, x2, y2 = mb[fn]
    ox, oy = int(x1 * W), int(y1 * H); A = im[oy:int(y2 * H), ox:int(x2 * W)]
    ref = (lx1 * W - ox, ly1 * H - oy, lx2 * W - ox, ly2 * H - oy)
    cs = locate.candidates(A); r = None
    for i, c in enumerate(cs):
        ix = max(0, min(c[2], ref[2]) - max(c[0], ref[0])); iy = max(0, min(c[3], ref[3]) - max(c[1], ref[1]))
        cov = ix * iy / ((ref[2] - ref[0]) * (ref[3] - ref[1]))  # fraction of ref covered
        prec = ix * iy / max(1, (c[2] - c[0]) * (c[3] - c[1]))
        if cov > 0.6 and prec > 0.35: r = i; break
    if r is None: miss.append(fn[:5])
    else: hit += 1; ranks.append(r)
print(f"recall {hit}/{len(lb)} rank hist {np.bincount(ranks)} miss {miss}")
