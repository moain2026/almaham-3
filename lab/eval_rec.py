"""Evaluate a SegReader checkpoint on the 46 readable test photos using reference line crops (line_boxes.json).

This measures the RECOGNIZER ONLY (ceiling given a perfect line locator). It is NOT the end-to-end number.
Usage: python3 eval_rec.py weights/rec_w075.pt [width=0.75]
Writes benchmark/results/engines/segreader_<ckpt>.json (per-image output, min char conf).
"""
import json
import statistics as st
import sys
import time
from pathlib import Path

import torch

import paths
from prep import to_input
from rec_model import SegReader, greedy_decode
from train_rec import load_real

THREADS = 2  # keep 2 of 4 cores free so the sandbox/agent stays responsive (see LESSONS.md)


def clean(text):
    integer_part = text.split(".")[0]
    return str(int(integer_part)) if integer_part.isdigit() else ""


def main(ckpt, width):
    torch.set_num_threads(THREADS)
    model = SegReader(width)
    model.load_state_dict(torch.load(ckpt))
    model.eval()
    names = sorted(json.load(open(paths.LINE_BOXES)))
    rows, ok, times = [], 0, []
    with torch.no_grad():
        for name, (crop, truth) in zip(names, load_real()):
            x = torch.from_numpy(to_input(crop))[None]
            t0 = time.perf_counter()
            text, probs = greedy_decode(model(x)[0])
            times.append((time.perf_counter() - t0) * 1000)
            value = clean(text)
            ok += value == truth
            rows.append({"file": name, "truth": truth, "raw": text, "value": value, "ok": value == truth,
                         "min_conf": round(min(probs), 3) if probs else None})
    times.sort()
    summary = {"checkpoint": Path(ckpt).name, "params": sum(p.numel() for p in model.parameters()),
               "exact": ok, "n": len(rows), "p50_ms": round(st.median(times), 2),
               "p95_ms": round(times[int(0.95 * len(times))], 2), "threads": THREADS,
               "hardware": "sandbox x86 CPU (NOT a phone)", "input": "reference line crop (oracle)"}
    paths.ensure_dirs()
    out = paths.RESULTS_ENGINES / f"segreader_{Path(ckpt).stem}.json"
    json.dump({"summary": summary, "rows": rows}, open(out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.75)
