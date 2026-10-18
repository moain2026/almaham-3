"""LiteRT (TFLite via onnx2tf) and minimal-ORT (.ort) parity vs ONNX Runtime 1.31 on 10 real photos.

Agent B, docs/apk-size-report.md. Report-only: does NOT change MeterReader.kt.
Stages (TF and torch live in different Pythons):
  python3 lab/litert_parity.py dump <out.npz>                          # ORT 1.31 + .onnx: real inputs/outputs, 10 photos, mode A
  <tfenv>/bin/python lab/litert_parity.py tfl <in.npz> <tfl_dir> <out.npz>   # LiteRT float32 outputs on the same inputs
  python3 lab/litert_parity.py ort <in.npz> <ort_dir> <out.npz>         # ORT 1.31 + .ort format models on the same inputs
  python3 lab/litert_parity.py compare <ref.npz> <other.npz> <out.json> # max|diff| per output + reading via decode/assemble
Photos: first 10 rows of benchmark/data/ground_truth.csv, cropped with meter_boxes.json (mode A) exactly as eval_e2e.py.
"""
import json
import sys

import numpy as np

N = 10
KEYS = ("peaks", "size", "offset")
MODELS = (("loc", "line_locator"), ("rd", "digit_reader"))


def dump(out):
    import csv

    import cv2
    import eval_e2e as E
    import paths
    eng = E.Engine("../app/meterocr/src/main/assets/models")
    rec = {}
    orig = eng.run

    def run(sess, img):
        name = "loc" if sess is eng.loc else "rd"
        r = orig(sess, img)
        if len(rec.get(name + "_in", [])) < len(rec.get("loc_in", [])) or name == "loc":  # first call per photo only
            rec.setdefault(name + "_in", []).append(cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32))
            for k, v in zip(KEYS, r):
                rec.setdefault(f"{name}_{k}", []).append(v)
        return r
    eng.run = run
    gt = list(csv.DictReader(open(paths.GROUND_TRUTH, encoding="utf-8")))[:N]
    boxes = json.load(open(paths.METER_BOXES))
    files, vals = [], []
    for g in gt:
        im = E.load_upright(g["filename"])
        H, W = im.shape[:2]
        x1, y1, x2, y2 = boxes[g["filename"]]
        r = eng.read(im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)])[0]
        files.append(g["filename"])
        vals.append(r.value)
    np.savez_compressed(out, files=np.array(files), values=np.array(vals), **{k: np.stack(v) for k, v in rec.items()})
    print("dumped", len(files), {k: np.stack(v).shape for k, v in rec.items()})


def tfl(inp, d, out):
    from ai_edge_litert.interpreter import Interpreter
    z = np.load(inp)
    res = {}
    for tag, model in MODELS:
        it = Interpreter(f"{d}/{model}/{model}_float32.tflite", num_threads=2)
        it.allocate_tensors()
        i0 = it.get_input_details()[0]["index"]
        outs = sorted(it.get_output_details(), key=lambda o: o["name"])  # Identity, _1, _2 == peaks, size, offset
        for x in z[f"{tag}_in"]:
            it.set_tensor(i0, x[None])
            it.invoke()
            for k, o in zip(KEYS, outs):
                res.setdefault(f"{tag}_{k}", []).append(np.transpose(it.get_tensor(o["index"])[0], (2, 0, 1)))  # NHWC->CHW
    np.savez_compressed(out, **{k: np.stack(v) for k, v in res.items()})
    print("tflite done", {k: np.stack(v).shape for k, v in res.items()})


def ort_fmt(inp, d, out):
    import onnxruntime as ort
    z = np.load(inp)
    res = {}
    for tag, model in MODELS:
        s = ort.InferenceSession(f"{d}/{model}.ort", providers=["CPUExecutionProvider"])
        for x in z[f"{tag}_in"]:
            for k, v in zip(KEYS, s.run(None, {"image": x[None]})):
                res.setdefault(f"{tag}_{k}", []).append(v[0])
    np.savez_compressed(out, **{k: np.stack(v) for k, v in res.items()})
    print(".ort done")


def compare(a, b, out):
    import assemble
    import eval_e2e as E
    from det_model import decode
    za, zb = np.load(a), np.load(b)
    rep = {"n_images": int(len(za["files"])), "max_abs_diff": {}}
    for k in zb.files:
        rep["max_abs_diff"][k] = float(np.abs(za[k] - zb[k]).max())
    same, rows = 0, []
    for i in range(len(za["files"])):
        ra = assemble.assemble(decode(za["rd_peaks"][i], za["rd_size"][i], za["rd_offset"][i], E.RD_PEAK_MIN), E.RD_W, E.RD_H)
        rb = assemble.assemble(decode(zb["rd_peaks"][i], zb["rd_size"][i], zb["rd_offset"][i], E.RD_PEAK_MIN), E.RD_W, E.RD_H)
        same += ra.value == rb.value
        rows.append({"file": str(za["files"][i]), "ref": ra.value, "other": rb.value})
    rep["same_reading_from_reader_heatmaps"] = same
    rep["rows"] = rows
    json.dump(rep, open(out, "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in rep.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    {"dump": dump, "tfl": tfl, "ort": ort_fmt, "compare": compare}[sys.argv[1]](*sys.argv[2:])
