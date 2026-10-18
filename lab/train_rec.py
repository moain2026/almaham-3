"""Train SegReader on synthetic lines only. Real photos are used for evaluation only (never as training samples)."""
import paths
import os, sys, time, json, csv, random
import cv2
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import IterableDataset, DataLoader
from rec_model import SegReader, VOCAB, greedy_decode
from prep import to_input
import synth

torch.set_num_threads(int(os.environ.get("TORCH_THREADS", "2")))  # logs v1/v2 were run with 3 (LESSONS)


class Synth(IterableDataset):
    def __iter__(self):
        wi = torch.utils.data.get_worker_info()
        seed = (wi.id if wi else 0) * 7919 + int(time.time() * 1000) % 100000
        random.seed(seed); np.random.seed(seed % (2 ** 31))
        while True:
            im, lab = synth.sample()
            yield torch.from_numpy(to_input(im)), lab


def collate(b):
    x = torch.stack([i[0] for i in b])
    labs = [i[1] for i in b]
    tg = torch.tensor([VOCAB.index(c) + 1 for l in labs for c in l], dtype=torch.long)
    ln = torch.tensor([len(l) for l in labs], dtype=torch.long)
    return x, tg, ln, labs


def real_eval(model, crops):
    model.eval(); ok = 0; outs = []
    with torch.no_grad():
        x = torch.stack([torch.from_numpy(to_input(c)) for c, _ in crops])
        lg = model(x)
    for i, (_, g) in enumerate(crops):
        t, _ = greedy_decode(lg[i])
        ip = t.split(".")[0]
        v = str(int(ip)) if ip.isdigit() else ""
        ok += v == g; outs.append(t)
    model.train()
    return ok, outs


def load_real():
    S = paths.PHOTOS_S
    gt = {r["filename"]: r["reading"] for r in csv.DictReader(open(paths.GROUND_TRUTH))}
    lines = json.load(open(paths.LINE_BOXES))
    out = []
    for fn, (x1, y1, x2, y2) in sorted(lines.items()):
        im = cv2.imread(S + fn); H, W = im.shape[:2]
        out.append((im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)], gt[fn]))
    return out


def main(steps, width, out_path, resume=None):
    model = SegReader(width)
    if resume: model.load_state_dict(torch.load(resume))
    print("argv", sys.argv, "threads", torch.get_num_threads(), flush=True)
    print("params", sum(p.numel() for p in model.parameters()))
    dl = DataLoader(Synth(), batch_size=96, num_workers=3, collate_fn=collate, prefetch_factor=4)
    opt = torch.optim.AdamW(model.parameters(), 2e-3, weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.OneCycleLR(opt, 2e-3, total_steps=steps, pct_start=0.08)
    ctc = nn.CTCLoss(blank=0, zero_infinity=True)
    real = load_real(); t0 = time.time(); run = 0
    for step, (x, tg, ln, labs) in enumerate(dl):
        if step >= steps: break
        lg = model(x)  # B,K,T
        lp = lg.permute(2, 0, 1).log_softmax(2)
        loss = ctc(lp, tg, torch.full((x.shape[0],), lp.shape[0], dtype=torch.long), ln)
        opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 5); opt.step(); sch.step()
        run = 0.98 * run + 0.02 * loss.item() if step else loss.item()
        if step % 500 == 0 or step == steps - 1:
            ok, _ = real_eval(model, real)
            print(f"step {step} loss {run:.3f} real {ok}/{len(real)} {time.time() - t0:.0f}s", flush=True)
            torch.save(model.state_dict(), out_path)
    torch.save(model.state_dict(), out_path)


if __name__ == "__main__":
    main(int(sys.argv[1]), float(sys.argv[2]), sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
