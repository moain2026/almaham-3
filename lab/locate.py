"""Classical candidate generation for the main reading line inside a meter crop (mirrors Kotlin LineLocator).

Idea: seven-segment digits are dark, tall, thin strokes arranged in a horizontal row on a lighter LCD.
1. work on a small gray copy (long side = WORK_SIDE)
2. black-hat (closing - image) highlights dark strokes thinner than the kernel
3. Otsu threshold, horizontal closing merges digits of one line into one blob
4. connected components -> boxes filtered by aspect/size, ranked by area*fill
"""
import cv2

WORK_SIDE = 480
BLACKHAT_FRAC = (0.035, 0.06)      # kernel size as fraction of work width (two scales)
CLOSE_W_FRAC, CLOSE_H_FRAC = 0.05, 0.012
MIN_ASPECT, MAX_ASPECT = 1.6, 14.0
MIN_H_FRAC, MAX_H_FRAC = 0.025, 0.35
MIN_W_FRAC = 0.12
MAX_CANDIDATES = 8
PAD_X, PAD_Y = 0.06, 0.22


def candidates(bgr):
    h0, w0 = bgr.shape[:2]
    s = WORK_SIDE / max(h0, w0)
    g = cv2.cvtColor(cv2.resize(bgr, (max(1, int(w0 * s)), max(1, int(h0 * s))), interpolation=cv2.INTER_AREA),
                     cv2.COLOR_BGR2GRAY)
    h, w = g.shape
    out = []
    for frac in BLACKHAT_FRAC:
        k = max(3, int(w * frac)) | 1
        bh = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
        _, th = cv2.threshold(bh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        cw, ch = max(3, int(w * CLOSE_W_FRAC)), max(1, int(h * CLOSE_H_FRAC))
        m = cv2.morphologyEx(th, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (cw, ch)))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, 8)
        for i in range(1, n):
            x, y, bw, bhh, area = st[i]
            if bhh < MIN_H_FRAC * h or bhh > MAX_H_FRAC * h or bw < MIN_W_FRAC * w:
                continue
            a = bw / bhh
            if a < MIN_ASPECT or a > MAX_ASPECT:
                continue
            fill = th[y:y + bhh, x:x + bw].mean() / 255
            if fill < 0.12 or fill > 0.75:
                continue
            score = bhh * bw * fill
            out.append((score, x, y, bw, bhh))
    out.sort(reverse=True)
    boxes = []
    for score, x, y, bw, bhh in out:
        px, py = bw * PAD_X, bhh * PAD_Y
        b = (max(0, (x - px) / s), max(0, (y - py) / s), min(w0, (x + bw + px) / s), min(h0, (y + bhh + py) / s))
        if all(_iou(b, c) < 0.6 for c in boxes):
            boxes.append(b)
        if len(boxes) >= MAX_CANDIDATES:
            break
    return boxes


def _iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy
    return i / max(1e-6, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i)
