import paths
import os, json, cv2
from yolo_onnx import YoloDetector
M = paths.ERP_VISION_S
SRC = str(paths.PHOTOS)
OUT = str(paths.REVIEW / "lcd")
os.makedirs(OUT, exist_ok=True)
det = YoloDetector(M + "lcd-detector-v1.onnx", 8)
res = {}
for f in sorted(os.listdir(SRC)):
    im = cv2.imread(os.path.join(SRC, f))
    boxes = det.detect(im, 0.25, 0.5)
    res[f] = [[round(b.x1), round(b.y1), round(b.x2), round(b.y2), round(b.score, 3), b.cls] for b in boxes]
    print(f, len(boxes), [r[4] for r in res[f]])
json.dump(res, open(paths.ERP_LCD_BOXES, "w"), indent=1)
