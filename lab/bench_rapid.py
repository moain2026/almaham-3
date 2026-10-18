"""Reference benchmark of PP-OCR models (via RapidOCR) on both test modes with a naive reading selector."""
import paths
import re, sys, time, json, cv2
from rapidocr import RapidOCR
import gt

M = paths.MODELS_S
det, rec, side = sys.argv[1], sys.argv[2], int(sys.argv[3])
eng = RapidOCR(params={"Det.model_path": M + det + ".onnx", "Rec.model_path": M + rec + ".onnx",
                       "Global.log_level": "error", "Global.use_cls": False, "Det.limit_side_len": side,
                       "Det.limit_type": "max"})


def pick(res):
    best = None
    if res.boxes is None:
        return ""
    for b, t, s in zip(res.boxes, res.txts, res.scores):
        m = re.match(r"^\D*?(\d{2,})", t.replace(" ", ""))
        if not m:
            continue
        h = max(abs(b[3][1] - b[0][1]), abs(b[2][1] - b[1][1]))
        if best is None or h > best[0]:
            best = (h, m.group(1))
    return (best[1].lstrip("0") or "0") if best else ""


rows = []
for it in gt.load():
    img = cv2.imread(gt.PHOTOS + it.name)
    r = {}
    for mode, im in [("rect", gt.crop_box(img, it.box)), ("full", img)]:
        t = time.perf_counter(); res = eng(im); dt = time.perf_counter() - t
        r[mode] = (pick(res), round(dt * 1000), list(res.txts or []))
    rows.append((it, r))
for mode in ["rect", "full"]:
    ok = sum(1 for it, r in rows if it.readable and r[mode][0] == it.reading)
    okc = sum(1 for it, r in rows if it.readable and not it.uncertain and r[mode][0] == it.reading)
    n = sum(it.readable for it, _ in rows); nc = sum(it.readable and not it.uncertain for it, _ in rows)
    ms = sorted(r[mode][1] for _, r in rows)
    print(f"{det}+{rec}@{side} {mode}: exact {ok}/{n}  certain {okc}/{nc}  p50 {ms[len(ms)//2]}ms")
json.dump([(it.name, it.reading, r) for it, r in rows], open(paths.RESULTS_ENGINES / f"rapid_{det}_{rec}_{side}.json", "w"), ensure_ascii=False)
