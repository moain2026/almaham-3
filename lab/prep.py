"""Shared preprocessing for the line recognizer (must mirror the Kotlin implementation exactly)."""
import cv2
import numpy as np

IN_H, IN_W = 48, 192


def to_input(bgr):
    """BGR crop -> float32 [1,48,192] in [0,1]: gray, keep aspect, pad right with edge mean, per-image min-max."""
    g = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY) if bgr.ndim == 3 else bgr
    h, w = g.shape
    nw = max(1, min(IN_W, int(round(w * IN_H / h))))
    r = cv2.resize(g, (nw, IN_H), interpolation=cv2.INTER_AREA if h > IN_H else cv2.INTER_LINEAR).astype(np.float32)
    lo, hi = np.percentile(r, 1), np.percentile(r, 99)
    r = np.clip((r - lo) / max(hi - lo, 1.0), 0, 1)
    out = np.full((IN_H, IN_W), float(np.median(r[:, -2:])), np.float32)
    out[:, :nw] = r
    return out[None]
