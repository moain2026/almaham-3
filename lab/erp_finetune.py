"""Fine-tune the DigitNet reader on ERP photos with human text labels (weak digit boxes) — contract §4.

Usage:
  python3 erp_finetune.py build  <locator.pt> <reader.pt> <out_prefix>      # labels -> line crops + weak boxes
  python3 erp_finetune.py train  <reader_init.pt> <real_prefix> <synth_prefixes> <steps> <out.pt>

build:
  * reads every benchmark/data/erp/labels*.csv (filename,text,...); keeps digit-only texts (skips X/P).
  * skips any photo whose SHA256 is in the 49-photo test set.
  * locates the reading line with the given locator on the upright full photo (letterbox 256, like the app),
    crops with the app's padding, letterboxes to 64x448 (like the app), runs the reader.
  * weak labelling rule (deterministic, logged):
      - reader finds exactly len(text) integer digits in a regular lattice  -> boxes accepted, classes := text
      - reader finds len(text)+k digits but the lattice gives len(text) main cells -> accepted, classes := text
      - otherwise                                                           -> rejected (counted per reason)
  * split by the first 8 hex chars of the filename (stand-in for meter id): 85% train / 15% val.
  * writes <out_prefix>_{train,val}_X.npy / _B.npy in the same format as gen_det_data.py (so train_det.py's
    Shards class loads them unchanged), plus <out_prefix>_report.json (acceptance per reason, class histogram).
train:
  * same loop as train_det.py but each batch is 50% real / 50% synthetic, lr 5e-4, and the real val split is
    evaluated as exact-reading accuracy every 500 steps. The 49 test photos are never touched here.
"""
import csv
import glob
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn

import assemble
import paths
from det_model import DigitNet, READER_CLASSES, LOCATOR_CLASSES, decode, focal_loss, reg_loss
from eval_e2e import LOC_IN, RD_H, RD_W, LOC_PEAK_MIN, LINE_MIN_H, PAD_X, PAD_Y, RD_PEAK_MIN, letterbox
from synth2 import CLS_LINE
from train_det import Shards, BATCH

torch.set_num_threads(int(os.environ.get("TORCH_THREADS", "2")))
ERP = paths.DATA / "erp"
LABELS = paths.BENCH_DATA / "erp"
TEST_HASHES = {ln.split()[0] for ln in open(paths.BENCH_DATA / "photos.sha256") if ln.strip()}


def load_labels():
    rows = {}
    for f in sorted(glob.glob(str(LABELS / "labels*.csv"))):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            t = r["text"].strip()
            if t.isdigit():
                rows[r["filename"]] = t
    return rows


def run_net(m, img):
    x = torch.from_numpy(cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)[None])
    with torch.no_grad():
        p, s, o = m.forward_export(x)
    return p[0].numpy(), s[0].numpy(), o[0].numpy()


