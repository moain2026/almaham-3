"""Lab tool: per-channel max-contrast view of a faint LCD crop (tiles B,G,R,LAB-L after background flattening)."""
import paths
import sys, cv2, numpy as np
SRC = paths.PHOTOS_S
name, x1, y1, x2, y2, out = sys.argv[1], *map(float, sys.argv[2:6]), sys.argv[6]
im = cv2.imread(SRC + name + ".jpg"); H, W = im.shape[:2]
c = im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)]
s = 1000 / c.shape[1]; c = cv2.resize(c, (1000, int(c.shape[0] * s)), interpolation=cv2.INTER_CUBIC)
lab = cv2.cvtColor(c, cv2.COLOR_BGR2LAB)
outs = []
for ch in [c[:, :, 0], c[:, :, 1], lab[:, :, 0]]:
    g = cv2.medianBlur(ch, 5).astype(np.float32)
    bg = cv2.morphologyEx(g, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (61, 61)))
    d = cv2.normalize(bg - g, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    outs.append(cv2.cvtColor(255 - d, cv2.COLOR_GRAY2BGR))
cv2.imwrite(out, np.vstack(outs))
