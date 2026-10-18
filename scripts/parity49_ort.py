"""Agent B, 0.2.0 parity: eval_e2e.Engine mode A on all 49 with <dir> <onnx|ort> <out.json>. Run once with ORT 1.31 (.onnx) and once with ORT 1.23.2 (.ort), then compare."""
import sys, json, csv
sys.path.insert(0, '/home/user/flutter_app/lab')
import onnxruntime as ort
import types, importlib.util
try:
    import torch  # noqa
except ImportError:  # ORT-1.23.2 venv has no torch: load det_model.decode (pure numpy) without torch
    src = open('/home/user/flutter_app/lab/det_model.py').read()
    stride = [l for l in src.splitlines() if l.startswith('STRIDE')][0]
    dec = src[src.index('def decode'):src.index('if __name__')]
    m = types.ModuleType('det_model'); exec(stride + '\n' + dec, m.__dict__); sys.modules['det_model'] = m
from pathlib import Path
import eval_e2e as E, paths
d, ext, out = sys.argv[1], sys.argv[2], sys.argv[3]
class Eng(E.Engine):
    def __init__(self):
        so = ort.SessionOptions(); so.intra_op_num_threads = 2
        self.loc = ort.InferenceSession(f"{d}/line_locator.{ext}", so, providers=["CPUExecutionProvider"])
        self.rd = ort.InferenceSession(f"{d}/digit_reader.{ext}", so, providers=["CPUExecutionProvider"])
eng = Eng()
boxes = json.load(open(paths.METER_BOXES)); res = {}
for g in csv.DictReader(open(paths.GROUND_TRUTH, encoding="utf-8")):
    fn = g["filename"]; im = E.load_upright(fn); H, W = im.shape[:2]
    x1, y1, x2, y2 = boxes[fn]
    r = eng.read(im[int(y1*H):int(y2*H), int(x1*W):int(x2*W)])[0]
    res[fn] = {"value": r.value, "raw": r.text, "status": r.status, "confident": bool(r.confident), "truth": g["reading"]}
json.dump({"ort": ort.__version__, "ext": ext, "rows": res}, open(out, "w"), indent=0, ensure_ascii=False)
print(ort.__version__, ext, "n", len(res), "exact", sum(v["value"] == v["truth"] and v["truth"] != "" for v in res.values()))
