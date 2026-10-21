"""DigitNet: a tiny CenterNet-style detector for seven-segment digits / reading lines (exports to ONNX).

Design goals: < 1M parameters, pure conv ops (ORT Mobile / NNAPI / XNNPACK friendly), input taken directly as an
RGB uint8-like float tensor in NHWC [1,H,W,3] (what Android gives us) with normalisation INSIDE the graph, and
peak suppression (3x3 max-pool NMS) INSIDE the graph so the Kotlin side only thresholds and reads boxes.

Outputs (stride 4):  peaks [1,C,H/4,W/4]  (sigmoid heat-map, zero everywhere except local maxima)
                     size  [1,2,H/4,W/4]  (box w,h in input pixels)
                     offs  [1,2,H/4,W/4]  (sub-cell centre offset, cells)
Two weight sets share this file: the LINE locator (C=1) and the DIGIT reader (C=11: '0'..'9' + dot).
"""
import torch
import torch.nn as nn
import torch.nn.functional as F

STRIDE = 4
READER_CLASSES = 11   # 0-9 + decimal dot
LOCATOR_CLASSES = 1   # main reading line


def cbr(i, o, k=3, s=1, g=1):
    return nn.Sequential(nn.Conv2d(i, o, k, s, k // 2, groups=g, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True))


class DW(nn.Module):
    """Depthwise-separable block with optional residual."""

    def __init__(self, i, o, s=1):
        super().__init__()
        self.b = nn.Sequential(cbr(i, i, 3, s, i), cbr(i, o, 1))
        self.res = (s == 1 and i == o)

    def forward(self, x):
        y = self.b(x)
        return x + y if self.res else y


class DigitNet(nn.Module):
    def __init__(self, n_classes, width=1.0):
        super().__init__()
        c1, c2, c3, c4, c5 = [int(round(c * width)) for c in (16, 32, 64, 96, 128)]
        self.n_classes = n_classes
        self.s2 = nn.Sequential(cbr(3, c1, 3, 2), DW(c1, c1))                       # /2
        self.s4 = nn.Sequential(DW(c1, c2, 2), DW(c2, c2))                          # /4
        self.s8 = nn.Sequential(DW(c2, c3, 2), DW(c3, c3), DW(c3, c3))              # /8
        self.s16 = nn.Sequential(DW(c3, c4, 2), DW(c4, c4), DW(c4, c4))             # /16
        self.s32 = nn.Sequential(DW(c4, c5, 2), DW(c5, c5), DW(c5, c5))             # /32
        self.l32 = cbr(c5, c4, 1)
        self.l16 = cbr(c4, c3, 1)
        self.l8 = cbr(c3, c2, 1)
        self.f16 = DW(c4, c4)
        self.f8 = DW(c3, c3)
        self.f4 = DW(c2, c2)
        self.head_in = nn.Sequential(DW(c2, c3), DW(c3, c3))
        self.hm = nn.Sequential(cbr(c3, c3), nn.Conv2d(c3, n_classes, 1))
        self.wh = nn.Sequential(cbr(c3, c2), nn.Conv2d(c2, 2, 1))
        self.off = nn.Sequential(cbr(c3, c2), nn.Conv2d(c2, 2, 1))
        self.hm[-1].bias.data.fill_(-2.19)  # focal-loss prior (p=0.1)

    def normalise(self, x):
        """x: [B,H,W,3] float in 0..255 (NHWC, as produced by Android) -> NCHW standardised per image."""
        x = x.permute(0, 3, 1, 2) / 255.0
        mean = x.mean(dim=(1, 2, 3), keepdim=True)
        std = x.std(dim=(1, 2, 3), keepdim=True).clamp_min(0.02)
        return (x - mean) / std

    def features(self, x):
        x2 = self.s2(x)
        x4 = self.s4(x2)
        x8 = self.s8(x4)
        x16 = self.s16(x8)
        x32 = self.s32(x16)
        p16 = self.f16(x16 + F.interpolate(self.l32(x32), size=x16.shape[2:], mode="nearest"))
        p8 = self.f8(x8 + F.interpolate(self.l16(p16), size=x8.shape[2:], mode="nearest"))
        p4 = self.f4(x4 + F.interpolate(self.l8(p8), size=x4.shape[2:], mode="nearest"))
        return self.head_in(p4)

    def forward(self, x):
        f = self.features(self.normalise(x))
        return self.hm(f), self.wh(f), self.off(f)

    def forward_export(self, x):
        hm, wh, off = self.forward(x)
        heat = torch.sigmoid(hm)
        keep = (F.max_pool2d(heat, 3, 1, 1) == heat).float()
        return heat * keep, F.relu(wh), off


class ExportWrapper(nn.Module):
    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, x):
        return self.m.forward_export(x)


def focal_loss(pred_logits, gt, ignore=None):
    """CenterNet penalty-reduced focal loss. pred_logits/gt: [B,C,H,W], gt in [0,1] with 1 at centres.
    ignore: optional [B,1,H,W] in {0,1}; cells with 1 contribute NO negative loss (unlabelled region of a
    weak-label sample, e.g. the fraction cells to the right of the integer reading — see
    docs/research/crystal-root-cause-2026-10-21.md, targets-conflict)."""
    p = torch.sigmoid(pred_logits).clamp(1e-4, 1 - 1e-4)
    pos = gt.eq(1).float()
    neg = 1 - pos
    if ignore is not None:
        neg = neg * (1 - ignore)
    neg_w = torch.pow(1 - gt, 4)
    pos_loss = torch.log(p) * torch.pow(1 - p, 2) * pos
    neg_loss = torch.log(1 - p) * torch.pow(p, 2) * neg_w * neg
    npos = pos.sum().clamp_min(1)
    return -(pos_loss.sum() + neg_loss.sum()) / npos


def reg_loss(pred, target, mask):
    """L1 on [B,2,H,W] where mask [B,1,H,W] marks object centres."""
    m = mask.expand_as(pred)
    return (torch.abs(pred - target) * m).sum() / m.sum().clamp_min(1)


def decode(peaks, size, offs, thr):
    """numpy decode of exported outputs for ONE image -> list of (cls, score, x1, y1, x2, y2) in input pixels."""
    import numpy as np
    C, H, W = peaks.shape
    cs, ys, xs = np.nonzero(peaks > thr)
    out = []
    for c, y, x in zip(cs, ys, xs):
        s = float(peaks[c, y, x])
        w, h = float(size[0, y, x]), float(size[1, y, x])
        cx = (x + float(offs[0, y, x])) * STRIDE
        cy = (y + float(offs[1, y, x])) * STRIDE
        out.append((int(c), s, cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))
    return out


if __name__ == "__main__":
    for n in (LOCATOR_CLASSES, READER_CLASSES):
        m = DigitNet(n)
        print(n, "classes, params", sum(p.numel() for p in m.parameters()))
    x = torch.rand(1, 64, 448, 3) * 255
    hm, wh, off = DigitNet(READER_CLASSES)(x)
    print(hm.shape, wh.shape, off.shape)
