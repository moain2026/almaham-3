"""Fine-tune the DigitNet reader on ERP photos with human text labels (weak digit boxes) — contract §4.

Usage:
  python3 erp_finetune.py build  <locator.pt> <reader.pt> <out_prefix>      # labels -> line crops + weak boxes
  python3 erp_finetune.py train  <init.pt> <real_prefix> <synth_prefixes> <steps> <out.pt> [reader|locator]

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
from det_model import DigitNet, READER_CLASSES, LOCATOR_CLASSES, decode, focal_loss, reg_loss, width_of
from eval_e2e import LOC_IN, RD_H, RD_W, LOC_PEAK_MIN, LINE_MIN_H, PAD_X, PAD_Y, RD_PEAK_MIN, letterbox
from synth2 import CLS_LINE

LATTICE_MAX_RATIO = 1.5  # max/min centre pitch allowed in an accepted weak label
from train_det import Shards, BATCH, validate

torch.set_num_threads(int(os.environ.get("TORCH_THREADS", "2")))
ERP = paths.DATA / "erp"
LABELS = paths.BENCH_DATA / "erp"
TEST_HASHES = {ln.split()[0] for ln in open(paths.BENCH_DATA / "photos.sha256") if ln.strip()}
# Frozen human test set on ERP photos (agent D, owner-verified) + photos that may be the same meter as a test photo.
# Both are excluded from every training shard (owner instruction 2026-10-21; docs/handoff/agentD-to-agentS-2026-10-21-owner-verified.md).
_ts = paths.BENCH_DATA / "erp" / "testset_human.sha256"
TEST_HASHES |= {ln.split()[0] for ln in open(_ts) if ln.strip()} if _ts.exists() else set()
_sib = paths.BENCH_DATA / "erp" / "testset_human_siblings.csv"
EXCLUDE_FILES = ({r["sibling_filename"] for r in csv.DictReader(open(_sib, encoding="utf-8"))} | {r["test_filename"] for r in csv.DictReader(open(_sib, encoding="utf-8"))}) if _sib.exists() else set()
_tsc = paths.BENCH_DATA / "erp" / "testset_human.csv"
EXCLUDE_FILES |= {r["filename"] for r in csv.DictReader(open(_tsc, encoding="utf-8"))} if _tsc.exists() else set()


HUMAN_LABELLERS = ("agentD",)  # 5-read consensus incl. a visual re-read (docs/prompts/AGENT-D-DATA-LABELLING.md)


def load_labels():
    """filename -> digit text. Machine labels (labels_slice_*, agentA_vision) first; human-verified labellers
    (labels_agentD.csv) are applied LAST and win: their digits override, and their X removes the photo entirely
    (a human said "unsure" -> never train on the machine guess for that photo)."""
    files = sorted(glob.glob(str(LABELS / "labels*.csv")))
    files.sort(key=lambda f: any(h in f for h in HUMAN_LABELLERS))  # human files last
    rows = {}
    for f in files:
        human = any(h in f for h in HUMAN_LABELLERS)
        for r in csv.DictReader(open(f, encoding="utf-8")):
            t = r["text"].strip()
            if t.isdigit():
                rows[r["filename"]] = t
            elif human:
                rows.pop(r["filename"], None)
    return rows


def run_net(m, img):
    x = torch.from_numpy(cv2.cvtColor(img, cv2.COLOR_BGR2RGB).astype(np.float32)[None])
    with torch.no_grad():
        p, s, o = m.forward_export(x)
    return p[0].numpy(), s[0].numpy(), o[0].numpy()


def build(loc_ckpt, rd_ckpt, out_prefix):
    loc = DigitNet(LOCATOR_CLASSES)  # width inferred below if needed
    loc.load_state_dict(torch.load(loc_ckpt, map_location="cpu"))
    loc.eval()
    rd = DigitNet(READER_CLASSES)
    rd.load_state_dict(torch.load(rd_ckpt, map_location="cpu"))
    rd.eval()
    labels = load_labels()
    types = {}
    for f in glob.glob(str(LABELS / "labels*.csv")):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            if r.get("meter_type"):
                types[r["filename"]] = r["meter_type"]
    by_type = {}
    reasons = {"ok_exact": 0, "ok_relabel": 0, "ok_lattice": 0, "ok_align": 0, "no_photo": 0, "test_photo": 0, "no_line": 0, "count_mismatch": 0, "irregular": 0, "unreadable": 0}
    X, B, keys = [], [], []
    LX, LB = [], []  # locator shard: whole-photo 256 letterbox + tight LINE box
    hist = np.zeros(10, int)
    for fn, text in sorted(labels.items()):
        p = ERP / "photos" / fn
        if not p.exists():
            reasons["no_photo"] += 1
            continue
        if fn in EXCLUDE_FILES or hashlib.sha256(open(p, "rb").read()).hexdigest() in TEST_HASHES:
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
        if len(ds) != len(text) and len(ds) >= 3:
            # lattice rescue: the detections span exactly len(text) cells of a regular pitch -> re-split into cells
            cxs = np.sort(np.array([(d.x1 + d.x2) / 2 for d in ds]))
            gaps = np.diff(cxs)
            pitch = np.median(gaps[gaps > 0.5 * np.median(gaps)])  # ignore split-digit gaps
            n_cells = int(round((cxs[-1] - cxs[0]) / pitch)) + 1
            if n_cells == len(text) and gaps.max() / pitch < 2.6:
                w = float(np.median([d.x2 - d.x1 for d in ds])); y1 = float(np.median([d.y1 for d in ds])); y2 = float(np.median([d.y2 for d in ds]))
                ds = [assemble.Digit(0, 1.0, cxs[0] + k * pitch - w / 2, y1, cxs[0] + k * pitch + w / 2, y2) for k in range(len(text))]
                reasons["ok_lattice"] += 1
        if len(ds) != len(text):
            # lattice alignment (2026-10-21, owner-verified labels): the reader often finds the integer digits PLUS
            # the same-height decimal cells (CRYSTAL "198" -> 19868) or a leading ghost cell. If ALL detected digits
            # form one regular lattice and the label matches a window of the raw lattice (<=1 misread, offset<=2,
            # <=3 trailing cells), take that window as the integer digits; the other cells become background, which
            # is exactly what the app needs (fraction = not a digit).
            al = sorted([d for d in r.digits_all] if hasattr(r, "digits_all") else [], key=lambda d: d.cx)
            if not al:
                al = sorted([assemble.Digit(int(c), float(sc), x1_, y1_, x2_, y2_) for c, sc, x1_, y1_, x2_, y2_ in decode(*run_net(rd, ri), RD_PEAK_MIN) if c < 10], key=lambda d: d.cx)
            M, N = len(al), len(text)
            if M > N and M - N <= 6:
                raw = "".join(str(d.cls) for d in al)
                for k in range(0, min(4, M - N + 1)):
                    win = raw[k:k + N]; wd = al[k:k + N]
                    ham = sum(a != b for a, b in zip(win, text))
                    # the chosen window itself must be one regular lattice (pitch + height); cells outside it may be anything
                    cxs = np.array([d.cx for d in wd]); gaps = np.diff(cxs); hs = np.array([d.h for d in wd])
                    regular = N == 1 or (gaps.max() / max(gaps.min(), 1e-6) <= LATTICE_MAX_RATIO and hs.min() / hs.max() >= 0.75)
                    # leading cells may be skipped only on CRYSTAL (blank/ghost leading cells); on 6-cell displays a
                    # leading "0" is a real digit and must not be taught as background. Digits must be tall (>= 40% of
                    # the crop) so a barcode/serial line is never accepted as a reading.
                    tall = hs.mean() >= 0.40 * RD_H
                    if regular and tall and ham <= (0 if N <= 2 else 1) and (M - k - N) <= 4 and (k == 0 or types.get(fn) == "CRYSTAL"):
                        ds = al[k:k + N]
                        reasons["ok_align"] += 1
                        break
        if len(ds) != len(text):
            reasons["count_mismatch"] += 1
            continue
        # regular lattice check: centre pitch and heights must be consistent, else a decimal/ghost cell got swapped in
        cx = np.array([(d.x1 + d.x2) / 2 for d in ds])
        hs = np.array([d.y2 - d.y1 for d in ds])
        gaps = np.diff(np.sort(cx))
        if len(gaps) and (gaps.max() / max(gaps.min(), 1e-6) > LATTICE_MAX_RATIO or hs.min() / hs.max() < 0.75):
            reasons["irregular"] += 1
            continue
        reasons["ok_exact" if r.text == text else "ok_relabel"] += 1
        by_type[types.get(fn, "?")] = by_type.get(types.get(fn, "?"), 0) + 1
        i = len(X)
        X.append(ri)
        for d, ch in zip(ds, text):
            B.append((i, int(ch), d.x1, d.y1, d.x2, d.y2))
            hist[int(ch)] += 1
        lb = np.array([[d.x1, d.y1, d.x2, d.y2] for d in ds])
        B.append((i, CLS_LINE, lb[:, 0].min(), lb[:, 1].min(), lb[:, 2].max(), lb[:, 3].max()))
        keys.append(fn[:8])
        # Locator sample (ADR-0005: LINE = tight union of digit boxes). Map reader-crop coords -> photo -> 256 letterbox.
        rs = min(RD_W / (sx2 - sx1), RD_H / (sy2 - sy1))
        roy = (RD_H - int(round((sy2 - sy1) * rs))) // 2
        gx1, gx2 = sx1 + lb[:, 0].min() / rs, sx1 + lb[:, 2].max() / rs
        gy1, gy2 = sy1 + (lb[:, 1].min() - roy) / rs, sy1 + (lb[:, 3].max() - roy) / rs
        LX.append(li)
        LB.append((len(LX) - 1, CLS_LINE, gx1 * s + ox, gy1 * s + oy, gx2 * s + ox, gy2 * s + oy))
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
    LX = np.stack(LX)
    LB = np.array(LB, np.float32)
    for name, pick in (("train", lambda k: k not in val_keys), ("val", lambda k: k in val_keys)):
        idx = [i for i, k in enumerate(keys) if pick(k)]
        remap = {old: new for new, old in enumerate(idx)}
        Bi = np.array([(remap[int(b[0])], *b[1:]) for b in LB if int(b[0]) in remap], np.float32).reshape(-1, 6)
        np.save(f"{out_prefix}_loc_{name}_X.npy", LX[idx])
        np.save(f"{out_prefix}_loc_{name}_B.npy", Bi)
        print("locator", name, LX[idx].shape, len(Bi), "boxes")
    rep = {"reasons": reasons, "accepted": len(X), "accepted_by_type": by_type, "excluded_files": len(EXCLUDE_FILES), "test_hashes": len(TEST_HASHES), "class_hist": hist.tolist(), "n_train_keys": len(uniq) - len(val_keys), "n_val_keys": len(val_keys)}
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


def train(init, real_prefix, synth_prefixes, steps, out, kind="reader", lr=2e-4):
    """kind=reader: shards <prefix>_{train,val}; kind=locator: shards <prefix>_loc_{train,val}.
    lr 2e-4 (reader_v2 regressed 45->39/97 when resumed at 5e-4 — lab/logs/train_reader_v2_aborted.log)."""
    seed = int(os.environ.get("SEED", "0"))
    torch.manual_seed(seed); np.random.seed(seed)
    print("argv", sys.argv, "threads", torch.get_num_threads(), "seed", seed, flush=True)
    pre = real_prefix + ("_loc" if kind == "locator" else "")
    real = Shards([pre + "_train"], kind)
    real.ignore_row = os.environ.get("IGNORE_ROW", "0") == "1" and kind == "reader"   # loss masking (targets-conflict fix)
    print("ignore_row", real.ignore_row, flush=True)
    real.val_idx = []
    realval = Shards([pre + "_val"], kind)
    realval.val_idx = realval.train_idx + realval.val_idx
    synth = Shards(synth_prefixes.split(","), kind)
    n_cls = READER_CLASSES if kind == "reader" else LOCATOR_CLASSES
    if init in ("none", "scratch"):   # capacity experiment (consult #2 Q5): from scratch at WIDTH x channels
        width = float(os.environ.get("WIDTH", "1.0")); model = DigitNet(n_cls, width=width); print("init scratch width", width, flush=True)
    else:
        sd = torch.load(init, map_location="cpu"); model = DigitNet(n_cls, width=width_of(sd)); model.load_state_dict(sd)
    opt = torch.optim.AdamW(model.parameters(), lr, weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    B = BATCH[kind]
    # EMA of weights (consultation 2026-10-24, all 6 models): decay 0.999 ramped, start after 500 steps; exported
    # checkpoint = EMA weights (BN buffers copied from the live model). EMA=0 disables.
    ema_decay = float(os.environ.get("EMA", "0.999"))
    ema = {k: v.detach().clone() for k, v in model.state_dict().items()} if ema_decay > 0 else None
    run, t0 = None, time.time()
    for step in range(steps):
        xr, hr, sr, orr, mr, ir = real.batch(B // 2)
        xs, hs, ss, os_, ms, is_ = synth.batch(B - B // 2)
        x = torch.cat([xr, xs]); heat = torch.cat([hr, hs]); size = torch.cat([sr, ss]); off = torch.cat([orr, os_]); mask = torch.cat([mr, ms]); ign = torch.cat([ir, is_])
        hm, wh, of = model(x)
        loss = focal_loss(hm, heat, ign) + 0.1 * reg_loss(wh, size, mask) + reg_loss(of, off, mask)
        opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 10); opt.step(); sch.step()
        run = loss.item() if run is None else 0.98 * run + 0.02 * loss.item()
        if ema is not None and step >= 500:
            d = min(ema_decay, (1 + step - 500) / (10 + step - 500))
            with torch.no_grad():
                for k, v in model.state_dict().items():
                    if v.dtype.is_floating_point:
                        ema[k].mul_(d).add_(v.detach(), alpha=1 - d)
                    else:
                        ema[k].copy_(v)
        if step % 250 == 0 or step == steps - 1:
            if ema is not None and step >= 500:
                live = {k: v.detach().clone() for k, v in model.state_dict().items()}
                model.load_state_dict(ema); torch.save(model.state_dict(), out)
                if kind == "reader":
                    ok, n = real_exact(model, realval)
                else:
                    ok, n = validate(model, realval, 10**6)
                model.load_state_dict(live)
                print(f"step {step} loss {run:.3f} real_val_{'exact' if kind == 'reader' else 'line_iou50'} {ok}/{n} {time.time() - t0:.0f}s (EMA)", flush=True)
                continue
            torch.save(model.state_dict(), out)
            if kind == "reader":
                ok, n = real_exact(model, realval)
                print(f"step {step} loss {run:.3f} real_val_exact {ok}/{n} {time.time() - t0:.0f}s", flush=True)
            else:
                ok, n = validate(model, realval, 10**6)
                print(f"step {step} loss {run:.3f} real_val_line_iou50 {ok}/{n} {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(sys.argv[2], sys.argv[3], sys.argv[4])
    elif sys.argv[1] == "train":
        train(sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5]), sys.argv[6], sys.argv[7] if len(sys.argv) > 7 else "reader")
    else:
        print(__doc__)
