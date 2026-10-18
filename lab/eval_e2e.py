"""End-to-end evaluation of the exported ONNX pair on the 49 test photos (modes A and B), mirroring MeterReader.kt.

Usage: python3 eval_e2e.py <models_dir> [tag]
Writes benchmark/results/engines/digitnet_<tag>_{A,B}.json and a per-image CSV, prints the summary table.
Metrics (per brief §3/§7): exact match on readable photos, per-digit accuracy, empty rate, wrong-confident rate,
per-stage p50/p95/max (sandbox CPU, NOT a phone), and rejection of the 3 unreadable photos.
"""
import csv
import json
import statistics as st
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

import assemble
import paths
import segverify
from det_model import decode

LOC_IN, RD_H, RD_W = 256, 64, 448
LOC_PEAK_MIN, LINE_MIN_H, PAD_X, PAD_Y, RD_PEAK_MIN = 0.25, 6.0, 0.18, 0.45, 0.30  # == MeterOcrConfig
LATTICE_PEAK_MIN = 0.08  # re-read threshold for lattice-predicted cells (MeterOcrConfig.LATTICE_PEAK_MIN)


def letterbox(img, dw, dh, centre_x=True):
    h, w = img.shape[:2]
    s = min(dw / w, dh / h)
    nw, nh = max(1, int(round(w * s))), max(1, int(round(h * s)))
    rs = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
    out = np.full((dh, dw, 3), 128, np.uint8)
    ox = (dw - nw) // 2 if centre_x else 0
    oy = (dh - nh) // 2
    out[oy:oy + nh, ox:ox + nw] = rs
    return out, s, ox, oy


class Engine:
    def __init__(self, d):
        so = ort.SessionOptions()
        so.intra_op_num_threads = 2
        self.loc = ort.InferenceSession(str(Path(d) / "line_locator.onnx"), so, providers=["CPUExecutionProvider"])
        self.rd = ort.InferenceSession(str(Path(d) / "digit_reader.onnx"), so, providers=["CPUExecutionProvider"])

    def run(self, sess, img_bgr):
        x = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB).astype(np.float32)[None]
        p, s, o = sess.run(None, {"image": x})
        return p[0], s[0], o[0]

    def read(self, crop):
        """crop: upright BGR. Returns (Reading, line_rect_or_None, line_score, stage_ms dict, reader_input)."""
        t0 = time.perf_counter()
        li, s, ox, oy = letterbox(crop, LOC_IN, LOC_IN)
        t1 = time.perf_counter()
        lines = decode(*self.run(self.loc, li), LOC_PEAK_MIN)
        t2 = time.perf_counter()
        lines = [l for l in lines if l[5] - l[3] >= LINE_MIN_H]
        best = max(lines, key=lambda l: l[1], default=None)
        H, W = crop.shape[:2]
        if best:
            x1, y1, x2, y2 = [(v - (ox if i % 2 == 0 else oy)) / s for i, v in enumerate(best[2:])]
            px, py = (x2 - x1) * PAD_X, (y2 - y1) * PAD_Y
            sx1, sy1 = int(np.clip(x1 - px, 0, W - 1)), int(np.clip(y1 - py, 0, H - 1))
            sx2, sy2 = int(np.clip(x2 + px, sx1 + 1, W)), int(np.clip(y2 + py, sy1 + 1, H))
            rect = (x1, y1, x2, y2)
        else:
            sx1, sy1, sx2, sy2, rect = 0, 0, W, H, None
        ri, _, _, _ = letterbox(crop[sy1:sy2, sx1:sx2], RD_W, RD_H, centre_x=False)
        t3 = time.perf_counter()
        peaks, size, offs = self.run(self.rd, ri)
        dets = decode(peaks, size, offs, RD_PEAK_MIN)
        t4 = time.perf_counter()
        r = assemble.assemble(dets, RD_W, RD_H)
        if r.status == "MISSING_DIGIT":
            # lattice re-read: for every cell the pitch lattice predicts, take the strongest class at that cell
            # from the raw heat-map with a much lower threshold (the digit is there, the peak was just weak).
            extra = []
            for (x1, y1, x2, y2) in assemble.missing_cells(r.digits):
                cx, cy = int(((x1 + x2) / 2) / 4), int(((y1 + y2) / 2) / 4)
                cy0, cy1 = max(0, cy - 1), min(peaks.shape[1], cy + 2)
                cx0, cx1 = max(0, cx - 1), min(peaks.shape[2], cx + 2)
                win = peaks[:10, cy0:cy1, cx0:cx1]
                if win.size and win.max() > LATTICE_PEAK_MIN:
                    c = int(np.unravel_index(win.argmax(), win.shape)[0])
                    extra.append((c, float(win.max()), x1, y1, x2, y2))
            if extra:
                r = assemble.assemble(dets + extra, RD_W, RD_H)
        segverify.verify(cv2.cvtColor(ri, cv2.COLOR_BGR2GRAY), r.digits)
        t5 = time.perf_counter()
        ms = {"loc_prep": (t1 - t0) * 1e3, "locate": (t2 - t1) * 1e3, "line_prep": (t3 - t2) * 1e3,
              "read": (t4 - t3) * 1e3, "assemble": (t5 - t4) * 1e3}
        ms["total"] = sum(ms.values())
        return r, rect, best[1] if best else 0.0, ms, ri


