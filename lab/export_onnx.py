"""Export DigitNet checkpoints to ONNX (NHWC uint8-range float input, peaks NMS'd in-graph) and verify parity.

Usage: python3 export_onnx.py weights/locator.pt weights/reader.pt ../app/meterocr/src/main/assets/models
Writes line_locator.onnx + digit_reader.onnx, prints file sizes, max abs diff vs PyTorch, and ORT CPU latency.
"""
import sys
import time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
import torch

from det_model import DigitNet, ExportWrapper, LOCATOR_CLASSES, READER_CLASSES, width_of

SHAPES = {"locator": (1, 256, 256, 3), "reader": (1, 64, 448, 3)}


def export(ckpt, kind, out_dir):
    n = LOCATOR_CLASSES if kind == "locator" else READER_CLASSES
    sd = torch.load(ckpt, map_location="cpu")
    m = DigitNet(n, width=width_of(sd))
    m.load_state_dict(sd)
    m.eval()
    w = ExportWrapper(m).eval()
    x = torch.rand(*SHAPES[kind]) * 255
    out = Path(out_dir) / ("line_locator.onnx" if kind == "locator" else "digit_reader.onnx")
    torch.onnx.export(w, x, str(out), input_names=["image"], output_names=["peaks", "size", "offset"], opset_version=17,
                      dynamo=False, do_constant_folding=True)
    model = onnx.load(str(out))
    onnx.checker.check_model(model)
    try:
        from onnxsim import simplify
        simp, ok = simplify(model)
        if ok:
            onnx.save(simp, str(out))
    except ImportError:
        pass
    sess = ort.InferenceSession(str(out), providers=["CPUExecutionProvider"])
    with torch.no_grad():
        ref = [t.numpy() for t in w(x)]
    got = sess.run(None, {"image": x.numpy()})
    diff = max(float(np.abs(a - b).max()) for a, b in zip(ref, got))
    for _ in range(5):
        sess.run(None, {"image": x.numpy()})
    t0 = time.perf_counter()
    for _ in range(30):
        sess.run(None, {"image": x.numpy()})
    ms = (time.perf_counter() - t0) / 30 * 1000
    print(f"{kind}: {out} {out.stat().st_size / 1024:.0f} KB, max|torch-ort| = {diff:.2e}, ORT CPU {ms:.1f} ms (sandbox x86, {ort.get_device()})")


if __name__ == "__main__":
    Path(sys.argv[3]).mkdir(parents=True, exist_ok=True)
    export(sys.argv[1], "locator", sys.argv[3])
    export(sys.argv[2], "reader", sys.argv[3])
