"""Benchmark the repo's two-stage ONNX (lcd-detector-v1 + digit-reader-v3) on rect/full modes with height-based decimal removal."""
import paths
import time, json, cv2
from yolo_onnx import YoloDetector
import gt

V = paths.ERP_VISION_S
lcd = YoloDetector(V + "lcd-detector-v1.onnx", 8)
dig = YoloDetector(V + "digit-reader-v3.onnx", 10)
MAIN_HEIGHT_RATIO = 0.8


def read(img):
    t0 = time.perf_counter()
    lcds = lcd.detect(img, 0.25, 0.5)
    t1 = time.perf_counter()
    if not lcds:
        return "", [], (t1 - t0, 0.0)
    b = lcds[0]
    bw, bh = b.x2 - b.x1, b.y2 - b.y1
    x1, y1 = max(0, int(b.x1 - .06 * bw)), max(0, int(b.y1 - .15 * bh))
    x2, y2 = min(img.shape[1], int(b.x2 + .06 * bw)), min(img.shape[0], int(b.y2 + .15 * bh))
    crop = img[y1:y2, x1:x2]
    ds = sorted(dig.detect(crop, 0.3, 0.35), key=lambda d: d.x1)
    t2 = time.perf_counter()
    if not ds:
        return "", [], (t1 - t0, t2 - t1)
    hmax = max(d.y2 - d.y1 for d in ds)
    # main digits must be one contiguous run at the left: stop at first small digit after main run
    run, started = [], False
    for d in ds:
        big = (d.y2 - d.y1) >= MAIN_HEIGHT_RATIO * hmax
        if big:
            run.append(d); started = True
        elif started:
            break
    s = "".join(str(d.cls) for d in run)
    return (s.lstrip("0") or ("0" if s else "")), [round(d.score, 2) for d in run], (t1 - t0, t2 - t1)


rows = []
for it in gt.load():
    img = cv2.imread(gt.PHOTOS + it.name)
    r = {}
    for mode, im in [("rect", gt.crop_box(img, it.box)), ("full", img)]:
        s, conf, t = read(im)
        r[mode] = (s, conf, [round(x * 1000) for x in t])
    rows.append((it, r))
for mode in ["rect", "full"]:
    n = sum(it.readable for it, _ in rows); nc = sum(it.readable and not it.uncertain for it, _ in rows)
    ok = sum(it.readable and r[mode][0] == it.reading for it, r in rows)
    okc = sum(it.readable and not it.uncertain and r[mode][0] == it.reading for it, r in rows)
    nor = sum(it.readable and r[mode][0] == "" for it, r in rows)
    print(f"baseline {mode}: exact {ok}/{n} certain {okc}/{nc} noread {nor}")
json.dump([(it.name, it.reading, r) for it, r in rows], open(paths.RESULTS_ENGINES / "erp_baseline.json", "w"))
