"""Experiment: can the app find the screen by itself when the user photographs the WHOLE meter (no careful
rectangle)? Simplest possible idea, no training: run the existing locator twice (coarse → fine).

  pass 1: whole photo → locator → best line box (coarse, low resolution: the line is tiny in 256x256)
  pass 2: expand that box by a generous margin (simulating the rectangle a user would have drawn) → crop →
          the normal Engine.read (locator again at full resolution + reader)

Compared honestly against mode A (user rectangle, the current app) and mode B (whole photo, single pass) on
the 49 evaluation photos. Nothing here is trained or tuned on the 49: margins are fixed a priori from the
mode-A rectangle statistics (meter_boxes.json is ~3-4x the line box in each direction).

Usage: python3 exp_coarse2fine.py <models_dir> [tag]
"""
import csv, json, sys, time
import numpy as np
import paths
import eval_e2e as e2e

MARGIN_X, MARGIN_Y = 1.5, 3.0   # expand the coarse line box by this fraction of its size on each side
MIN_W_FRAC = 0.35               # never crop narrower than this fraction of the photo (coarse box may be too tight)


def coarse_box(eng, im):
    li, s, ox, oy = e2e.letterbox(im, e2e.LOC_IN, e2e.LOC_IN)
    lines = e2e.decode(*eng.run(eng.loc, li), e2e.LOC_PEAK_MIN)
    lines = [l for l in lines if l[5] - l[3] >= e2e.LINE_MIN_H]
    best = max(lines, key=lambda l: l[1], default=None)
    if best is None:
        return None, 0.0
    x1, y1, x2, y2 = [(v - (ox if i % 2 == 0 else oy)) / s for i, v in enumerate(best[2:])]
    return (x1, y1, x2, y2), float(best[1])


def refine_crop(im, box):
    H, W = im.shape[:2]
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    cw = max(w * (1 + 2 * MARGIN_X), W * MIN_W_FRAC)
    ch = h * (1 + 2 * MARGIN_Y)
    sx1, sx2 = int(np.clip(cx - cw / 2, 0, W - 1)), int(np.clip(cx + cw / 2, 1, W))
    sy1, sy2 = int(np.clip(cy - ch / 2, 0, H - 1)), int(np.clip(cy + ch / 2, 1, H))
    return im[sy1:sy2, sx1:sx2], (sx1, sy1, sx2, sy2)


def main():
    models = sys.argv[1]; tag = sys.argv[2] if len(sys.argv) > 2 else "c2f"
    eng = e2e.Engine(models)
    gt = list(csv.DictReader(open(paths.GROUND_TRUTH, encoding="utf-8")))
    boxes = json.load(open(paths.METER_BOXES))
    res = {"A": 0, "B": 0, "C2F": 0}; wc = {"A": 0, "B": 0, "C2F": 0}; rows = []
    for g in gt:
        fn = g["filename"]; im = e2e.load_upright(fn); H, W = im.shape[:2]
        truth = g["reading"]
        if not truth:
            continue
        out = {"file": fn, "truth": truth, "type": g["meter_type"]}
        # A: user rectangle
        x1, y1, x2, y2 = boxes[fn]
        rA = eng.read(im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)])[0]
        # B: whole photo single pass
        rB = eng.read(im)[0]
        # C2F: whole photo, coarse box → generous crop → normal read
        t0 = time.perf_counter()
        cb, cs = coarse_box(eng, im)
        if cb is None:
            rC = rB; crop_rect = None
        else:
            crop, crop_rect = refine_crop(im, cb)
            rC = eng.read(crop)[0]
        ms = (time.perf_counter() - t0) * 1e3
        for k, r in (("A", rA), ("B", rB), ("C2F", rC)):
            ok = r.value == truth
            res[k] += ok; wc[k] += (not ok) and r.status == "OK" and getattr(r, "confident", False)
            out[k] = r.value; out[k + "_ok"] = ok
        out["coarse_score"] = round(cs, 3); out["crop_rect"] = crop_rect; out["c2f_ms"] = round(ms, 1)
        rows.append(out)
        print(f"{fn} truth={truth:>8} A={str(rA.value):>8} B={str(rB.value):>8} C2F={str(rC.value):>8} coarse={cs:.2f} {g['meter_type']}")
    n = len(rows)
    summ = {"models": models, "n_readable": n, "exact_A": res["A"], "exact_B": res["B"], "exact_C2F": res["C2F"],
            "wrong_confident": wc, "MARGIN_X": MARGIN_X, "MARGIN_Y": MARGIN_Y, "MIN_W_FRAC": MIN_W_FRAC,
            "c2f_p50_ms": round(float(np.median([r["c2f_ms"] for r in rows])), 1),
            "note": "A=user rectangle (current app); B=whole photo single pass; C2F=whole photo, locator coarse->fine. 49 photos eval-only."}
    print("\n" + json.dumps(summ, ensure_ascii=False))
    paths.ensure_dirs()
    json.dump({"summary": summ, "rows": rows}, open(paths.RESULTS_ENGINES / f"exp_coarse2fine_{tag}.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
