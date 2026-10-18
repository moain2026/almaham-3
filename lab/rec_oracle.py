"""Mode C: recognition-only on reference display crops (upper main line) to measure recognizer ceiling."""
import paths
import cv2, json, csv, re, time, statistics as st
from rapidocr import RapidOCR
M = paths.MODELS_S; S = paths.PHOTOS_S
gt = {r["filename"]: r for r in csv.DictReader(open(paths.GROUND_TRUTH))}
disp = json.load(open(paths.DISPLAY_BOXES))
RECS = {"v5_en": "en_PP-OCRv5_rec_mobile.onnx", "v5_ch": "ch_PP-OCRv5_rec_mobile.onnx",
        "v6_tiny": "PP-OCRv6_rec_tiny.onnx", "v6_small": "PP-OCRv6_rec_small.onnx"}
DETS = {"v5": "ch_PP-OCRv5_det_mobile.onnx", "v6t": "PP-OCRv6_det_tiny.onnx"}
def clean(t):
    d = re.sub(r"[^0-9]", "", t)
    return str(int(d[:6])) if len(d) >= 1 else ""
for dk, dm in DETS.items():
  for rk, rm in RECS.items():
    e = RapidOCR(params={"Global.log_level": "error", "Global.use_cls": False, "Det.model_path": M+dm, "Rec.model_path": M+rm})
    ok = 0; tms = []; fails = []
    for fn, (x1, y1, x2, y2) in sorted(disp.items()):
        im = cv2.imread(S+fn); H, W = im.shape[:2]
        c = im[int(y1*H):int(y2*H), int(x1*W):int(x2*W)]
        c = cv2.resize(c, (640, int(c.shape[0]*640/c.shape[1])))
        t = time.perf_counter(); r = e(c); tms.append((time.perf_counter()-t)*1000)
        best = None
        for tx, s, b in zip(r.txts or [], r.scores or [], r.boxes if r.boxes is not None else []):
            h = b[:,1].max()-b[:,1].min()
            if sum(ch.isdigit() for ch in tx) >= 2 and (best is None or h > best[0]): best = (h, tx, s)
        v = clean(best[1]) if best else ""
        if v == gt[fn]["reading"]: ok += 1
        else: fails.append(f"{fn[:5]}:{best[1] if best else '-'}")
    print(f"det {dk} rec {rk}: {ok}/{len(disp)} p50 {st.median(tms):.0f}ms | {' '.join(fails[:14])}")
