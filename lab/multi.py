"""Lab tool: stack several normalized crops (name x1 y1 x2 y2 ...) into one review sheet with CLAHE."""
import paths
import sys, cv2, numpy as np
SRC = paths.PHOTOS_S
a = sys.argv[2:]; rows = []
for i in range(0, len(a), 5):
    n, x1, y1, x2, y2 = a[i], *map(float, a[i+1:i+5])
    im = cv2.imread(SRC + n + ".jpg"); H, W = im.shape[:2]
    c = im[int(y1*H):int(y2*H), int(x1*W):int(x2*W)]
    c = cv2.resize(c, (900, int(c.shape[0]*900/c.shape[1])), interpolation=cv2.INTER_CUBIC)
    e = cv2.createCLAHE(3.0, (4, 8)).apply(cv2.cvtColor(c, cv2.COLOR_BGR2GRAY))
    r = np.hstack([c, cv2.cvtColor(e, cv2.COLOR_GRAY2BGR)])
    cv2.putText(r, n, (5, 30), 0, 1, (0, 0, 255), 2); rows.append(r)
cv2.imwrite(sys.argv[1], np.vstack(rows))
