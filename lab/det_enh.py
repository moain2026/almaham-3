"""Check DB detection recall on enhanced (flattened+CLAHE) rect crops for faint LCDs."""
import paths
import sys, cv2, numpy as np, onnxruntime as ort
from rapidocr.ch_ppocr_det.utils import DBPostProcess, DetPreProcess
import gt
model, side = sys.argv[1], int(sys.argv[2]); names = sys.argv[3].split(",")
sess = ort.InferenceSession(paths.MODELS_S + f"{model}.onnx", providers=["CPUExecutionProvider"])
pre = DetPreProcess(side, "max", [0.5] * 3, [0.5] * 3)
post = DBPostProcess(thresh=0.3, box_thresh=0.5, max_candidates=1000, unclip_ratio=1.6, use_dilation=True, score_mode="fast")
def enh(im):
    g = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY).astype(np.float32)
    bg = cv2.GaussianBlur(g, (0, 0), max(8, im.shape[1] / 30))
    f = cv2.normalize(g / (bg + 1), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    f = cv2.createCLAHE(3.0, (8, 8)).apply(f)
    return cv2.cvtColor(f, cv2.COLOR_GRAY2BGR)
tiles = []
items = {i.name[:5]: i for i in gt.load()}
for n in names:
    im = gt.crop_box(cv2.imread(gt.PHOTOS + n + ".jpg"), items[n].box)
    e = enh(im)
    p = sess.run(None, {"x": pre(e)})[0]
    boxes, _ = post(p, e.shape[:2])
    for b in boxes: cv2.polylines(e, [b.astype(np.int32)], True, (0, 0, 255), 4)
    s = 300 / e.shape[1]; e = cv2.resize(e, (300, int(e.shape[0] * s)))
    e = cv2.copyMakeBorder(e, 0, max(0, 400 - e.shape[0]), 0, 0, cv2.BORDER_CONSTANT)[:400]
    tiles.append(e)
cv2.imwrite(paths.REVIEW_S + "detenh.jpg", np.hstack(tiles))
