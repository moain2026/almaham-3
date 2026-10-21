"""Standard photometric + geometric augmentation for DigitNet training (recipe v2 §3.2,
docs/research/training-standards-2026-10-21.md). numpy + cv2 only. Boxes follow the image.

    im2, boxes2 = augment(im, boxes, kind, rng)      im: HxWx3 uint8 ; boxes: [M,5] (cls,x1,y1,x2,y2) float

Design rules
  * Geometry is ONE affine (rotation+shear+scale+shift) -> boxes are transformed exactly (4 corners -> AABB) and
    boxes that leave the frame (centre outside, or <60% of area kept) are dropped. Border fill = mid grey 128 (the
    app letterboxes with the same grey).
  * Photometric ops never move pixels, so boxes are untouched.
  * `kind` selects ranges: reader (64x448 line crop, small rotations, digit permutation allowed) vs locator (256x256
    scene, larger rotations). Everything is parameterised in AUG so an ablation can switch groups off.
  * Deterministic given rng.
"""
import cv2
import numpy as np

AUG = {
    "reader": {
        "p_geom": 0.6, "rot_deg": 8, "shear": 0.15, "scale": (0.8, 1.2), "shift": 0.06,
        "p_photo": 0.8, "brightness": 0.35, "contrast": (0.6, 1.5), "gamma": (0.6, 1.6), "p_gamma": 0.3,
        "p_hsv": 0.3, "hue": 15, "sat": (0.5, 1.5), "p_gray": 0.15,
        "p_blur": 0.3, "gauss_blur": 1.5, "motion_blur": (3, 7), "p_noise": 0.3, "noise_sigma": 8,
        "p_jpeg": 0.4, "jpeg_q": (35, 95), "p_glare": 0.2, "p_chan_perm": 0.15, "p_digit_perm": 0.2,
    },
    "locator": {
        "p_geom": 0.6, "rot_deg": 12, "shear": 0.12, "scale": (0.75, 1.25), "shift": 0.08,
        "p_photo": 0.8, "brightness": 0.35, "contrast": (0.6, 1.5), "gamma": (0.6, 1.6), "p_gamma": 0.3,
        "p_hsv": 0.3, "hue": 15, "sat": (0.5, 1.5), "p_gray": 0.15,
        "p_blur": 0.3, "gauss_blur": 1.5, "motion_blur": (3, 7), "p_noise": 0.3, "noise_sigma": 8,
        "p_jpeg": 0.4, "jpeg_q": (35, 95), "p_glare": 0.2, "p_chan_perm": 0.15, "p_digit_perm": 0.0,
    },
}
GREY = (128, 128, 128)
MIN_KEEP_AREA = 0.6


