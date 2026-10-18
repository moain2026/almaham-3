"""Train SegReader from pre-generated synthetic npz files (with cheap online aug: shift/scale/invert)."""
import os, sys, time, numpy as np, torch, torch.nn as nn
from rec_model import SegReader, VOCAB
from train_rec import load_real, real_eval
torch.set_num_threads(int(os.environ.get("TORCH_THREADS", "2")))  # logs v1/v2 were run with 3 (LESSONS)
steps, width, outp = int(sys.argv[1]), float(sys.argv[2]), sys.argv[3]
files = sys.argv[4].split(","); resume = sys.argv[5] if len(sys.argv) > 5 else None
X = np.concatenate([np.load(f)["X"] for f in files]); Y = np.concatenate([np.load(f)["Y"] for f in files])
print("argv", sys.argv, "threads", torch.get_num_threads(), flush=True)  # always log the exact command (LESSONS)
print("data", X.shape)
model = SegReader(width)
if resume: model.load_state_dict(torch.load(resume))
opt = torch.optim.AdamW(model.parameters(), 3e-3, weight_decay=1e-4)
sch = torch.optim.lr_scheduler.OneCycleLR(opt, 3e-3, total_steps=steps, pct_start=0.06)
ctc = nn.CTCLoss(blank=0, zero_infinity=True); real = load_real(); B = 128; run = 0; t0 = time.time()
for step in range(steps):
    idx = np.random.randint(0, len(X), B)
    x = torch.from_numpy(X[idx]).float().div_(255).unsqueeze(1)
    if np.random.rand() < 0.5:  # contrast jitter
        a = torch.empty(B, 1, 1, 1).uniform_(0.6, 1.0); x = x * a + (1 - a) * torch.rand(B, 1, 1, 1)
    labs = Y[idx]
    tg = torch.tensor([VOCAB.index(c) + 1 for l in labs for c in l]); ln = torch.tensor([len(l) for l in labs])
    lp = model(x).permute(2, 0, 1).log_softmax(2)
    loss = ctc(lp, tg, torch.full((B,), lp.shape[0], dtype=torch.long), ln)
    opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 5); opt.step(); sch.step()
    run = 0.98 * run + 0.02 * loss.item() if step else loss.item()
    if step % 1000 == 0 or step == steps - 1:
        ok, _ = real_eval(model, real)
        print(f"step {step} loss {run:.3f} real {ok}/{len(real)} {time.time() - t0:.0f}s", flush=True)
        torch.save(model.state_dict(), outp)
