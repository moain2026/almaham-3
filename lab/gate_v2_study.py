"""Gate v2 study (consult #2 D3) on val-m4 end-to-end, never on the 49/34.
Fixed structure, measured component by component:
  G0  status OK & every digit score>=0.45 & alt<0.5*score            (= today's `OK & not uncertain` without the 7-seg veto)
  G1  G0 & min_conf >= T                                              (T = the ONE free threshold; swept, then LTT on half)
  G2  G1 & TTA agreement: the string is identical under gamma 0.7 / 1.4 and scale 0.92 / 1.08 re-reads of the meter crop
  G3  G2 & previous-reading window: prev <= value <= prev + K*M (prev SIMULATED = truth - U(0,M), M=500, K=2, 50 draws)
Also reports the error TYPE of each accepted-wrong reading (length error vs same-length substitution): length errors are
exactly what the previous-reading window kills, substitutions are what remains.
Usage: python3 gate_v2_study.py ../data/models_<tag> <tag>   -> benchmark/results/engines/gate_v2_<tag>.json
"""
import sys, json, random, cv2, numpy as np
import paths, erp_finetune as ef
from eval_e2e import Engine
from build_meter_shards import load_meter_boxes

PRE = "../data/erp/ft/m4"; random.seed(0)


def tta_views(crop):
    out = []
    for g in (0.7, 1.4):
        lut = (np.linspace(0, 1, 256) ** g * 255).astype(np.uint8); out.append(cv2.LUT(crop, lut))
    H, W = crop.shape[:2]
    for s in (0.92, 1.08):
        r = cv2.resize(crop, (max(8, int(W * s)), max(8, int(H * s))), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
        if s < 1:   # pad back to the original size (grey) so the locator sees the same framing
            canvas = np.full_like(crop, 128); y0, x0 = (H - r.shape[0]) // 2, (W - r.shape[1]) // 2
            canvas[y0:y0 + r.shape[0], x0:x0 + r.shape[1]] = r; out.append(canvas)
        else:
            y0, x0 = (r.shape[0] - H) // 2, (r.shape[1] - W) // 2; out.append(r[y0:y0 + H, x0:x0 + W])
    return out


def main(models_dir, tag):
    eng = Engine(models_dir); eng.read(np.full((80, 64, 3), 128, np.uint8))
    d = json.load(open(f"{PRE}_val_clean_idx.json")); files = d["val_order"]; clean = set(d["clean_idx"])
    boxes = load_meter_boxes(); labels = ef.load_labels()
    rows = []
    for i, fn in enumerate(files):
        im = cv2.imread(str(ef.ERP / "photos" / fn)); H, W = im.shape[:2]
        mx1, my1, mx2, my2 = boxes[fn]; crop = im[int(my1 * H):int(my2 * H), int(mx1 * W):int(mx2 * W)]
        r, rect, ls, ms, _ = eng.read(crop)
        truth = (labels.get(fn) or "").lstrip("0") or "0"
        g0 = r.status == "OK" and r.value != "" and all(dg.score >= 0.45 and dg.alt_score < 0.5 * dg.score for dg in r.digits)
        tta = [eng.read(v)[0].value for v in tta_views(crop)] if g0 else []
        agree = bool(tta) and all(t == r.value for t in tta)
        cx = sorted((dg.x1 + dg.x2) / 2 for dg in r.digits); pitch_cv = float(np.std(np.diff(cx)) / max(np.mean(np.diff(cx)), 1e-6)) if len(cx) >= 3 else 0.0
        # previous-reading window (simulated)
        prev_ok = None
        if r.value:
            M, K, hits = 500, 2.0, 0
            for _ in range(50):
                prev = max(0, int(truth) - random.randint(0, M)); hits += prev <= int(r.value) <= prev + K * M
            prev_ok = hits / 50
        etype = "" if r.value == truth else ("empty" if not r.value else ("length" if len(r.value) != len(truth) else "subst"))
        rows.append(dict(i=i, f=fn[:12], clean=i in clean, truth=truth, value=r.value, ok=r.value == truth, status=r.status,
                         min_conf=round(r.min_conf, 3), g0=bool(g0), tta=tta, agree=bool(agree), pitch_cv=round(pitch_cv, 3),
                         n=len(r.digits), prev_ok=prev_ok, etype=etype))
    res = dict(models=models_dir, tag=tag, rows=rows)
    json.dump(res, open(paths.RESULTS_ENGINES / f"gate_v2_{tag}.json", "w"), indent=0, ensure_ascii=False)
    report(rows, tag)


def report(rows, tag):
    def rc(sel, name):
        a = [r for r in rows if sel(r)]; w = [r for r in a if not r["ok"]]
        c = [r for r in a if r["clean"]]; cw = [r for r in c if not r["ok"]]
        print(f"  {name:42s} all177: acc {len(a):3d} wrong {len(w):2d} [{','.join(sorted(set(r['etype'] for r in w)))}] | clean65: acc {len(c):2d} wrong {len(cw)}")
    print(f"== {tag}: exact all {sum(r['ok'] for r in rows)}/177, clean {sum(r['ok'] for r in rows if r['clean'])}/65")
    rc(lambda r: r["g0"], "G0 OK&score>=.45&alt<.5")
    for T in (0.50, 0.55, 0.60):
        rc(lambda r, T=T: r["g0"] and r["min_conf"] >= T, f"G1 G0&min_conf>={T}")
    rc(lambda r: r["g0"] and r["agree"], "G2a G0&TTA-agree")
    for T in (0.45, 0.50, 0.55):
        rc(lambda r, T=T: r["g0"] and r["agree"] and r["min_conf"] >= T, f"G2 G0&TTA&min_conf>={T}")
    rc(lambda r: r["g0"] and (r["prev_ok"] or 0) >= 0.98, "G3a G0&prev-window")
    for T in (0.45, 0.50, 0.55):
        rc(lambda r, T=T: r["g0"] and (r["prev_ok"] or 0) >= 0.98 and r["min_conf"] >= T, f"G3 G0&prev&min_conf>={T}")
        rc(lambda r, T=T: r["g0"] and r["agree"] and (r["prev_ok"] or 0) >= 0.98 and r["min_conf"] >= T, f"G4 G0&TTA&prev&min_conf>={T}")
    w = [r for r in rows if r["g0"] and not r["ok"]]
    print("  G0 wrong:", [(r["value"], r["truth"], r["min_conf"], r["etype"], "agree" if r["agree"] else "disagree") for r in w])


if __name__ == "__main__":
    if sys.argv[1] == "report":
        report(json.load(open(sys.argv[2]))["rows"], sys.argv[2])
    else:
        main(sys.argv[1], sys.argv[2])
