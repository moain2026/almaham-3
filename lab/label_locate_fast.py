"""Fast localisation for LABELLED photos that have NO meter box (365 on 2026-10-24).
text_locate.py slides hundreds of windows (16 s/photo); here we let the LOCATOR propose the line on the whole
upright photo at a few scales/crops, read each proposal with the reader, and accept the proposal whose integer
string equals the human label exactly (plus the integer_part relaxation). That is a label-verified box: the human
label is the ground truth, the model only tells us WHERE. Output = text_locate format (photo px) with "fast": true.
Usage: python3 label_locate_fast.py <models_dir> <todo.json {fn: null}> <out.json> [--limit N]
"""
import sys, os, json, cv2, numpy as np
import erp_finetune as ef
from eval_e2e import Engine, letterbox, LOC_IN, LOC_PEAK_MIN, LINE_MIN_H, PAD_X, PAD_Y, RD_W, RD_H
from det_model import decode
from pseudo_label import to_photo


def proposals(eng, im):
    """line boxes (photo px) from the locator on the whole photo and on a 3x3 grid of 60% crops."""
    H, W = im.shape[:2]; out = []
    crops = [(0, 0, W, H)]
    for fy in (0.0, 0.2, 0.4):
        for fx in (0.0, 0.2, 0.4):
            crops.append((int(fx * W), int(fy * H), int(fx * W + 0.6 * W), int(fy * H + 0.6 * H)))
    for cx1, cy1, cx2, cy2 in crops:
        c = im[cy1:cy2, cx1:cx2]
        li, s, ox, oy = letterbox(c, LOC_IN, LOC_IN)
        for l in decode(*eng.run(eng.loc, li), LOC_PEAK_MIN):
            if l[5] - l[3] < LINE_MIN_H: continue
            x1, y1, x2, y2 = [(v - (ox if i % 2 == 0 else oy)) / s for i, v in enumerate(l[2:])]
            out.append((l[1], cx1 + x1, cy1 + y1, cx1 + x2, cy1 + y2))
    return out


def main():
    models, todo_p, out_p = sys.argv[1:4]
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10 ** 9
    eng = Engine(models); labels = ef.load_labels()
    todo = json.load(open(todo_p)); done = json.load(open(out_p)) if os.path.exists(out_p) else {}
    n = acc = 0
    for fn in sorted(todo):
        if fn in done or n >= limit: continue
        text = labels.get(fn)
        p = ef.ERP / "photos" / fn
        if not text or not p.exists(): continue
        im = cv2.imread(str(p))
        if im is None: continue
        n += 1; H, W = im.shape[:2]; best = None
        want = text.lstrip("0") or "0"
        for sc, x1, y1, x2, y2 in sorted(proposals(eng, im), key=lambda t: -t[0])[:12]:
            # read a padded crop around the proposal (pass it through the normal engine so the box is re-located tightly)
            px, py = (x2 - x1) * 0.6, (y2 - y1) * 1.5
            cx1, cy1 = int(max(0, x1 - px)), int(max(0, y1 - py)); cx2, cy2 = int(min(W, x2 + px)), int(min(H, y2 + py))
            crop = im[cy1:cy2, cx1:cx2]
            if crop.size == 0 or crop.shape[0] < 16 or crop.shape[1] < 32: continue
            r, rect, ls, _, _ = eng.read(crop)
            if rect is None or r.status != "OK" or r.value != want: continue
            if len(r.digits) != len(text):   # need one box per label character for the shard builder
                continue
            if best is None or r.min_conf > best[0]:
                line, digs = to_photo(rect, sorted(r.digits, key=lambda d: d.x1), crop.shape, cx1, cy1)
                best = (r.min_conf, line, digs)
        if best:
            done[fn] = {"line": best[1], "score": round(float(best[0]), 3), "digits": best[2], "fast": True, "models": models}; acc += 1
        else:
            done[fn] = None
        if n % 20 == 0:
            json.dump(done, open(out_p, "w")); print(f"{n} seen, {acc} located", flush=True)
    json.dump(done, open(out_p, "w")); print(f"DONE seen {n} located {acc}", flush=True)


if __name__ == "__main__":
    main()
