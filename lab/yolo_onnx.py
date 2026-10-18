"""Lab-only helper: run an Ultralytics-exported YOLO ONNX detector (no NMS in graph)."""
from dataclasses import dataclass
import cv2
import numpy as np
import onnxruntime as ort

PAD_VALUE = 114


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float
    score: float
    cls: int


def letterbox(image_bgr: np.ndarray, size: int):
    h, w = image_bgr.shape[:2]
    scale = min(size / w, size / h)
    nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
    pad_x, pad_y = (size - nw) // 2, (size - nh) // 2
    canvas = np.full((size, size, 3), PAD_VALUE, np.uint8)
    canvas[pad_y:pad_y + nh, pad_x:pad_x + nw] = cv2.resize(image_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    chw = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    return chw[None], scale, pad_x, pad_y


def iou(a: Box, b: Box) -> float:
    ix = max(0.0, min(a.x2, b.x2) - max(a.x1, b.x1))
    iy = max(0.0, min(a.y2, b.y2) - max(a.y1, b.y1))
    inter = ix * iy
    union = (a.x2 - a.x1) * (a.y2 - a.y1) + (b.x2 - b.x1) * (b.y2 - b.y1) - inter
    return inter / max(union, 1e-9)


class YoloDetector:
    def __init__(self, path: str, num_classes: int):
        self.session = ort.InferenceSession(path, providers=["CPUExecutionProvider"])
        self.size = self.session.get_inputs()[0].shape[2]
        self.num_classes = num_classes

    def detect(self, image_bgr: np.ndarray, conf: float, iou_thr: float) -> list[Box]:
        tensor, scale, pad_x, pad_y = letterbox(image_bgr, self.size)
        out = self.session.run(None, {"images": tensor})[0][0]  # [4+nc, N]
        scores = out[4:4 + self.num_classes]
        cls = scores.argmax(0)
        best = scores.max(0)
        keep = best >= conf
        cx, cy, bw, bh = out[0][keep], out[1][keep], out[2][keep], out[3][keep]
        boxes = [
            Box((x - w / 2 - pad_x) / scale, (y - h / 2 - pad_y) / scale,
                (x + w / 2 - pad_x) / scale, (y + h / 2 - pad_y) / scale, float(s), int(c))
            for x, y, w, h, s, c in zip(cx, cy, bw, bh, best[keep], cls[keep])
        ]
        boxes.sort(key=lambda b: -b.score)
        kept: list[Box] = []
        for b in boxes:
            if all(iou(k, b) <= iou_thr for k in kept):
                kept.append(b)
        return kept
