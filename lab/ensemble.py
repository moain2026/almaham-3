"""Heat-map averaging ensemble (consult #2, all 4 models: 'do not pick a seed - ensemble').
Averages sigmoid heat, wh and offset of N DigitNet checkpoints BEFORE the 3x3 max-pool NMS, then applies the same
NMS as det_model.forward_export, so the output contract (peaks, size, offset) is identical to one ONNX session and
Engine.read() works unchanged.  Kotlin mirror = run N ORT sessions exported WITHOUT the max-pool (or export raw heat)
and average; parity test must use the same N checkpoints.
Usage as an Engine drop-in:
    eng = Engine(models_dir_for_locator)        # locator from ONNX as usual
    eng.rd = EnsembleSession(["weights/reader_m4_s0.pt", "weights/reader_m4_s1.pt", "weights/reader_m4_s2.pt"], "reader")
    eng.loc = EnsembleSession([...locator ckpts...], "locator")   # optional
Standalone: python3 ensemble.py <kind> <ckpt1,ckpt2,...> <out_dir_with_other_onnx> <tag>  -> runs eval_ckpt-like A/B via eval_e2e
"""
import sys, numpy as np, torch, torch.nn.functional as F
from det_model import DigitNet, READER_CLASSES, LOCATOR_CLASSES, width_of


class EnsembleSession:
    def __init__(self, ckpts, kind):
        n = READER_CLASSES if kind == "reader" else LOCATOR_CLASSES
        self.models = []
        for c in ckpts:
            sd = torch.load(c, map_location="cpu"); m = DigitNet(n, width=width_of(sd)); m.load_state_dict(sd); m.eval(); self.models.append(m)
        torch.set_num_threads(max(1, torch.get_num_threads()))

    def run(self, _names, feed):
        x = torch.from_numpy(np.ascontiguousarray(feed["image"]))  # NHWC float RGB 0..255 (DigitNet.normalise permutes)
        with torch.no_grad():
            heats, whs, offs = [], [], []
            for m in self.models:
                hm, wh, off = m(x); heats.append(torch.sigmoid(hm)); whs.append(F.relu(wh)); offs.append(off)
            heat = torch.stack(heats).mean(0); wh = torch.stack(whs).mean(0); off = torch.stack(offs).mean(0)
            keep = (F.max_pool2d(heat, 3, 1, 1) == heat).float()
            return [(heat * keep).numpy(), wh.numpy(), off.numpy()]


if __name__ == "__main__":
    # minimal check: compare the ensemble of ONE checkpoint with its ONNX export on a random input
    import onnxruntime as ort, sys
    from pathlib import Path
    kind, ck, onnx_path = sys.argv[1], sys.argv[2], sys.argv[3]
    es = EnsembleSession([ck], kind)
    so = ort.SessionOptions(); so.intra_op_num_threads = 1
    sess = ort.InferenceSession(onnx_path, so, providers=["CPUExecutionProvider"])
    shape = (1, 64, 448, 3) if kind == "reader" else (1, 256, 256, 3)
    x = (np.random.RandomState(0).rand(*shape) * 255).astype(np.float32)
    a = es.run(None, {"image": x}); b = sess.run(None, {"image": x})
    print("max|ensemble(1) - onnx|:", [float(np.abs(p - q).max()) for p, q in zip(a, b)])