def _affine(im, boxes, cfg, rng):
    h, w = im.shape[:2]
    ang = rng.uniform(-cfg["rot_deg"], cfg["rot_deg"])
    sc = rng.uniform(*cfg["scale"])
    sh = rng.uniform(-cfg["shear"], cfg["shear"])
    tx, ty = rng.uniform(-cfg["shift"], cfg["shift"]) * w, rng.uniform(-cfg["shift"], cfg["shift"]) * h
    M = cv2.getRotationMatrix2D((w / 2, h / 2), ang, sc)          # 2x3
    S = np.array([[1, sh, -sh * h / 2], [0, 1, 0]], np.float64)   # shear about centre
    M3 = np.vstack([M, [0, 0, 1]]) @ np.vstack([S, [0, 0, 1]])
    M3[0, 2] += tx
    M3[1, 2] += ty
    out = cv2.warpAffine(im, M3[:2], (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=GREY)
    if len(boxes) == 0:
        return out, boxes
    b = np.asarray(boxes, np.float32)
    x1, y1, x2, y2 = b[:, 1], b[:, 2], b[:, 3], b[:, 4]
    corners = np.stack([np.stack([x1, y1], 1), np.stack([x2, y1], 1), np.stack([x2, y2], 1), np.stack([x1, y2], 1)], 1)  # M,4,2
    ones = np.ones((*corners.shape[:2], 1), np.float32)
    pc = np.concatenate([corners, ones], 2) @ M3[:2].T.astype(np.float32)  # M,4,2
    nx1, ny1 = pc[:, :, 0].min(1), pc[:, :, 1].min(1)
    nx2, ny2 = pc[:, :, 0].max(1), pc[:, :, 1].max(1)
    area = (nx2 - nx1) * (ny2 - ny1)
    cx1, cy1, cx2, cy2 = np.clip(nx1, 0, w), np.clip(ny1, 0, h), np.clip(nx2, 0, w), np.clip(ny2, 0, h)
    carea = np.clip(cx2 - cx1, 0, None) * np.clip(cy2 - cy1, 0, None)
    keep = (carea >= MIN_KEEP_AREA * np.maximum(area, 1e-6)) & (cx2 > cx1 + 1) & (cy2 > cy1 + 1)
    nb = np.stack([b[:, 0], cx1, cy1, cx2, cy2], 1)[keep]
    return out, nb


def _photometric(im, cfg, rng):
    im = im.astype(np.float32)
    if rng.random() < cfg["p_photo"]:
        a = rng.uniform(*cfg["contrast"])
        bshift = rng.uniform(-cfg["brightness"], cfg["brightness"]) * 255
        im = (im - 128) * a + 128 + bshift
    if rng.random() < cfg["p_gamma"] and im.mean() > 40:  # do not stack gamma on an already-dark frame
        g = rng.uniform(*cfg["gamma"])
        im = 255.0 * np.power(np.clip(im, 0, 255) / 255.0, g)
    im = np.clip(im, 0, 255).astype(np.uint8)
    if rng.random() < cfg["p_hsv"]:
        hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV).astype(np.int32)
        hsv[..., 0] = (hsv[..., 0] + rng.integers(-cfg["hue"], cfg["hue"] + 1)) % 180
        hsv[..., 1] = np.clip(hsv[..., 1] * rng.uniform(*cfg["sat"]), 0, 255)
        im = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    if rng.random() < cfg["p_gray"]:
        g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        im = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
    if rng.random() < cfg["p_chan_perm"]:
        im = im[..., rng.permutation(3)]
    if rng.random() < cfg["p_blur"]:
        if rng.random() < 0.5:
            s = rng.uniform(0.3, cfg["gauss_blur"])
            im = cv2.GaussianBlur(im, (0, 0), s)
        else:
            k = int(rng.integers(cfg["motion_blur"][0], cfg["motion_blur"][1] + 1))
            kern = np.zeros((k, k), np.float32)
            if rng.random() < 0.5:
                kern[k // 2, :] = 1.0
            else:
                kern[:, k // 2] = 1.0
            im = cv2.filter2D(im, -1, kern / k)
    if rng.random() < cfg["p_noise"]:
        n = rng.normal(0, rng.uniform(1, cfg["noise_sigma"]), im.shape).astype(np.float32)
        im = np.clip(im.astype(np.float32) + n, 0, 255).astype(np.uint8)
    if rng.random() < cfg["p_glare"]:
        h, w = im.shape[:2]
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        rx, ry = rng.uniform(0.15, 0.5) * w, rng.uniform(0.3, 1.0) * h
        yy, xx = np.mgrid[0:h, 0:w]
        g = np.exp(-(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2))
        im = np.clip(im.astype(np.float32) + (g[..., None] * rng.uniform(60, 160)), 0, 255).astype(np.uint8)
    if rng.random() < cfg["p_jpeg"]:
        q = int(rng.integers(cfg["jpeg_q"][0], cfg["jpeg_q"][1] + 1))
        ok, enc = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])
        if ok:
            im = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return im


def _digit_permutation(im, boxes, rng):
    """Swap the pixel content of two digit cells of similar size on the same line (S1 Copel-AMR trick): breaks
    position/class correlation. Labels follow the content. Only cls 0..9 boxes, only when >=3 digits."""
    b = np.asarray(boxes, np.float32)
    idx = [i for i in range(len(b)) if 0 <= b[i, 0] <= 9]
    if len(idx) < 3:
        return im, boxes
    i, j = rng.choice(idx, 2, replace=False)
    bi, bj = b[i], b[j]
    hi, wi = bi[4] - bi[2], bi[3] - bi[1]
    hj, wj = bj[4] - bj[2], bj[3] - bj[1]
    if hi <= 2 or hj <= 2 or wi <= 2 or wj <= 2 or abs(hi - hj) > 0.2 * max(hi, hj):
        return im, boxes
    out = im.copy()
    ri = (slice(int(bi[2]), int(bi[4])), slice(int(bi[1]), int(bi[3])))
    rj = (slice(int(bj[2]), int(bj[4])), slice(int(bj[1]), int(bj[3])))
    pi, pj = im[ri].copy(), im[rj].copy()
    if pi.size == 0 or pj.size == 0:
        return im, boxes
    out[ri] = cv2.resize(pj, (pi.shape[1], pi.shape[0]))
    out[rj] = cv2.resize(pi, (pj.shape[1], pj.shape[0]))
    nb = b.copy()
    nb[i, 0], nb[j, 0] = b[j, 0], b[i, 0]
    return out, nb


def augment(im, boxes, kind="reader", rng=None, cfg=None):
    rng = rng if rng is not None else np.random.default_rng()
    cfg = cfg or AUG[kind]
    boxes = np.asarray(boxes, np.float32).reshape(-1, 5)
    if cfg["p_digit_perm"] > 0 and rng.random() < cfg["p_digit_perm"]:
        im, boxes = _digit_permutation(im, boxes, rng)
    if rng.random() < cfg["p_geom"]:
        im, boxes = _affine(im, boxes, cfg, rng)
    im = _photometric(np.ascontiguousarray(im), cfg, rng)
    return im, boxes
