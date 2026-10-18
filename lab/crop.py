"""Lab tool: crop normalized region from full-res photo, upscale, and add a CLAHE-enhanced copy below."""
import paths
import sys, cv2, numpy as np
SRC = paths.PHOTOS_S
name, x1, y1, x2, y2 = sys.argv[1], *map(float, sys.argv[2:6])
im = cv2.imread(SRC + name + ".jpg"); H, W = im.shape[:2]
c = im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)]
s = 1000 / c.shape[1]; c = cv2.resize(c, (1000, int(c.shape[0] * s)), interpolation=cv2.INTER_CUBIC)
g = cv2.cvtColor(c, cv2.COLOR_BGR2GRAY)
e = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 8)).apply(g)
cv2.imwrite(paths.REVIEW_S + f"c_{name}.jpg", np.vstack([c, cv2.cvtColor(e, cv2.COLOR_GRAY2BGR)]))
