"""Visualize DB text-line detections (PP-OCR det) on rect-mode crops to measure display-line recall."""
import paths
import sys, cv2, numpy as np
from rapidocr.ch_ppocr_det.utils import DBPostProcess, DetPreProcess
import onnxruntime as ort
import gt

model, side = sys.argv[1], int(sys.argv[2])
sess = ort.InferenceSession(paths.MODELS_S + f"{model}.onnx", providers=["CPUExecutionProvider"])
pre = DetPreProcess(side, "max", [0.5] * 3, [0.5] * 3)
post = DBPostProcess(thresh=0.3, box_thresh=0.5, max_candidates=1000, unclip_ratio=1.6, use_dilation=True, score_mode="fast")
tiles = []
for it in gt.load():
    im = gt.crop_box(cv2.imread(gt.PHOTOS + it.name), it.box)
    x = pre(im)
    p = sess.run(None, {sess.get_inputs()[0].name: x})[0]
    boxes, _ = post(p, im.shape[:2])
    v = im.copy()
    for b in boxes:
        cv2.polylines(v, [b.astype(np.int32)], True, (0, 0, 255), max(2, im.shape[1] // 200))
    s = 300 / v.shape[1]
    v = cv2.resize(v, (300, int(v.shape[0] * s)))
    v = cv2.copyMakeBorder(v, 0, max(0, 400 - v.shape[0]), 0, 0, cv2.BORDER_CONSTANT)[:400]
    cv2.putText(v, it.name[:5], (5, 395), 0, 0.7, (255, 0, 255), 2)
    tiles.append(v)
while len(tiles) % 7: tiles.append(np.zeros_like(tiles[0]))
rows = [np.hstack(tiles[i:i + 7]) for i in range(0, len(tiles), 7)]
cv2.imwrite(paths.REVIEW_S + f"det_{model}_{side}_A.jpg", np.vstack(rows[:4]))
cv2.imwrite(paths.REVIEW_S + f"det_{model}_{side}_B.jpg", np.vstack(rows[4:]))
