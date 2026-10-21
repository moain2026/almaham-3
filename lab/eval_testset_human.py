"""Exact-match on the frozen human ERP test set (benchmark/data/erp/testset_human.csv, agent D + owner-verified).

Usage: python3 eval_testset_human.py <models_dir> [tag]
ERP photos have no user rectangle, so this is whole-photo mode (like mode B on the 49). Reading compared as
integers (leading zeros stripped on both sides) — the app shows the integer part only.
Writes benchmark/results/engines/testset_human_<tag>.json. The set is evaluation only, never trained on
(erp_finetune.py excludes it by sha256 and by filename, plus the sibling list).
"""
import csv, json, sys
import cv2
import paths
import eval_e2e as e2e


def main():
    models = sys.argv[1]; tag = sys.argv[2] if len(sys.argv) > 2 else "x"
    eng = e2e.Engine(models)
    rows = []; ok = 0; by_type = {}
    for g in csv.DictReader(open(paths.BENCH_DATA / "erp" / "testset_human.csv", encoding="utf-8")):
        p = paths.ERP_PHOTOS / g["filename"] if hasattr(paths, "ERP_PHOTOS") else paths.DATA / "erp" / "photos" / g["filename"]
        im = cv2.imread(str(p))
        if im is None:
            rows.append({"file": g["filename"], "truth": g["reading"], "value": None, "ok": False, "note": "missing photo"}); continue
        r = eng.read(im)[0]
        truth = g["reading"].lstrip("0") or "0"; val = (r.value or "").lstrip("0") or ("0" if r.value else "")
        hit = val == truth; ok += hit
        t = g["meter_type"]; by_type.setdefault(t, [0, 0]); by_type[t][0] += hit; by_type[t][1] += 1
        rows.append({"file": g["filename"], "type": t, "truth": g["reading"], "value": r.value, "raw": r.text, "status": r.status, "ok": hit})
        print(f'{g["filename"][:8]} {t:13s} truth={g["reading"]:>7} got={str(r.value):>7} {"OK" if hit else "--"}')
    summ = {"models": models, "n": len(rows), "exact": ok, "by_type": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_type.items())}}
    print(json.dumps(summ, ensure_ascii=False))
    paths.ensure_dirs()
    json.dump({"summary": summ, "rows": rows}, open(paths.RESULTS_ENGINES / f"testset_human_{tag}.json", "w"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    main()
