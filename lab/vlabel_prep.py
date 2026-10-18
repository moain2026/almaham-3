"""Prepare enhanced single-photo crops for vision labelling and a batch list. Usage: python3 vlabel_prep.py <n>"""
import cv2, glob, os, sys, json
import paths
ERP = paths.DATA / "erp"
n = int(sys.argv[1])
fs = sorted(glob.glob(str(ERP / "photos" / "*.jpg")))[:n]
out = ERP / "vsingle"; out.mkdir(exist_ok=True)
done = json.load(open(ERP / "vlabels_raw.json")) if (ERP / "vlabels_raw.json").exists() else {}
todo = []
for f in fs:
    b = os.path.basename(f)
    if b in done: continue
    if not (out / b).exists():
        im = cv2.imread(f)
        if im is None: continue
        H, W = im.shape[:2]; crop = im[: int(H * 0.7)]
        s = 700 / crop.shape[1]; crop = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
        lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB); lab[..., 0] = cv2.createCLAHE(3.0, (8, 8)).apply(lab[..., 0])
        cv2.imwrite(str(out / b), cv2.cvtColor(lab, cv2.COLOR_LAB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 80])
    todo.append(str(out / b))
print("\n".join(todo))
