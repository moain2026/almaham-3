"""How much would a previous-reading plausibility check help the gate? (owner 2026-10-24: previous reading IS
available in the app at capture time; UI shows e.g. 'previous 2259' and the model fills 3155).
We have no real previous readings for the eval photos, so we SIMULATE: prev = truth - U(0, M) where M is the monthly
consumption budget, and the check accepts a prediction p iff prev <= p <= prev + K*M.  A wrong prediction survives
only if it lands inside that window. Report, over many draws, the fraction of wrong predictions caught and the
fraction of correct predictions wrongly rejected, for several (M, K). Uses the model's actual wrong values on the 49
(A+B) and 34 from benchmark/results/engines (reference pair + m4 readers).
Also: digit-swap errors (same length) vs magnitude errors (x10, /10, extra/missing digit) — the latter are what the
window catches almost surely."""
import json, csv, glob, random, sys
random.seed(0)
def load_rows(tag):
    rows = []
    for m in "AB":
        d = json.load(open(f"../benchmark/results/engines/digitnet_{tag}_{m}.json"))["rows"]
        rows += [(r["truth"], r["value"], r["status"]) for r in d if r["truth"]]
    th = json.load(open(f"../benchmark/results/engines/testset_human_{tag}.json"))
    for r in th.get("rows", []):
        if r.get("truth"): rows.append((r["truth"], r.get("value", ""), r.get("status", "")))
    return rows
def sim(rows, M=400, K=2.0, draws=200):
    caught = total_wrong = rej_ok = total_ok = 0
    for truth, val, st in rows:
        if val == "" or not val.isdigit() or not truth.isdigit(): continue
        t, p = int(truth), int(val)
        for _ in range(draws):
            prev = max(0, t - random.randint(0, M))
            ok = prev <= p <= prev + K * M
            if p == t: total_ok += 1; rej_ok += (not ok)
            else: total_wrong += 1; caught += (not ok)
    return caught / max(1, total_wrong), rej_ok / max(1, total_ok), total_wrong // draws, total_ok // draws
for tag in ["check", "m1loc_reader_m4_s0", "m1loc_reader_m4_s1"]:
    try: rows = load_rows(tag)
    except FileNotFoundError as e: print(tag, "missing", e); continue
    wrong = [(t, v) for t, v, s in rows if v and v != t]
    same_len = sum(1 for t, v in wrong if len(v) == len(t)); mag = len(wrong) - same_len
    print(f"\n== {tag}: n={len(rows)} wrong={len(wrong)} (same-length digit swaps {same_len}, magnitude/length errors {mag})")
    for M, K in ((300, 2), (500, 2), (500, 3), (1000, 2)):
        c, r, nw, nk = sim(rows, M, K)
        print(f"  monthly budget M={M:4d} kWh, window K={K}: wrong caught {c:5.1%} (of {nw}), correct rejected {r:5.1%} (of {nk})")
    # what survives: same-length swaps with small numeric distance
    surv = [(t, v) for t, v in wrong if len(v) == len(t) and abs(int(v) - int(t)) < 1000]
    print("  wrong readings that a 2x500 window would typically NOT catch (same length, |diff|<1000):", surv[:12])

# ---- combined with a looser confidence gate: window first, then min_conf >= t ----
print("\n== Combined: prev-window (M=500,K=2, prev=truth-U(0,M)) + min_conf >= t, on the 49 A+B rows (which carry min_conf)")
for tag in ["check", "m1loc_reader_m4_s0"]:
    rows = []
    for m in "AB":
        rows += [r for r in json.load(open(f"../benchmark/results/engines/digitnet_{tag}_{m}.json"))["rows"] if r["truth"]]
    print(f"  {tag}:")
    for t in (0.55, 0.45, 0.40, 0.35):
        acc = wrong = acc_w = wrong_w = 0
        for r in rows:
            if r["status"] != "OK" or not r["value"] or r["min_conf"] < t: continue
            acc += 1; wrong += r["value"] != r["truth"]
            # window (expected over draws)
            tv, pv = int(r["truth"]), int(r["value"]); n = 0
            for _ in range(200):
                prev = max(0, tv - random.randint(0, 500)); n += prev <= pv <= prev + 1000
            frac = n / 200; acc_w += frac; wrong_w += frac * (r["value"] != r["truth"])
        print(f"    min_conf>={t:.2f}: gate alone accepted {acc:2d} wrong {wrong:2d}  |  + prev-window: accepted {acc_w:5.1f} wrong {wrong_w:4.1f}  (of {len(rows)})")
