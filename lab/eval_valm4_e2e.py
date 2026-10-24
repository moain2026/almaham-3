"""End-to-end (locator -> line crop -> reader -> assemble) evaluation of an exported model pair on val-m4,
split into clean65 (never in any model's training) and seen112 (were in the reference's training).
Mirrors the product path exactly (eval_e2e.Engine on the meter crop), unlike eval_valm4.py which scores
the reader alone on the stored 64x448 crop.
Usage:
  python3 eval_valm4_e2e.py ../data/models_<tag> <tag>   -> benchmark/results/engines/valm4_e2e_<tag>.json
  python3 eval_valm4_e2e.py compare <A.json> <B.json>      -> exact paired McNemar on clean65 and on all 177
"""
import sys, json, csv, cv2, numpy as np
import paths, erp_finetune as ef
from eval_e2e import Engine, load_upright
from build_meter_shards import load_meter_boxes

PRE = "../data/erp/ft/m4"; OUT = paths.RESULTS_ENGINES


def val_files():
    """(filename, truth) for the 177 val-m4 photos in the stored val order (m4_val_clean_idx.json)."""
    d = json.load(open(f"{PRE}_val_clean_idx.json"))
    labels = ef.load_labels()
    return d["val_order"], set(d["clean_idx"]), labels


def main(models_dir, tag):
    eng = Engine(models_dir); eng.read(np.full((80, 64, 3), 128, np.uint8))
    files, clean, labels = val_files(); boxes = load_meter_boxes()
    types = {r["filename"]: r["meter_type"] for r in csv.DictReader(open(paths.BENCH_DATA / "erp" / "labels_agentD.csv", encoding="utf-8"))}
    rows = []
    for i, fn in enumerate(files):
        im = cv2.imread(str(ef.ERP / "photos" / fn)); H, W = im.shape[:2]
        mx1, my1, mx2, my2 = boxes[fn]; crop = im[int(my1 * H):int(my2 * H), int(mx1 * W):int(mx2 * W)]
        r, rect, ls, ms, _ = eng.read(crop)
        truth = (labels.get(fn) or "").lstrip("0") or "0"
        strict = r.status == "OK" and r.value != "" and r.min_conf >= 0.55 and all(d.alt_score < 0.5 * d.score for d in r.digits)
        rows.append(dict(i=i, f=fn[:12], type=types.get(fn, "?"), clean=i in clean, truth=truth, value=r.value, ok=r.value == truth,
                         status=r.status, min_conf=round(r.min_conf, 3), confident=bool(r.confident), strict=bool(strict), line_score=round(ls, 3)))
    def summ(rs):
        acc = [r for r in rs if r["strict"]]; conf = [r for r in rs if r["confident"]]
        return dict(n=len(rs), exact=sum(r["ok"] for r in rs), empty=sum(r["value"] == "" for r in rs),
                    wrong=sum(bool(r["value"]) and not r["ok"] for r in rs),
                    confident_total=len(conf), confident_wrong=sum(not r["ok"] for r in conf),
                    strict_accepted=len(acc), strict_wrong=sum(not r["ok"] for r in acc))
    res = dict(models=models_dir, tag=tag, all=summ(rows), clean65=summ([r for r in rows if r["clean"]]),
               seen=summ([r for r in rows if not r["clean"]]), rows=rows)
    json.dump(res, open(OUT / f"valm4_e2e_{tag}.json", "w"), indent=0, ensure_ascii=False)
    for k in ("clean65", "seen", "all"):
        s = res[k]
        print(f"{tag} {k}: exact {s['exact']}/{s['n']} empty {s['empty']} wrong {s['wrong']} | confident {s['confident_total']} (wrong {s['confident_wrong']}) | strict {s['strict_accepted']} (wrong {s['strict_wrong']})")


def mcnemar(a, b):
    from math import comb
    def cdf(k, n): return sum(comb(n, i) for i in range(k + 1)) / 2 ** n
    A = json.load(open(a)); B = json.load(open(b))
    for name, flt in (("clean65", lambda r: r["clean"]), ("all177", lambda r: True)):
        oa = {r["i"]: r["ok"] for r in A["rows"] if flt(r)}; ob = {r["i"]: r["ok"] for r in B["rows"] if flt(r)}
        ids = sorted(set(oa) & set(ob)); b01 = sum(1 for i in ids if not oa[i] and ob[i]); b10 = sum(1 for i in ids if oa[i] and not ob[i])
        nd = b01 + b10; p = min(1.0, 2 * cdf(min(b01, b10), nd)) if nd else 1.0
        print(f"{name}: {A['tag']} {sum(oa.values())}/{len(ids)} vs {B['tag']} {sum(ob.values())}/{len(ids)} | only-B {b01} only-A {b10} | McNemar p={p:.3f}")


if __name__ == "__main__":
    if sys.argv[1] == "compare": mcnemar(sys.argv[2], sys.argv[3])
    else: main(sys.argv[1], sys.argv[2])
