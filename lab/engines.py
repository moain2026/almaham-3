"""Lab engines: each returns list of (text, score, box[4x2]) for a BGR image."""
import paths
import numpy as np
from rapidocr import RapidOCR

M = paths.MODELS_S

def rapid(det, rec, det_side=736):
    eng = RapidOCR(params={
        "Global.log_level": "error", "Global.use_cls": False,
        "Det.model_path": M + det, "Rec.model_path": M + rec,
        "Det.limit_side_len": det_side,
        "EngineConfig.onnxruntime.intra_op_num_threads": 4,
    })
    def run(img):
        r = eng(img)
        if r.txts is None:
            return []
        return [(t, float(s), np.array(b)) for t, s, b in zip(r.txts, r.scores, r.boxes)]
    return run

ENGINES = {
    "ppocrv5_mobile": lambda: rapid("ch_PP-OCRv5_det_mobile.onnx", "en_PP-OCRv5_rec_mobile.onnx"),
    "ppocrv6_tiny": lambda: rapid("PP-OCRv6_det_tiny.onnx", "PP-OCRv6_rec_tiny.onnx"),
    "ppocrv6_small": lambda: rapid("PP-OCRv6_det_small.onnx", "PP-OCRv6_rec_small.onnx"),
}
