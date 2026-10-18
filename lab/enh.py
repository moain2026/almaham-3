"""Lab tool: strong enhancement for faint LCDs (illumination flattening + CLAHE + per-channel view)."""
import paths
import sys, cv2, numpy as np
SRC = paths.PHOTOS_S
name, x1, y1, x2, y2 = sys.argv[1], *map(float, sys.argv[2:6])
im = cv2.imread(SRC + name + ".jpg"); H, W = im.shape[:2]
c = im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)]
s = 1000 / c.shape[1]; c = cv2.resize(c, (1000, int(c.shape[0] * s)), interpolation=cv2.INTER_CUBIC)
outs = [c]
for ch in [cv2.cvtColor(c, cv2.COLOR_BGR2GRAY), c[:, :, 2]]:
    g = cv2.GaussianBlur(ch, (0, 0), 2).astype(np.float32)
    bg = cv2.GaussianBlur(g, (0, 0), 40)
    flat = cv2.normalize(g / (bg + 1), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    e = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(2, 6)).apply(flat)
    outs.append(cv2.cvtColor(e, cv2.COLOR_GRAY2BGR))
cv2.imwrite(paths.REVIEW_S + f"e_{name}.jpg", np.vstack(outs))
