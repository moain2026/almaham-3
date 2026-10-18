"""Tiny conv-only CTC recognizer for meter display lines (mobile friendly, exports cleanly to ONNX)."""
import torch.nn as nn

VOCAB = "0123456789."
BLANK = 0  # index 0 = blank; chars are 1..len(VOCAB)
IN_H, IN_W = 48, 192


def cbr(i, o, k=3, s=1, g=1):
    return nn.Sequential(nn.Conv2d(i, o, k, s, k // 2, groups=g, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True))


def dw(i, o, s=1):
    return nn.Sequential(cbr(i, i, 3, s, i), cbr(i, o, 1))


class SegReader(nn.Module):
    def __init__(self, width=1.0):
        super().__init__()
        c = [int(x * width) for x in (32, 64, 96, 128, 192)]
        self.body = nn.Sequential(
            cbr(1, c[0], 3, 2),            # 24x96
            dw(c[0], c[1]), dw(c[1], c[1], (2, 1)),   # 12x96
            dw(c[1], c[2]), dw(c[2], c[2], (2, 2)),   # 6x48
            dw(c[2], c[3]), dw(c[3], c[3]),
            dw(c[3], c[4], (2, 1)),                    # 3x48
            dw(c[4], c[4]),
        )
        self.collapse = nn.Conv2d(c[4], c[4], (3, 1), bias=False)  # 1x48
        self.ctx = nn.Sequential(
            nn.Conv1d(c[4], c[4], 5, padding=2, groups=c[4]), nn.Conv1d(c[4], c[4], 1), nn.ReLU(inplace=True),
            nn.Conv1d(c[4], c[4], 5, padding=2, groups=c[4]), nn.Conv1d(c[4], c[4], 1), nn.ReLU(inplace=True),
        )
        self.head = nn.Conv1d(c[4], len(VOCAB) + 1, 1)

    def forward(self, x):  # x: [B,1,48,192] in [0,1]
        f = self.collapse(self.body(x)).squeeze(2)  # [B,C,48]
        f = f + self.ctx(f)
        return self.head(f)  # [B,K,T] logits


def greedy_decode(logits):
    """logits [K,T] tensor -> (text, per-char prob list)."""
    p = logits.softmax(0)
    best = p.argmax(0).tolist()
    conf = p.max(0).values.tolist()
    out, probs, prev = [], [], BLANK
    for k, c in zip(best, conf):
        if k != BLANK and k != prev:
            out.append(VOCAB[k - 1]); probs.append(c)
        elif k != BLANK and k == prev and probs:
            probs[-1] = max(probs[-1], c)
        prev = k
    return "".join(out), probs