def build(loc_ckpt, rd_ckpt, out_prefix):
    loc = DigitNet(LOCATOR_CLASSES)
    loc.load_state_dict(torch.load(loc_ckpt, map_location="cpu"))
    loc.eval()
    rd = DigitNet(READER_CLASSES)
    rd.load_state_dict(torch.load(rd_ckpt, map_location="cpu"))
    rd.eval()
    labels = load_labels()
    reasons = {"ok_exact": 0, "ok_relabel": 0, "no_photo": 0, "test_photo": 0, "no_line": 0, "count_mismatch": 0, "unreadable": 0}
    X, B, keys = [], [], []
    hist = np.zeros(10, int)
    for fn, text in sorted(labels.items()):
        p = ERP / "photos" / fn
        if not p.exists():
            reasons["no_photo"] += 1
            continue
        if hashlib.sha256(open(p, "rb").read()).hexdigest() in TEST_HASHES:
            reasons["test_photo"] += 1
            continue
        im = cv2.imread(str(p))
        if im is None:
            reasons["unreadable"] += 1
            continue
        li, s, ox, oy = letterbox(im, LOC_IN, LOC_IN)
        lines = [l for l in decode(*run_net(loc, li), LOC_PEAK_MIN) if l[5] - l[3] >= LINE_MIN_H]
        if not lines:
            reasons["no_line"] += 1
            continue
        best = max(lines, key=lambda l: l[1])
        H, W = im.shape[:2]
        x1, y1, x2, y2 = [(v - (ox if i % 2 == 0 else oy)) / s for i, v in enumerate(best[2:])]
        px, py = (x2 - x1) * PAD_X, (y2 - y1) * PAD_Y
        sx1, sy1 = int(np.clip(x1 - px, 0, W - 1)), int(np.clip(y1 - py, 0, H - 1))
        sx2, sy2 = int(np.clip(x2 + px, sx1 + 1, W)), int(np.clip(y2 + py, sy1 + 1, H))
        ri, _, _, _ = letterbox(im[sy1:sy2, sx1:sx2], RD_W, RD_H, centre_x=False)
        r = assemble.assemble(decode(*run_net(rd, ri), RD_PEAK_MIN), RD_W, RD_H)
        ds = r.digits
        if len(ds) != len(text):
            reasons["count_mismatch"] += 1
            continue
        reasons["ok_exact" if r.text == text else "ok_relabel"] += 1
        i = len(X)
        X.append(ri)
        for d, ch in zip(ds, text):
            B.append((i, int(ch), d.x1, d.y1, d.x2, d.y2))
            hist[int(ch)] += 1
        lb = np.array([[d.x1, d.y1, d.x2, d.y2] for d in ds])
        B.append((i, CLS_LINE, lb[:, 0].min(), lb[:, 1].min(), lb[:, 2].max(), lb[:, 3].max()))
        keys.append(fn[:8])
    if not X:
        print("nothing accepted", reasons)
        return
    X = np.stack(X)
    B = np.array(B, np.float32)
    # split by key
    uniq = sorted(set(keys))
    rng = np.random.RandomState(0)
    rng.shuffle(uniq)
    val_keys = set(uniq[: max(1, int(0.15 * len(uniq)))])
    for name, pick in (("train", lambda k: k not in val_keys), ("val", lambda k: k in val_keys)):
        idx = [i for i, k in enumerate(keys) if pick(k)]
        remap = {old: new for new, old in enumerate(idx)}
        Xi = X[idx]
        Bi = np.array([(remap[int(b[0])], *b[1:]) for b in B if int(b[0]) in remap], np.float32).reshape(-1, 6)
        np.save(f"{out_prefix}_{name}_X.npy", Xi)
        np.save(f"{out_prefix}_{name}_B.npy", Bi)
        print(name, Xi.shape, len(Bi), "boxes")
    rep = {"reasons": reasons, "accepted": len(X), "class_hist": hist.tolist(), "n_train_keys": len(uniq) - len(val_keys), "n_val_keys": len(val_keys)}
    json.dump(rep, open(f"{out_prefix}_report.json", "w"), indent=1)
    print(json.dumps(rep))


def real_exact(model, data):
    model.eval()
    ok = n = 0
    with torch.no_grad():
        for si, i in data.val_idx + data.train_idx[:0]:
            im, bx = data.item(si, i)
            peaks, size, offs = model.forward_export(torch.from_numpy(im[None]).float())
            lines = bx[bx[:, 0] == CLS_LINE]
            truth = assemble.truth_from_boxes(bx, lines[0]) if len(lines) else None
            if truth is None:
                continue
            r = assemble.assemble(decode(peaks[0].numpy(), size[0].numpy(), offs[0].numpy(), RD_PEAK_MIN), data.W, data.H)
            ok += r.text == truth
            n += 1
    model.train()
    return ok, n


def train(init, real_prefix, synth_prefixes, steps, out):
    print("argv", sys.argv, "threads", torch.get_num_threads(), flush=True)
    real = Shards([real_prefix + "_train"], "reader")
    real.val_idx = []
    realval = Shards([real_prefix + "_val"], "reader")
    realval.val_idx = realval.train_idx + realval.val_idx
    synth = Shards(synth_prefixes.split(","), "reader")
    model = DigitNet(READER_CLASSES)
    model.load_state_dict(torch.load(init, map_location="cpu"))
    opt = torch.optim.AdamW(model.parameters(), 5e-4, weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    B = BATCH["reader"]
    run, t0 = None, time.time()
    for step in range(steps):
        xr, hr, sr, orr, mr = real.batch(B // 2)
        xs, hs, ss, os_, ms = synth.batch(B - B // 2)
        x = torch.cat([xr, xs]); heat = torch.cat([hr, hs]); size = torch.cat([sr, ss]); off = torch.cat([orr, os_]); mask = torch.cat([mr, ms])
        hm, wh, of = model(x)
        loss = focal_loss(hm, heat) + 0.1 * reg_loss(wh, size, mask) + reg_loss(of, off, mask)
        opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 10); opt.step(); sch.step()
        run = loss.item() if run is None else 0.98 * run + 0.02 * loss.item()
        if step % 500 == 0 or step == steps - 1:
            torch.save(model.state_dict(), out)
            ok, n = real_exact(model, realval)
            print(f"step {step} loss {run:.3f} real_val_exact {ok}/{n} {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "train":
        train(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), sys.argv[6])
    else:
        print(__doc__)