def load_upright(fn):
    im = cv2.imread(paths.photo(fn), cv2.IMREAD_COLOR)  # cv2 applies EXIF orientation by default
    return im


def digit_acc(value, truth):
    """Right-aligned per-digit accuracy (meter digits are positional)."""
    if not truth:
        return None
    n = max(len(value), len(truth))
    v, t = value.rjust(n, " "), truth.rjust(n, " ")
    return sum(a == b for a, b in zip(v, t)) / n


def summarize(rows):
    readable = [r for r in rows if r["truth"]]
    unreadable = [r for r in rows if not r["truth"]]
    times = sorted(r["ms"]["total"] for r in rows)
    out = {
        "n_readable": len(readable), "exact": sum(r["ok"] for r in readable),
        "exact_clear": sum(r["ok"] for r in readable if r["difficulty"] == "clear"),
        "n_clear": sum(1 for r in readable if r["difficulty"] == "clear"),
        "empty": sum(1 for r in readable if r["value"] == ""),
        "wrong": sum(1 for r in readable if r["value"] and not r["ok"]),
        "wrong_confident": sum(1 for r in readable if r["value"] and not r["ok"] and r["confident"]),
        "confident_total": sum(1 for r in readable if r["confident"]),
        "confident_correct": sum(1 for r in readable if r["confident"] and r["ok"]),
        "digit_acc": round(float(np.mean([digit_acc(r["value"], r["truth"]) for r in readable])), 4),
        "unreadable_rejected": sum(1 for r in unreadable if r["value"] == ""),
        "unreadable_n": len(unreadable),
        "p50_ms": round(st.median(times), 1), "p95_ms": round(times[int(0.95 * (len(times) - 1))], 1), "max_ms": round(times[-1], 1),
        "hardware": "sandbox x86 CPU, 2 ORT threads (NOT a phone)",
    }
    for k in ("loc_prep", "locate", "line_prep", "read", "assemble"):
        v = sorted(r["ms"][k] for r in rows)
        out[f"stage_{k}_p50_ms"] = round(st.median(v), 2)
    return out


def main(models_dir, tag):
    eng = Engine(models_dir)
    gt = list(csv.DictReader(open(paths.GROUND_TRUTH, encoding="utf-8")))
    boxes = json.load(open(paths.METER_BOXES))
    blank = np.full((80, 64, 3), 128, np.uint8)
    eng.read(blank)
    results = {}
    paths.ensure_dirs()
    review = paths.REVIEW / f"e2e_{tag}"
    review.mkdir(parents=True, exist_ok=True)
    for mode in ("A", "B"):
        rows = []
        for g in gt:
            fn = g["filename"]
            im = load_upright(fn)
            H, W = im.shape[:2]
            if mode == "A":
                x1, y1, x2, y2 = boxes[fn]
                im = im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)]
            r, rect, lscore, ms, ri = eng.read(im)
            ok = bool(g["reading"]) and r.value == g["reading"]
            rows.append({"file": fn, "mode": mode, "truth": g["reading"], "type": g["meter_type"], "difficulty": g["difficulty"],
                         "uncertain_gt": g["uncertain"], "raw": r.text, "value": r.value, "status": r.status, "ok": ok,
                         "confident": r.confident, "min_conf": round(r.min_conf, 3), "line_score": round(lscore, 3),
                         "line_found": rect is not None, "uncertain_idx": [i for i, d in enumerate(r.digits) if d.uncertain],
                         "ms": {k: round(v, 2) for k, v in ms.items()}})
            vis = ri.copy()
            for d in r.digits:
                col = (0, 165, 255) if d.uncertain else (0, 255, 0)
                cv2.rectangle(vis, (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2)), col, 1)
                cv2.putText(vis, str(d.cls), (int(d.x1), int(d.y1) - 1), 0, 0.35, col, 1)
            cv2.putText(vis, f"{r.value or '-'} / {g['reading'] or '?'}", (2, 62), 0, 0.4, (0, 0, 255) if not ok else (0, 200, 0), 1)
            cv2.imwrite(str(review / f"{mode}_{fn}"), vis)
        summ = summarize(rows)
        results[mode] = summ
        out = paths.RESULTS_ENGINES / f"digitnet_{tag}_{mode}.json"
        json.dump({"summary": summ, "models": str(models_dir), "rows": rows}, open(out, "w"), ensure_ascii=False, indent=1)
        with open(paths.RESULTS_ENGINES / f"digitnet_{tag}_{mode}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["file", "mode", "truth", "value", "raw", "status", "ok", "confident", "min_conf", "line_found", "line_score",
                        "digit_acc", "total_ms", "difficulty", "type"])
            for r in rows:
                w.writerow([r["file"], mode, r["truth"], r["value"], r["raw"], r["status"], r["ok"], r["confident"], r["min_conf"],
                            r["line_found"], r["line_score"], digit_acc(r["value"], r["truth"]), r["ms"]["total"], r["difficulty"], r["type"]])
        print(mode, json.dumps(summ, ensure_ascii=False))
    return results


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "v1")
