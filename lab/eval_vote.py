"""Measure neural (DigitNet ONNX) vs forensic vs vote on the 46 readable photos, mode A (meter rectangle) and
on the oracle line crop L. Usage: python3 eval_vote.py <models_dir> [tag]
Writes benchmark/results/engines/vote_<tag>.json and prints the comparison table.
"""
import csv
import json
import sys

import cv2

import forensic_reader
import paths
import vote
from eval_e2e import Engine, PAD_X, PAD_Y


def main(models_dir, tag):
    eng = Engine(models_dir)
    gt = {r["filename"]: r for r in csv.DictReader(open(paths.GROUND_TRUTH, encoding="utf-8"))}
    boxes = json.load(open(paths.METER_BOXES))
    lines = json.load(open(paths.LINE_BOXES))
    out = {"A": [], "L": []}
    for fn, g in sorted(gt.items()):
        truth = g["reading"]
        if not truth:
            continue
        im = cv2.imread(paths.photo(fn))
        H, W = im.shape[:2]
        x1, y1, x2, y2 = boxes[fn]
        crop_a = im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)]
        # mode A: neural pipeline locates the line; forensic reads the same located line crop
        r, rect, _, _, _ = eng.read(crop_a)
        if rect:
            lx1, ly1, lx2, ly2 = rect
            px, py = (lx2 - lx1) * PAD_X, (ly2 - ly1) * PAD_Y
            h, w = crop_a.shape[:2]
            line_a = crop_a[int(max(0, ly1 - py)):int(min(h, ly2 + py)), int(max(0, lx1 - px)):int(min(w, lx2 + px))]
        else:
            line_a = crop_a
        f = forensic_reader.read_line(line_a) if line_a.size else {"text": "", "digits": []}
        out["A"].append((fn, truth, r, f, vote.vote(r, f)))
        # mode L: oracle line crop for both (skip photos readable in GT v3 but without an oracle line box, e.g. 23072)
        if fn not in lines:
            continue
        lx1, ly1, lx2, ly2 = lines[fn]
        lw, lh = (lx2 - lx1) * W, (ly2 - ly1) * H
        line_l = im[int(max(0, ly1 * H - PAD_Y * lh)):int(min(H, ly2 * H + PAD_Y * lh)), int(max(0, lx1 * W - PAD_X * lw)):int(min(W, lx2 * W + PAD_X * lw))]
        rl, _, _, _, _ = eng.read_line_only(line_l) if hasattr(eng, "read_line_only") else eng.read(line_l)
        fl = forensic_reader.read_line(line_l)
        out["L"].append((fn, truth, rl, fl, vote.vote(rl, fl)))
    res = {}
    for mode, rows in out.items():
        for name, pick in (("neural", lambda r, f, v: (r.value, r.confident)), ("forensic", lambda r, f, v: (fval(f), fconf(f))),
                           ("vote", lambda r, f, v: (v["value"], v["confident"]))):
            ex = wc = emp = 0
            for fn, truth, r, f, v in rows:
                val, conf = pick(r, f, v)
                ex += val == truth
                emp += val == ""
                wc += val != "" and val != truth and conf
            res[f"{mode}_{name}"] = {"exact": ex, "empty": emp, "wrong_confident": wc, "n": len(rows)}
            print(f"{mode:1s} {name:9s} exact {ex:2d}/{len(rows)}  empty {emp:2d}  wrong&confident {wc}")
    detail = {m: [{"file": fn, "truth": t, "neural": r.value, "forensic": fval(f), "vote": v["value"], "vote_conf": v["confident"]} for fn, t, r, f, v in rows] for m, rows in out.items()}
    paths.ensure_dirs()
    json.dump({"summary": res, "models": str(models_dir), "rows": detail}, open(paths.RESULTS_ENGINES / f"vote_{tag}.json", "w"), ensure_ascii=False, indent=1)


def fval(f):
    t = f.get("text", "")
    return str(int(t)) if t.isdigit() else ""


def fconf(f):
    ds = f.get("digits", [])
    return bool(ds) and all(d["conf"] >= vote.HIGH for d in ds)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "v1")
