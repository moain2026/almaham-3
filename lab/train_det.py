"""Train DigitNet (locator or reader) on pre-generated synthetic shards. Real photos are never used here.

Usage: TORCH_THREADS=2 python3 train_det.py <reader|locator> <steps> <out.pt> <shard_prefix[,prefix2]> [resume.pt]
Shards come from gen_det_data.py (<prefix>_X.npy / <prefix>_B.npy). Images are memory-mapped.
Logs the exact command first (LESSONS), saves the checkpoint every 500 steps, and holds out the LAST 2% of every
shard as a synthetic validation set (printed as exact-reading accuracy for the reader, line IoU>0.5 recall for
the locator).
"""
import os
import sys
import time

import numpy as np
import augment
import torch
import torch.nn as nn

import assemble
from det_model import DigitNet, LOCATOR_CLASSES, READER_CLASSES, STRIDE, decode, focal_loss, reg_loss
from synth2 import CLS_LINE

torch.set_num_threads(int(os.environ.get("TORCH_THREADS", "2")))
BATCH = {"reader": 32, "locator": 24}
AUG_MODE = os.environ.get("AUG", "v1")          # v1 = legacy shift/channel-swap ; v2 = augment.py recipe (standards doc §3.2)
AUG_RNG = np.random.default_rng(int(os.environ.get("AUG_SEED", "0")))
HOLDOUT = 0.02


def gaussian_radius(h, w, min_overlap=0.7):
    a1, b1, c1 = 1, h + w, w * h * (1 - min_overlap) / (1 + min_overlap)
    r1 = (b1 + np.sqrt(b1 ** 2 - 4 * a1 * c1)) / 2
    a2, b2, c2 = 4, 2 * (h + w), (1 - min_overlap) * w * h
    r2 = (b2 + np.sqrt(b2 ** 2 - 4 * a2 * c2)) / 2
    a3, b3, c3 = 4 * min_overlap, -2 * min_overlap * (h + w), (min_overlap - 1) * w * h
    r3 = (b3 + np.sqrt(b3 ** 2 - 4 * a3 * c3)) / 2
    return max(0, int(min(r1, r2, r3)))


def draw_gaussian(hm, cx, cy, r):
    d = 2 * r + 1
    sigma = d / 6
    ys, xs = np.ogrid[-r:r + 1, -r:r + 1]
    g = np.exp(-(xs * xs + ys * ys) / (2 * sigma * sigma))
    H, W = hm.shape
    l, rr = min(cx, r), min(W - cx, r + 1)
    t, b = min(cy, r), min(H - cy, r + 1)
    if rr <= -l or b <= -t:
        return
    hm[cy - t:cy + b, cx - l:cx + rr] = np.maximum(hm[cy - t:cy + b, cx - l:cx + rr], g[r - t:r + b, r - l:r + rr])


