"""Build LOCATOR + READER shards from WHOLE-METER crops (the app's real input) using
  * agent D's meter boxes          (erp/manifests/meter_bbox_agentD_*.jsonl, fraction x1,y1,x2,y2 of the photo)
  * text-supervised line boxes     (data/erp/ft/text_locate_*.json, photo px; from lab/text_locate.py)
  * owner-verified readings        (benchmark/data/erp/labels_agentD.csv) -> digit classes

For each photo that has all three and passes the anti-poisoning test (critic round 2026-10-21):
  locator sample: meter crop -> 256x256 letterbox, LINE box = union of the digit boxes (ADR-0005)
  reader  sample: line box padded PAD_X/PAD_Y inside the meter crop -> 64x448 letterbox, digit boxes + LINE
Split by photo key (first 8 chars) 85/15, seed 0. Excludes the 49, testset_human (+siblings), rejected, multi-meter.

Anti-poisoning (per text_locate result): score >= MIN_SCORE; digits >= 5 OR (type in SHORT_OK and score >= 0.5);
digit boxes form one lattice (pitch ratio <= 1.5, height ratio >= 0.75); line inside the meter box.
Writes <out>_{train,val}_{X,B}.npy, <out>_loc_{train,val}_{X,B}.npy, <out>_report.json (+ per-type counts),
and a review sheet data/review/meter_shards_<name>.jpg of 40 random samples for the 100-box human audit.

Usage: python3 build_meter_shards.py <text_locate.json> <out_prefix> [--audit N]
"""
import csv, json, sys, hashlib, glob
import cv2
import numpy as np
import paths
import erp_finetune as ef
from eval_e2e import LOC_IN, RD_W, RD_H, PAD_X, PAD_Y, letterbox
from synth2 import CLS_LINE

MIN_SCORE = 0.35
SHORT_OK = {"CRYSTAL", "KENWELL", "GLORY"}
PRIV = paths.DATA.parent.parent / "almaham-3-private-data" if (paths.DATA.parent.parent / "almaham-3-private-data").exists() else None


def load_meter_boxes():
    bb = {}
    for f in sorted(glob.glob(str(paths.DATA / "erp" / "manifests" / "meter_bbox_agentD_*.jsonl"))) or sorted(glob.glob(str(PRIV / "erp" / "manifests" / "meter_bbox_agentD_*.jsonl"))):
        for ln in open(f):
            d = json.loads(ln); bb[d["f"]] = d["b"]
    # agent D b6/b7: photos that are already a whole-meter close-up carry crop=none in erp/by_type/<T>/index.csv
    # (the by_type file has the photo's own size) -> meter box = whole photo.
    if PRIV:
        for f in glob.glob(str(PRIV / "erp" / "by_type" / "*" / "index.csv")):
            for r in csv.DictReader(open(f, encoding="utf-8")):
                if r.get("crop") == "none" and r["filename"] not in bb:
                    bb[r["filename"]] = [0.0, 0.0, 1.0, 1.0]
    return bb


def multi_meter():
    out = set()
    for f in glob.glob(str(paths.DATA / "erp" / "manifests" / "pools_b3_agentD.json")) + ([str(PRIV / "erp" / "manifests" / "pools_b3_agentD.json")] if PRIV else []):
        try:
            out |= set(json.load(open(f)).get("group", []))
        except Exception:  # noqa: BLE001
            pass
    return out


