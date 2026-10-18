"""Lab tool: crop absolute pixel box (with margin) from full-res photo and upscale for reading."""
import paths
import sys, cv2
SRC = paths.PHOTOS_S
name, x1, y1, x2, y2 = sys.argv[1], *map(int, sys.argv[2:6])
out = sys.argv[6]
im = cv2.imread(SRC + name + ".jpg"); H, W = im.shape[:2]
mx, my = (x2 - x1) // 6, (y2 - y1) // 4
c = im[max(0, y1 - my):min(H, y2 + my), max(0, x1 - mx):min(W, x2 + mx)]
s = 900 / c.shape[1]; c = cv2.resize(c, (900, int(c.shape[0] * s)), interpolation=cv2.INTER_CUBIC)
cv2.imwrite(out, c)
