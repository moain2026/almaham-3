"""Pre-generate synthetic detector data as memory-mappable shards (uint8 images + per-image boxes).

Usage: python3 gen_det_data.py <scene|line> <N> <out_prefix> <seed>
Writes <out_prefix>_X.npy (uint8 [N,H,W,3], loadable with mmap_mode so training never holds a shard in RAM)
and <out_prefix>_B.npy (float32 [M,6] = image_index, cls, x1, y1, x2, y2).
Runs with 2 worker processes (sandbox rule: leave 2 of 4 cores free).
"""
import random
import sys
from multiprocessing import Pool

import numpy as np

import synth2


def work(args):
    kind, seed, n = args
    random.seed(seed)
    np.random.seed(seed % (2 ** 31))
    imgs, boxes = [], []
    while len(imgs) < n:
        s = synth2.scene_sample() if kind == "scene" else synth2.line_sample()
        if s is None:
            continue
        im, bx = s
        i = len(imgs)
        imgs.append(im)
        boxes += [(i, c, x1, y1, x2, y2) for c, x1, y1, x2, y2 in bx]
    return np.stack(imgs), np.array(boxes, np.float32).reshape(-1, 6)


if __name__ == "__main__":
    kind, N, out, base = sys.argv[1], int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
    print("argv", sys.argv, flush=True)
    chunks = [(kind, base * 1000 + i, N // 8) for i in range(8)]
    with Pool(2) as p:
        res = p.map(work, chunks)
    n_total = sum(len(r[0]) for r in res)
    X = np.lib.format.open_memmap(out + "_X.npy", mode="w+", dtype=np.uint8, shape=(n_total,) + res[0][0].shape[1:])
    B, off = [], 0
    for r in res:
        X[off:off + len(r[0])] = r[0]
        b = r[1].copy()
        b[:, 0] += off
        B.append(b)
        off += len(r[0])
    X.flush()
    np.save(out + "_B.npy", np.concatenate(B))
    print(X.shape, sum(len(b) for b in B), "boxes")
