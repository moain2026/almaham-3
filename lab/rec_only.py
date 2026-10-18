"""Mode C2: recognizer-only (use_det=False) on reference display crops: full crop, and main-line band."""
import paths
import cv2, json, csv, re, time, statistics as st
from rapidocr import RapidOCR
M = paths.MODELS_S; S = paths.PHOTOS_S
gt = {r["filename"]: r for r in csv.DictReader(open(paths.GROUND_TRUTH))}
disp = json.load(open(paths.DISPLAY_BOXES))
RECS = {"v5_en": "en_PP-OCRv5_rec_mobile.onnx", "v6_tiny": "PP-OCRv6_rec_tiny.onnx", "v6_small": "PP-OCRv6_rec_small.onnx"}
def clean(t):
    d = re.sub(r"[^0-9]", "", t.replace("O","0").replace("D","0"))
    return str(int(d[:6])) if d else ""
for rk, rm in RECS.items():
    e = RapidOCR(params={"Global.log_level": "error", "Global.use_cls": False, "Global.use_det": False, "Rec.model_path": M+rm})
    ok = 0; tms = []; fails = []
    for fn, (x1, y1, x2, y2) in sorted(disp.items()):
        im = cv2.imread(S+fn); H, W = im.shape[:2]
        c = im[int(y1*H):int(y2*H), int(x1*W):int(x2*W)]
        t = time.perf_counter(); r = e(c, use_det=False); tms.append((time.perf_counter()-t)*1000)
        tx = r.txts[0] if r.txts else ""
        if clean(tx) == gt[fn]["reading"]: ok += 1
        else: fails.append(f"{fn[:5]}:{tx}")
    print(f"rec-only {rk}: {ok}/{len(disp)} p50 {st.median(tms):.0f}ms\n   {' '.join(fails)}")
