"""Pseudo-labels for the UNLABELLED ERP photos that have an agent-D meter box (778 on 2026-10-24).
Owner 2026-10-24: "you have thousands of photos — use them". Human labels are the ceiling of quality, but a
self-training round with a STRICT agreement gate is the cheapest way to grow the real-data pool today.

Gate (measured in docs/research/gate-v2-2026-10-24.md to give 0 wrong of 104 accepted on val-m4 e2e when
combined with a previous-reading window; here we have no previous reading, so we demand MORE agreement):
  * two different model pairs (candidate m4 and reference) read the meter crop and return the SAME integer string
  * TTA (gamma 0.7/1.4, scale 0.92/1.08) of the candidate pair all return the same string
  * status OK, every digit score >= 0.45, alt < 0.5 x score, min_conf >= 0.55, 3..7 digits
Output: data/erp/ft/pseudo_<tag>.json in text_locate format (line box + digit boxes in PHOTO pixels, "pseudo": true)
so build_meter_shards can consume it as if it were a located photo; plus a label CSV for the private store.
Never touches the 49/34 (hash exclusion in ef.TEST_HASHES / EXCLUDE_FILES).
Usage: python3 pseudo_label.py <models_dir_A> <models_dir_B> <tag> [--shard i/n] [--limit N]
"""
import sys, os, json, hashlib, cv2, numpy as np
import erp_finetune as ef
from eval_e2e import Engine, PAD_X, PAD_Y, RD_W, RD_H
from build_meter_shards import load_meter_boxes, multi_meter
from gate_v2_study import tta_views


def strict_ok(r):
    return (r.status == "OK" and r.value != "" and 3 <= len(r.digits) <= 7 and r.min_conf >= 0.55
            and all(d.score >= 0.45 and d.alt_score < 0.5 * d.score for d in r.digits))


def to_photo(rect, digits, crop_shape, mx1, my1):
    """map reader-canvas digit boxes back to photo pixels (inverse of eval_e2e.Engine.read crop + letterbox)."""
    H, W = crop_shape[:2]; x1, y1, x2, y2 = rect
    px, py = (x2 - x1) * PAD_X, (y2 - y1) * PAD_Y
    sx1, sy1 = int(np.clip(x1 - px, 0, W - 1)), int(np.clip(y1 - py, 0, H - 1))
    sx2, sy2 = int(np.clip(x2 + px, sx1 + 1, W)), int(np.clip(y2 + py, sy1 + 1, H))
    s = min(RD_W / (sx2 - sx1), RD_H / (sy2 - sy1)); oy = (RD_H - (sy2 - sy1) * s) / 2   # centre_x=False -> ox = 0
    out = []
    for d in digits:
        out.append([int(d.cls), d.x1 / s + sx1 + mx1, (d.y1 - oy) / s + sy1 + my1, d.x2 / s + sx1 + mx1, (d.y2 - oy) / s + sy1 + my1])
    xs1 = min(o[1] for o in out); ys1 = min(o[2] for o in out); xs2 = max(o[3] for o in out); ys2 = max(o[4] for o in out)
    return [xs1, ys1, xs2, ys2], out


def main():
    A, B, tag = sys.argv[1:4]
    shard = sys.argv[sys.argv.index("--shard") + 1] if "--shard" in sys.argv else "0/1"
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10 ** 9
    si, sn = map(int, shard.split("/"))
    ea, eb = Engine(A), Engine(B)
    labels = ef.load_labels(); multi = multi_meter()
    boxes = {k: v for k, v in load_meter_boxes().items() if isinstance(v, (list, tuple)) and len(v) == 4 and all(isinstance(t, (int, float)) for t in v)}
    photos = sorted(os.listdir(str(ef.ERP / "photos")))
    todo = [f for j, f in enumerate(photos) if f not in labels and boxes.get(f) and f not in multi and f not in ef.EXCLUDE_FILES and j % sn == si]
    out_p = f"../data/erp/ft/pseudo_{tag}.json"
    done = json.load(open(out_p)) if os.path.exists(out_p) else {}
    print(f"shard {shard}: {len(todo)} candidates, {len(done)} done", flush=True)
    n = acc = 0
    for fn in todo:
        if fn in done or n >= limit: continue
        p = ef.ERP / "photos" / fn
        if hashlib.sha256(open(p, "rb").read()).hexdigest() in ef.TEST_HASHES: continue
        im = cv2.imread(str(p))
        if im is None: continue
        H, W = im.shape[:2]; bx = boxes[fn]; mx1, my1 = int(bx[0] * W), int(bx[1] * H)
        crop = im[my1:int(bx[3] * H), mx1:int(bx[2] * W)]
        if crop.size == 0: continue
        n += 1
        ra, rect, ls, _, _ = ea.read(crop)
        if not strict_ok(ra) or rect is None: done[fn] = None; continue
        rb = eb.read(crop)[0]
        if rb.value != ra.value: done[fn] = None; continue
        if any(ea.read(v)[0].value != ra.value for v in tta_views(crop)): done[fn] = None; continue
        line, digs = to_photo(rect, sorted(ra.digits, key=lambda d: d.x1), crop.shape, mx1, my1)
        done[fn] = {"line": line, "score": round(float(ra.min_conf), 3), "digits": digs, "text": ra.value, "pseudo": True, "models": [A, B]}
        acc += 1
        if n % 25 == 0:
            json.dump(done, open(out_p, "w")); print(f"{n} seen, {acc} accepted", flush=True)
    json.dump(done, open(out_p, "w"))
    print(f"DONE {tag} shard {shard}: seen {n}, accepted {acc}", flush=True)


if __name__ == "__main__":
    main()