class Shards:
    def __init__(self, prefixes, kind):
        self.X, self.B, self.train_idx, self.val_idx = [], [], [], []
        for si, p in enumerate(prefixes):
            X = np.load(p + "_X.npy", mmap_mode="r")
            B = np.load(p + "_B.npy")
            by = [[] for _ in range(len(X))]
            for row in B:
                by[int(row[0])].append(row[1:])
            self.X.append(X)
            self.B.append([np.array(b, np.float32).reshape(-1, 5) for b in by])
            n_val = max(1, int(len(X) * HOLDOUT))
            self.train_idx += [(si, i) for i in range(len(X) - n_val)]
            self.val_idx += [(si, i) for i in range(len(X) - n_val, len(X))]
        self.kind = kind
        self.H, self.W = self.X[0].shape[1:3]
        self.C = READER_CLASSES if kind == "reader" else LOCATOR_CLASSES

    def item(self, si, i):
        return np.asarray(self.X[si][i]), self.B[si][i]

    def targets(self, boxes):
        """boxes [M,5] (cls,x1,y1,x2,y2) -> heat [C,h,w], size [2,h,w], off [2,h,w], mask [1,h,w]."""
        h, w = self.H // STRIDE, self.W // STRIDE
        heat = np.zeros((self.C, h, w), np.float32)
        size = np.zeros((2, h, w), np.float32)
        off = np.zeros((2, h, w), np.float32)
        mask = np.zeros((1, h, w), np.float32)
        for c, x1, y1, x2, y2 in boxes:
            c = int(c)
            if self.kind == "reader":
                if c == CLS_LINE:
                    continue
            else:
                if c != CLS_LINE:
                    continue
                c = 0
            bw, bh = (x2 - x1) / STRIDE, (y2 - y1) / STRIDE
            if bw < 0.5 or bh < 0.5:
                continue
            cx, cy = (x1 + x2) / 2 / STRIDE, (y1 + y2) / 2 / STRIDE
            ix, iy = int(cx), int(cy)
            if not (0 <= ix < w and 0 <= iy < h):
                continue
            r = max(1, gaussian_radius(bh, bw)) if self.kind == "locator" else max(0, gaussian_radius(bh, bw))
            draw_gaussian(heat[c], ix, iy, r)
            heat[c, iy, ix] = 1.0
            size[:, iy, ix] = (x2 - x1, y2 - y1)
            off[:, iy, ix] = (cx - ix, cy - iy)
            mask[0, iy, ix] = 1.0
        return heat, size, off, mask

    def batch(self, n):
        picks = [self.train_idx[k] for k in np.random.randint(0, len(self.train_idx), n)]
        xs, hs, ss, os_, ms = [], [], [], [], []
        for si, i in picks:
            im, bx = self.item(si, i)
            if AUG_MODE == "v2":  # recipe v2 (augment.py): geometric + photometric + degradation, boxes follow
                im, bx = augment.augment(im, bx, self.kind, AUG_RNG)
                bx = bx.reshape(-1, 5)
            elif np.random.rand() < 0.5:  # legacy (v1): horizontal shift of a few pixels
                dx = np.random.randint(-6, 7)
                im = np.roll(im, dx, axis=1)
                bx = bx.copy()
                bx[:, [1, 3]] += dx
            if AUG_MODE != "v2" and np.random.rand() < 0.15:  # legacy channel swap: LCD colour invariance
                im = im[..., np.random.permutation(3)]
            h, s, o, m = self.targets(bx)
            xs.append(im)
            hs.append(h)
            ss.append(s)
            os_.append(o)
            ms.append(m)
        f = lambda a: torch.from_numpy(np.stack(a))
        return f(xs).float(), f(hs), f(ss), f(os_), f(ms)


def validate(model, data, max_n=400):
    """Synthetic hold-out: reader -> exact main reading (assemble.py) ; locator -> IoU>0.5 recall on main line."""
    model.eval()
    ok, n = 0, 0
    with torch.no_grad():
        for si, i in data.val_idx[:max_n]:
            im, bx = data.item(si, i)
            peaks, size, offs = model.forward_export(torch.from_numpy(im[None]).float())
            dets = decode(peaks[0].numpy(), size[0].numpy(), offs[0].numpy(), 0.3)
            if data.kind == "reader":
                lines = bx[bx[:, 0] == CLS_LINE]
                if len(lines) == 0:
                    continue
                truth = assemble.truth_from_boxes(bx, lines[0])
                if truth is None:
                    continue
                r = assemble.assemble(dets, data.W, data.H)
                ok += (r.text == truth)
                n += 1
            else:
                lines = bx[bx[:, 0] == CLS_LINE]
                if len(lines) == 0:
                    continue
                n += 1
                best = max(dets, key=lambda d: d[1], default=None)
                if best and assemble.iou(best[2:], lines[0][1:]) > 0.5:
                    ok += 1
    model.train()
    return ok, n


def main():
    kind, steps, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    prefixes = sys.argv[4].split(",")
    resume = sys.argv[5] if len(sys.argv) > 5 else None
    print("argv", sys.argv, "threads", torch.get_num_threads(), flush=True)
    data = Shards(prefixes, kind)
    print("train", len(data.train_idx), "val", len(data.val_idx), "input", data.H, data.W, flush=True)
    model = DigitNet(data.C)
    if resume:
        model.load_state_dict(torch.load(resume))
    opt = torch.optim.AdamW(model.parameters(), 2e-3, weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.OneCycleLR(opt, 2e-3, total_steps=steps, pct_start=0.05)
    B = BATCH[kind]
    run, t0 = None, time.time()
    for step in range(steps):
        x, heat, size, off, mask = data.batch(B)
        hm, wh, of = model(x)
        loss = focal_loss(hm, heat) + 0.1 * reg_loss(wh, size, mask) + reg_loss(of, off, mask)
        opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(model.parameters(), 10)
        opt.step()
        sch.step()
        run = loss.item() if run is None else 0.98 * run + 0.02 * loss.item()
        if step % 250 == 0 or step == steps - 1:
            torch.save(model.state_dict(), out)
            ok, n = validate(model, data, 100 if step < steps - 1 else 400)
            print(f"step {step} loss {run:.3f} val {ok}/{n} {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
