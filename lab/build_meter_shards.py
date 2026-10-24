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
import csv, json, os, sys, hashlib, glob
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
    _poison = paths.BENCH_DATA / "erp" / "poisoned_m3_short_2026-10-24.json"
    poisoned = set(json.load(open(_poison))) if _poison.exists() else set()   # audited wrong-line short labels (S 2026-10-24)
    reasons = {"no_tl": 0, "no_meterbox": 0, "excluded": 0, "multi": 0, "low_score": 0, "short_unsafe": 0, "irregular": 0, "outside_meter": 0, "ok": 0}
    conf = {r["filename"]: r.get("confidence", "") for f in glob.glob(str(ef.LABELS / "labels_agentD.csv")) for r in csv.DictReader(open(f, encoding="utf-8"))}
    OWNER_W = 2.0   # agent D request 2026-10-21: owner_visual readings get higher sampling weight
    X, B, LX, LB, keys, by_type, review, SW, files_ok = [], [], [], [], [], {}, [], [], []
    for fn, res in sorted(tl.items()):
        text = labels.get(fn) or (res.get("text") if res and res.get("pseudo") else None)   # pseudo_label.py entries carry their own text
        if not res or not text:
            reasons["no_tl"] += 1; continue
        if fn not in boxes and res and res.get("fast"):
            # label_locate_fast.py result on a photo without an agent-D meter box: synthesise the "user rectangle" as a
            # randomised generous region around the located line (line width x 1.6..3.0, height x 4..9, clipped to photo)
            # -> the locator still sees a realistic meter-like framing. Deterministic per filename.
            _im = cv2.imread(str(ef.ERP / "photos" / fn)); _H, _W = _im.shape[:2]
            _r = np.random.RandomState(int(hashlib.md5(fn.encode()).hexdigest()[:8], 16))
            lx1, ly1, lx2, ly2 = res["line"]; lw, lh = lx2 - lx1, ly2 - ly1; cx, cy = (lx1 + lx2) / 2, (ly1 + ly2) / 2
            bw, bh = lw * _r.uniform(1.6, 3.0), lh * _r.uniform(4.0, 9.0)
            bx1 = np.clip(cx - bw * _r.uniform(0.35, 0.65), 0, _W); bx2 = np.clip(bx1 + bw, 0, _W)
            by1 = np.clip(cy - bh * _r.uniform(0.3, 0.7), 0, _H); by2 = np.clip(by1 + bh, 0, _H)
            boxes[fn] = [bx1 / _W, by1 / _H, bx2 / _W, by2 / _H]
        if fn not in boxes:
            reasons["no_meterbox"] += 1; continue
        p = ef.ERP / "photos" / fn
        if fn in poisoned:
            reasons["excluded"] += 1; continue
        if fn in ef.EXCLUDE_FILES or hashlib.sha256(open(p, "rb").read()).hexdigest() in ef.TEST_HASHES:
            reasons["excluded"] += 1; continue
        if fn in multi:
            reasons["multi"] += 1; continue
        human = bool(res.get("R")) or bool(res.get("pseudo"))   # R-verified box, or pseudo-label (already passed the dual-pair+TTA gate)
        t = types.get(fn, "?")
        if not human and res["score"] < MIN_SCORE:
            reasons["low_score"] += 1; continue
        if not human and len(text) < 5 and not (t in SHORT_OK and res["score"] >= 0.5):
            reasons["short_unsafe"] += 1; continue
        digs = sorted(res["digits"], key=lambda d: d[1])
        cx = np.array([(d[1] + d[3]) / 2 for d in digs]); hs = np.array([d[4] - d[2] for d in digs])
        if len(digs) >= 2 and not human:
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
        keys.append(fn.replace("pending-", "")[:8]); files_ok.append(fn); by_type[t] = by_type.get(t, 0) + 1; reasons["ok"] += 1
        SW.append(OWNER_W if conf.get(fn) == "owner_visual" else (float(os.environ.get("PSEUDO_W", "0.5")) if res.get("pseudo") else 1.0))
        if len(review) < audit * 3:
            vis = crop.copy(); cv2.rectangle(vis, (int(lx1 - mx1), int(ly1 - my1)), (int(lx2 - mx1), int(ly2 - my1)), (0, 0, 255), max(2, cw // 200))
            vis = cv2.resize(vis, (300, int(300 * ch / cw)))[:300]; vis = np.vstack([vis, np.full((300 - vis.shape[0], 300, 3), 128, np.uint8)]) if vis.shape[0] < 300 else vis
            cv2.putText(vis, f"{t[:8]} {text}", (3, 16), 0, 0.5, (0, 255, 255), 2); review.append(vis)
    if not X:
        print("nothing", reasons); return
    X = np.stack(X); B = np.array(B, np.float32); LX = np.stack(LX); LB = np.array(LB, np.float32)
    if os.environ.get("SPLIT", "key") == "phash":
        # photo-similarity split (training audit 2026-10-24): same meter under different filenames must not straddle
        # train/val. Union-find over 16x16 median-hash with hamming <= PHASH_T, then whole clusters go to val.
        T = int(os.environ.get("PHASH_T", "24")); hs = []
        for fn in files_ok:
            g = cv2.resize(cv2.cvtColor(cv2.imread(str(ef.ERP / "photos" / fn)), cv2.COLOR_BGR2GRAY), (16, 16), interpolation=cv2.INTER_AREA)
            hs.append((g > np.median(g)).flatten())
        par = list(range(len(hs)))
        def find(a):
            while par[a] != a: par[a] = par[par[a]]; a = par[a]
            return a
        for i in range(len(hs)):
            for j in range(i + 1, len(hs)):
                if int((hs[i] != hs[j]).sum()) <= T: par[find(i)] = find(j)
        keys = [f"c{find(i)}" for i in range(len(hs))]
        print("phash clusters:", len(set(keys)), "of", len(keys), "photos (T=%d)" % T)
    uniq = sorted(set(keys)); rng = np.random.RandomState(0); rng.shuffle(uniq); val_keys = set(uniq[: max(1, int(0.15 * len(uniq)))])
    if os.environ.get("FIXED_VAL"):
        # m5+ (2026-10-24): keep the val set IDENTICAL to a previous build (its <out>_keys.json "files" map) so clean65 /
        # val-m4 numbers stay comparable; every new photo (incl. pseudo-labels) goes to train. A new photo that falls in
        # the pHash cluster of a fixed-val photo is DROPPED from train (leak guard).
        fv = json.load(open(os.environ["FIXED_VAL"]))["files"]; val_files = {f for f, s_ in fv.items() if s_ == "val"}
        val_keys = {k for fn, k in zip(files_ok, keys) if fn in val_files}
        drop = [i for i, (fn, k) in enumerate(zip(files_ok, keys)) if k in val_keys and fn not in val_files]
        print(f"FIXED_VAL: {len(val_files)} val files kept, {len(drop)} new photos dropped (cluster of a val photo), pseudo in val = 0")
        keep = [i for i in range(len(keys)) if i not in set(drop)]
        X, LX = X[keep], LX[keep]; remap_k = {o: n for n, o in enumerate(keep)}
        B = np.array([(remap_k[int(b[0])], *b[1:]) for b in B if int(b[0]) in remap_k], np.float32).reshape(-1, 6)
        LB = np.array([(remap_k[int(b[0])], *b[1:]) for b in LB if int(b[0]) in remap_k], np.float32).reshape(-1, 6)
        keys = [keys[i] for i in keep]; files_ok = [files_ok[i] for i in keep]; SW = [SW[i] for i in keep]; uniq = sorted(set(keys))
    for name, pick in (("train", lambda k: k not in val_keys), ("val", lambda k: k in val_keys)):
        idx = [i for i, k in enumerate(keys) if pick(k)]; remap = {o: n for n, o in enumerate(idx)}
        Bi = np.array([(remap[int(b[0])], *b[1:]) for b in B if int(b[0]) in remap], np.float32).reshape(-1, 6)
        np.save(f"{out}_{name}_X.npy", X[idx]); np.save(f"{out}_{name}_B.npy", Bi)
        np.save(f"{out}_{name}_W.npy", np.array([SW[i] for i in idx], np.float32)); np.save(f"{out}_loc_{name}_W.npy", np.array([SW[i] for i in idx], np.float32))
        LBi = np.array([(remap[int(b[0])], *b[1:]) for b in LB if int(b[0]) in remap], np.float32).reshape(-1, 6)
        np.save(f"{out}_loc_{name}_X.npy", LX[idx]); np.save(f"{out}_loc_{name}_B.npy", LBi)
        print(name, X[idx].shape, len(Bi), "boxes; locator", LX[idx].shape)
    # photo-level split record (dev-set construction / leakage checks): which files landed in train vs val
    json.dump({"train_keys": sorted(k for k in uniq if k not in val_keys), "val_keys": sorted(val_keys),
               "files": {fn: ("val" if k in val_keys else "train") for fn, k in zip(files_ok, keys)}}, open(f"{out}_keys.json", "w"), indent=0)
    rep = {"reasons": reasons, "accepted": len(X), "by_type": by_type, "owner_visual": int(sum(1 for w in SW if w > 1)), "owner_w": OWNER_W, "n_train_keys": len(uniq) - len(val_keys), "n_val_keys": len(val_keys), "min_score": MIN_SCORE}
    json.dump(rep, open(f"{out}_report.json", "w"), indent=1); print(json.dumps(rep))
    rng = np.random.RandomState(1); sel = [review[i] for i in rng.choice(len(review), min(audit, len(review)), replace=False)]
    rows = [np.hstack(sel[i:i + 5] + [np.full((300, 300, 3), 128, np.uint8)] * (5 - len(sel[i:i + 5]))) for i in range(0, len(sel), 5)]
    paths.ensure_dirs(); outimg = paths.REVIEW / f"meter_shards_{out.split('/')[-1]}.jpg"; cv2.imwrite(str(outimg), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 70]); print("audit sheet", outimg)


if __name__ == "__main__":
    main()
