"""Q5 zero-cost diagnostic (Opus 5.5, 2026-10-24): run a reader on its own REAL training crops (no augmentation) and on
the val crops; exact integer match via assemble + median correct-cell score. Underfitting if train ~= val; data-limited
if train >> val.  Usage: python3 fit_diag.py <reader.pt> <shard_prefix>   e.g. weights/reader_ft6m2_s1.pt ../data/erp/ft/m4"""
import sys, numpy as np, torch
import assemble, erp_finetune as ef
from det_model import DigitNet, READER_CLASSES, decode
from eval_e2e import RD_W, RD_H, RD_PEAK_MIN
pt, pre = sys.argv[1], sys.argv[2]
m = DigitNet(READER_CLASSES); m.load_state_dict(torch.load(pt, map_location="cpu")); m.eval()
for split in ("train", "val"):
    X = np.load(f"{pre}_{split}_X.npy", mmap_mode="r"); B = np.load(f"{pre}_{split}_B.npy")
    ok = n = 0; scores = []
    for i in range(len(X)):
        rows = B[B[:, 0] == i]; digs = rows[rows[:, 1] < 10]
        if not len(digs): continue
        truth = "".join(str(int(c)) for c in digs[np.argsort(digs[:, 2]), 1]).lstrip("0") or "0"
        dets = decode(*ef.run_net(m, np.asarray(X[i])), RD_PEAK_MIN)
        r = assemble.assemble(dets, RD_W, RD_H); n += 1; ok += r.value == truth
        if r.value == truth and r.digits: scores.append(min(d.score for d in r.digits))
    print(f"{split}: exact {ok}/{n} = {ok/n:.3f}   median min-score of correct readings {np.median(scores):.2f}  (n={len(scores)})")
