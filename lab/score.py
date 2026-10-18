"""Score raw engine outputs vs ground truth using a generic 'largest digit line' picker + cleaning."""
import paths
import json, csv, re, sys, statistics as st
gt = {r["filename"]: r for r in csv.DictReader(open(paths.GROUND_TRUTH))}
def pick(items):
    best = None
    for t, s, b in items:
        d = re.sub(r"[^0-9]", "", t.replace("O", "0").replace("o", "0"))
        if len(d) < 3: continue
        h = max(p[1] for p in b) - min(p[1] for p in b)
        if re.search(r"[A-Za-z]{2,}", t): continue
        if best is None or h > best[0]: best = (h, d, s)
    return best
def clean(d, n_int=6):
    core = d[:n_int] if len(d) > n_int else d
    return str(int(core)) if core else ""
for name in sys.argv[1:]:
    raw = json.load(open(paths.RESULTS_RAW / f"raw_{name}.json"))
    for mode in "AB":
        ok = no = wrong = 0; tm = []; readable = 0
        for fn, g in gt.items():
            r = raw[f"{fn}|{mode}"]; tm.append(r["ms"])
            if not g["reading"]: continue
            readable += 1
            p = pick(r["items"])
            if p is None: no += 1; continue
            v = clean(p[1])
            if v == g["reading"]: ok += 1
            else: wrong += 1
        tm.sort()
        print(f"{name:16s} mode {mode}: exact {ok}/{readable} ({ok/readable:.0%}) wrong {wrong} noread {no} | p50 {st.median(tm):.0f}ms p95 {tm[int(.95*len(tm))]:.0f}ms (sandbox CPU)")
