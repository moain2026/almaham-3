"""Risk-coverage curve for the shipped `confident` gate and for simple confidence thresholds, on the 49 (mode B,
whole photo) AND testset_human (34). Selective prediction: the app fills the field only when the gate passes;
otherwise the field stays empty (reject). Owner's '0.0 error' = among ACCEPTED readings, wrong must be ~0.
Usage: python3 risk_coverage.py <models_dir> <tag>   -> benchmark/results/engines/risk_coverage_<tag>.json
"""
import csv, json, sys
import cv2, numpy as np
import eval_e2e as e2e, paths, assemble

def collect(eng):
    out = []
    gt = {r["filename"]: r["reading"] for r in csv.DictReader(open(paths.BENCH_DATA / "ground_truth.csv"))}
    for fn, truth in gt.items():
        if not truth.isdigit():
            continue
        im = e2e.load_upright(fn)
        r = eng.read(im)[0]
        out.append(("49B", fn, truth, r))
    for g in csv.DictReader(open(paths.BENCH_DATA / "erp" / "testset_human.csv", encoding="utf-8")):
        im = cv2.imread(str(paths.DATA / "erp" / "photos" / g["filename"]))
        if im is None:
            continue
        out.append(("TH34", g["filename"], g["reading"], eng.read(im)[0]))
    return out

def stats(items, gate):
    acc = [(t, r) for _, _, t, r in items if r.value and gate(r)]
    n = len(items); a = len(acc)
    ok = sum((r.value.lstrip("0") or "0") == (t.lstrip("0") or "0") for t, r in acc)
    return {"n": n, "accepted": a, "correct": ok, "wrong": a - ok, "coverage": round(a / n, 3) if n else 0, "precision": round(ok / a, 3) if a else None}

def main():
    eng = e2e.Engine(sys.argv[1]); tag = sys.argv[2]
    items = collect(eng)
    gates = {
        "none (any value)": lambda r: True,
        "status OK": lambda r: r.status == "OK",
        "shipped confident": lambda r: r.confident,
        "OK & min_conf>=0.45": lambda r: r.status == "OK" and r.min_conf >= 0.45,
        "OK & min_conf>=0.55": lambda r: r.status == "OK" and r.min_conf >= 0.55,
        "OK & min_conf>=0.65": lambda r: r.status == "OK" and r.min_conf >= 0.65,
        "OK & min_conf>=0.55 & alt<0.5": lambda r: r.status == "OK" and r.min_conf >= 0.55 and all(d.alt_score < 0.5 * d.score for d in r.digits),
    }
    rep = {}
    for name, g in gates.items():
        rep[name] = {"all": stats(items, g), "49B": stats([i for i in items if i[0] == "49B"], g), "TH34": stats([i for i in items if i[0] == "TH34"], g)}
        a = rep[name]["all"]
        print(f'{name:32s} accepted {a["accepted"]:3d}/{a["n"]}  correct {a["correct"]:3d}  WRONG {a["wrong"]:3d}  coverage {a["coverage"]:.2f} precision {a["precision"]}')
    json.dump({"models": sys.argv[1], "gates": rep}, open(paths.RESULTS_ENGINES / f"risk_coverage_{tag}.json", "w"), indent=1)

if __name__ == "__main__":
    main()