def main():
    tl = {}
    for f in sys.argv[1].split(","):   # several text_locate result files (parallel workers); a located entry wins
        for k, v in json.load(open(f)).items():
            if k not in tl or (v and not tl.get(k)):
                tl[k] = v
    out = sys.argv[2]
    audit = int(sys.argv[sys.argv.index("--audit") + 1]) if "--audit" in sys.argv else 40
    labels = ef.load_labels(); boxes = load_meter_boxes(); multi = multi_meter()
    types = {r["filename"]: r["meter_type"] for r in csv.DictReader(open(paths.BENCH_DATA / "erp" / "labels_agentD.csv", encoding="utf-8"))}
    reasons = {"no_tl": 0, "no_meterbox": 0, "excluded": 0, "multi": 0, "low_score": 0, "short_unsafe": 0, "irregular": 0, "outside_meter": 0, "ok": 0}
    X, B, LX, LB, keys, by_type, review = [], [], [], [], [], {}, []
    for fn, res in sorted(tl.items()):
        text = labels.get(fn)
        if not res or not text:
            reasons["no_tl"] += 1; continue
        if fn not in boxes:
            reasons["no_meterbox"] += 1; continue
        p = ef.ERP / "photos" / fn
        if fn in ef.EXCLUDE_FILES or hashlib.sha256(open(p, "rb").read()).hexdigest() in ef.TEST_HASHES:
            reasons["excluded"] += 1; continue
        if fn in multi:
            reasons["multi"] += 1; continue
        if res["score"] < MIN_SCORE:
            reasons["low_score"] += 1; continue
        t = types.get(fn, "?")
        if len(text) < 5 and not (t in SHORT_OK and res["score"] >= 0.5):
            reasons["short_unsafe"] += 1; continue
        digs = sorted(res["digits"], key=lambda d: d[1])
        cx = np.array([(d[1] + d[3]) / 2 for d in digs]); hs = np.array([d[4] - d[2] for d in digs])
        if len(digs) >= 2:
            gaps = np.diff(cx)
            if gaps.max() / max(gaps.min(), 1e-6) > ef.LATTICE_MAX_RATIO or hs.min() / hs.max() < 0.75:
                reasons["irregular"] += 1; continue
        im = cv2.imread(str(p)); H, W = im.shape[:2]
        mx1, my1, mx2, my2 = boxes[fn]; mx1, my1, mx2, my2 = int(mx1 * W), int(my1 * H), int(mx2 * W), int(my2 * H)
        lx1, ly1, lx2, ly2 = res["line"]
        if not (mx1 - 5 <= lx1 and ly1 >= my1 - 5 and lx2 <= mx2 + 5 and ly2 <= my2 + 5):
            reasons["outside_meter"] += 1; continue
        crop = im[my1:my2, mx1:mx2]; ch, cw = crop.shape[:2]
        # ---- locator sample (meter crop -> 256)
        li, s, ox, oy = letterbox(crop, LOC_IN, LOC_IN)
        LX.append(li); LB.append((len(LX) - 1, CLS_LINE, (lx1 - mx1) * s + ox, (ly1 - my1) * s + oy, (lx2 - mx1) * s + ox, (ly2 - my1) * s + oy))
        # ---- reader sample (padded line crop -> 64x448)
        px, py = (lx2 - lx1) * PAD_X, (ly2 - ly1) * PAD_Y
        sx1, sy1 = int(np.clip(lx1 - px - mx1, 0, cw - 1)), int(np.clip(ly1 - py - my1, 0, ch - 1))
        sx2, sy2 = int(np.clip(lx2 + px - mx1, sx1 + 1, cw)), int(np.clip(ly2 + py - my1, sy1 + 1, ch))
        ri, rs, rox, roy = letterbox(crop[sy1:sy2, sx1:sx2], RD_W, RD_H, centre_x=False)
        i = len(X); X.append(ri)
        for d, chr_ in zip(digs, text):
            x1 = (d[1] - mx1 - sx1) * rs + rox; y1 = (d[2] - my1 - sy1) * rs + roy; x2 = (d[3] - mx1 - sx1) * rs + rox; y2 = (d[4] - my1 - sy1) * rs + roy
            B.append((i, int(chr_), x1, y1, x2, y2))
        B.append((i, CLS_LINE, (lx1 - mx1 - sx1) * rs + rox, (ly1 - my1 - sy1) * rs + roy, (lx2 - mx1 - sx1) * rs + rox, (ly2 - my1 - sy1) * rs + roy))
        keys.append(fn[:8]); by_type[t] = by_type.get(t, 0) + 1; reasons["ok"] += 1
        if len(review) < audit * 3:
            vis = crop.copy(); cv2.rectangle(vis, (int(lx1 - mx1), int(ly1 - my1)), (int(lx2 - mx1), int(ly2 - my1)), (0, 0, 255), max(2, cw // 200))
            vis = cv2.resize(vis, (300, int(300 * ch / cw)))[:300]; vis = np.vstack([vis, np.full((300 - vis.shape[0], 300, 3), 128, np.uint8)]) if vis.shape[0] < 300 else vis
            cv2.putText(vis, f"{t[:8]} {text}", (3, 16), 0, 0.5, (0, 255, 255), 2); review.append(vis)
    if not X:
        print("nothing", reasons); return
    X = np.stack(X); B = np.array(B, np.float32); LX = np.stack(LX); LB = np.array(LB, np.float32)
    uniq = sorted(set(keys)); rng = np.random.RandomState(0); rng.shuffle(uniq); val_keys = set(uniq[: max(1, int(0.15 * len(uniq)))])
    for name, pick in (("train", lambda k: k not in val_keys), ("val", lambda k: k in val_keys)):
        idx = [i for i, k in enumerate(keys) if pick(k)]; remap = {o: n for n, o in enumerate(idx)}
        Bi = np.array([(remap[int(b[0])], *b[1:]) for b in B if int(b[0]) in remap], np.float32).reshape(-1, 6)
        np.save(f"{out}_{name}_X.npy", X[idx]); np.save(f"{out}_{name}_B.npy", Bi)
        LBi = np.array([(remap[int(b[0])], *b[1:]) for b in LB if int(b[0]) in remap], np.float32).reshape(-1, 6)
        np.save(f"{out}_loc_{name}_X.npy", LX[idx]); np.save(f"{out}_loc_{name}_B.npy", LBi)
        print(name, X[idx].shape, len(Bi), "boxes; locator", LX[idx].shape)
    rep = {"reasons": reasons, "accepted": len(X), "by_type": by_type, "n_train_keys": len(uniq) - len(val_keys), "n_val_keys": len(val_keys), "min_score": MIN_SCORE}
    json.dump(rep, open(f"{out}_report.json", "w"), indent=1); print(json.dumps(rep))
    rng = np.random.RandomState(1); sel = [review[i] for i in rng.choice(len(review), min(audit, len(review)), replace=False)]
    rows = [np.hstack(sel[i:i + 5] + [np.full((300, 300, 3), 128, np.uint8)] * (5 - len(sel[i:i + 5]))) for i in range(0, len(sel), 5)]
    paths.ensure_dirs(); outimg = paths.REVIEW / f"meter_shards_{out.split('/')[-1]}.jpg"; cv2.imwrite(str(outimg), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 70]); print("audit sheet", outimg)


if __name__ == "__main__":
    main()
