"""Honest model selection on val-m4 (pHash-cluster split, 177 reader crops / 177 locator crops), never on the 49/34.
Reader: exact integer via assemble on the stored 64x448 crop (same as fit_diag). Also per-photo outcome vector so two
candidates can be compared with an exact paired McNemar test (consult #2 Q4).
Usage:
  python3 eval_valm4.py reader  <ckpt.pt|ens:a.pt,b.pt,c.pt> <tag>        -> benchmark/results/engines/valm4_reader_<tag>.json
  python3 eval_valm4.py compare benchmark/results/engines/valm4_reader_<A>.json benchmark/results/engines/valm4_reader_<B>.json
"""
import sys, json, numpy as np, torch, torch.nn.functional as F
import assemble
from det_model import DigitNet, READER_CLASSES, decode, width_of
from eval_e2e import RD_W, RD_H, RD_PEAK_MIN
PRE = "../data/erp/ft/m4"; OUT = "../benchmark/results/engines/"

def load(spec):
    cks = spec[4:].split(",") if spec.startswith("ens:") else [spec]
    ms = []
    for c in cks:
        sd = torch.load(c, map_location="cpu"); m = DigitNet(READER_CLASSES, width=width_of(sd)); m.load_state_dict(sd); m.eval(); ms.append(m)
    return ms

def run(ms, x):
    xt = torch.from_numpy(np.asarray(x, np.float32)[None])
    with torch.no_grad():
        hs, ws, os_ = [], [], []
        for m in ms:
            hm, wh, off = m(xt); hs.append(torch.sigmoid(hm)); ws.append(F.relu(wh)); os_.append(off)
        heat = torch.stack(hs).mean(0); wh = torch.stack(ws).mean(0); off = torch.stack(os_).mean(0)
        keep = (F.max_pool2d(heat, 3, 1, 1) == heat).float()
        return (heat * keep)[0].numpy(), wh[0].numpy(), off[0].numpy()

def evaluate(spec, tag):
    ms = load(spec); X = np.load(f"{PRE}_val_X.npy", mmap_mode="r"); B = np.load(f"{PRE}_val_B.npy")
    keys = json.load(open(f"{PRE}_keys.json"))
    rows = []
    for i in range(len(X)):
        rb = B[B[:, 0] == i]; digs = rb[rb[:, 1] < 10]
        if not len(digs): continue
        truth = "".join(str(int(c)) for c in digs[np.argsort(digs[:, 2]), 1]).lstrip("0") or "0"
        r = assemble.assemble(decode(*run(ms, X[i]), RD_PEAK_MIN), RD_W, RD_H)
        strict = r.status == "OK" and r.value != "" and r.min_conf >= 0.55 and all(d.alt_score < 0.5 * d.score for d in r.digits)
        rows.append(dict(i=i, truth=truth, value=r.value, ok=r.value == truth, status=r.status, min_conf=round(r.min_conf, 3), strict=strict))
    n = len(rows); k = sum(r["ok"] for r in rows); acc = [r for r in rows if r["strict"]]
    res = dict(spec=spec, tag=tag, n=n, exact=k, strict_accepted=len(acc), strict_wrong=sum(not r["ok"] for r in acc), rows=rows)
    json.dump(res, open(f"{OUT}valm4_reader_{tag}.json", "w"), indent=0)
    print(f"{tag}: val-m4 exact {k}/{n} = {k/n:.3f} | strict gate accepted {len(acc)} wrong {res['strict_wrong']}")

def mcnemar(a, b):
    """exact two-sided McNemar on paired per-photo outcomes."""
    from scipy.stats import binom
    A = json.load(open(a)); Bj = json.load(open(b))
    oa = {r["i"]: r["ok"] for r in A["rows"]}; ob = {r["i"]: r["ok"] for r in Bj["rows"]}
    ids = sorted(set(oa) & set(ob)); b01 = sum(1 for i in ids if not oa[i] and ob[i]); b10 = sum(1 for i in ids if oa[i] and not ob[i])
    nd = b01 + b10; p = min(1.0, 2 * binom.cdf(min(b01, b10), nd, 0.5)) if nd else 1.0
    print(f"{A['tag']} exact {A['exact']}/{A['n']}  vs  {Bj['tag']} exact {Bj['exact']}/{Bj['n']}")
    print(f"  discordant: only-B-right {b01}, only-A-right {b10}  -> exact McNemar p = {p:.3f}  ({'B better' if b01>b10 else 'A better' if b10>b01 else 'tie'}{', significant' if p<0.05 else ', not significant'})")

if __name__ == "__main__":
    if sys.argv[1] == "reader": evaluate(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == "compare": mcnemar(sys.argv[2], sys.argv[3])
