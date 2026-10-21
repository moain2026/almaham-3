"""Text-supervised localisation: find WHERE the human-verified reading is in a whole photo, without any box label.

Why: erp_finetune.build only accepts a photo when the CURRENT locator already finds the line. So the locator's
training set contains only photos the locator already handles -> it never learns the photos it fails on (Crystal,
Emeter, whole-LCD boxes, labels/barcodes mistaken for the line). Self-training trap, measured 2026-10-21:
testset_human 19 failures, ~11 of them locator (5 no box, ~6 box on label/barcode/fraction).

How: slide windows of line aspect (~3.5:1) over the upright photo at several scales, run the READER on each
window (64x448 letterbox, same as the app), assemble, and accept the window whose integer text equals the human
label (exact) — with the lattice-window relaxation of erp_finetune for same-height fractions. Among matching
windows take the one with the highest min digit score; its digit boxes mapped back to the photo give a tight
LINE box. Output: JSON {filename: {"line": [x1,y1,x2,y2] photo px, "score":..., "digits": [[cls,x1,y1,x2,y2],...]}}

Usage: python3 text_locate.py <reader.pt> <out.json> [--only-unaccepted <ft_prefix>] [--limit N]
Evaluation photos (49 + testset_human + siblings) are skipped (same exclusion as erp_finetune).
"""
import csv, hashlib, json, sys, time
import cv2
import numpy as np
import torch
import paths, assemble
import erp_finetune as ef
from det_model import DigitNet, decode, READER_CLASSES
from eval_e2e import RD_W, RD_H, RD_PEAK_MIN, letterbox

ASPECT = RD_W / RD_H                 # 7:1 reader canvas; windows use a 3.5:1 content box letterboxed into it
SCALES = (0.22, 0.32, 0.46, 0.66)   # window width as fraction of photo width (coarse; refined by a 2nd pass)
STRIDE = 0.5                         # of window size
WIN_ASPECT = 3.6


def windows(W, H):
    for s in SCALES:
        ww = int(W * s); wh = int(ww / WIN_ASPECT)
        if wh < 24 or wh > H:
            continue
        sx = max(8, int(ww * STRIDE)); sy = max(8, int(wh * STRIDE))
        for y in range(0, max(1, H - wh + 1), sy):
            for x in range(0, max(1, W - ww + 1), sx):
                yield x, y, min(W, x + ww), min(H, y + wh)


def match(r, dets, text):
    """exact assembled match, else lattice-window match (same rule as erp_finetune alignment)."""
    if r.text == text:
        return [d for d in r.digits], 1.0
    al = sorted([assemble.Digit(int(c), float(s), x1, y1, x2, y2) for c, s, x1, y1, x2, y2 in dets if c < 10], key=lambda d: d.cx)
    M, N = len(al), len(text)
    if M > N and M - N <= 6:
        raw = "".join(str(d.cls) for d in al)
        for k in range(0, min(4, M - N + 1)):
            wd = al[k:k + N]
            if raw[k:k + N] != text:
                continue
            cxs = np.array([d.cx for d in wd]); gaps = np.diff(cxs); hs = np.array([d.h for d in wd])
            if N == 1 or (gaps.max() / max(gaps.min(), 1e-6) <= ef.LATTICE_MAX_RATIO and hs.min() / hs.max() >= 0.75):
                if hs.mean() >= 0.40 * RD_H and (M - k - N) <= 4:
                    return wd, 0.8
    return None, 0.0


def _eval_win(rd, im, text, x1, y1, x2, y2):
    crop = im[y1:y2, x1:x2]
    if crop.size == 0:
        return None
    ri, s, ox, oy = letterbox(crop, RD_W, RD_H, centre_x=False)
    dets = decode(*ef.run_net(rd, ri), RD_PEAK_MIN)
    if sum(1 for d in dets if d[0] < 10) < len(text):
        return None
    r = assemble.assemble(dets, RD_W, RD_H)
    digs, q = match(r, dets, text)
    if not digs:
        return None
    conf = q * min(d.score for d in digs)
    bx = [[d.cls, x1 + (d.x1 - ox) / s, y1 + (d.y1 - oy) / s, x1 + (d.x2 - ox) / s, y1 + (d.y2 - oy) / s] for d in digs]
    return conf, bx


def locate(rd, im, text):
    H, W = im.shape[:2]
    best = None
    for x1, y1, x2, y2 in windows(W, H):
        got = _eval_win(rd, im, text, x1, y1, x2, y2)
        if got and (best is None or got[0] > best[0]):
            best = got
    if best is not None:
        # refine: re-crop tightly around the found digits with padding (like the app's PAD), a few jitters
        arr = np.array([b[1:] for b in best[1]]); bw, bh = arr[:, 2].max() - arr[:, 0].min(), arr[:, 3].max() - arr[:, 1].min()
        cx, cy = (arr[:, 0].min() + arr[:, 2].max()) / 2, (arr[:, 1].min() + arr[:, 3].max()) / 2
        for px, py in ((0.18, 0.45), (0.35, 0.7), (0.6, 1.0), (0.18, 0.9)):
            w2, h2 = bw * (1 + 2 * px), bh * (1 + 2 * py)
            x1, x2 = int(max(0, cx - w2 / 2)), int(min(W, cx + w2 / 2)); y1, y2 = int(max(0, cy - h2 / 2)), int(min(H, cy + h2 / 2))
            got = _eval_win(rd, im, text, x1, y1, x2, y2)
            if got and got[0] > best[0]:
                best = got
    if False:
        pass
    if best is None:
        return None
    conf, bx = best
    arr = np.array([b[1:] for b in bx])
    return {"line": [float(arr[:, 0].min()), float(arr[:, 1].min()), float(arr[:, 2].max()), float(arr[:, 3].max())],
            "score": round(float(conf), 3), "digits": [[int(b[0])] + [round(float(v), 1) for v in b[1:]] for b in bx]}


def main():
    rd_ckpt, out = sys.argv[1], sys.argv[2]
    only_un = sys.argv[sys.argv.index("--only-unaccepted") + 1] if "--only-unaccepted" in sys.argv else None
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10**9
    torch.set_num_threads(int(__import__("os").environ.get("TORCH_THREADS", "3")))
    rd = DigitNet(READER_CLASSES); rd.load_state_dict(torch.load(rd_ckpt, map_location="cpu")); rd.eval()
    labels = ef.load_labels()
    accepted = set()
    if only_un:
        # photos already accepted by build are listed nowhere; recompute quickly via the report keys is not stored ->
        # we re-run the acceptance test cheaply: skip photos where locator top box + reader already match (done inside build).
        pass
    done = json.load(open(out)) if __import__("os").path.exists(out) else {}
    t0 = time.time(); n = 0; found = 0
    for fn, text in sorted(labels.items()):
        if fn in done or n >= limit:
            continue
        p = ef.ERP / "photos" / fn
        if not p.exists() or fn in ef.EXCLUDE_FILES or hashlib.sha256(open(p, "rb").read()).hexdigest() in ef.TEST_HASHES:
            continue
        im = cv2.imread(str(p))
        if im is None:
            continue
        # work at <=1600px on the long side for speed; boxes are mapped back
        H, W = im.shape[:2]; k = min(1.0, 1600 / max(H, W))
        small = cv2.resize(im, None, fx=k, fy=k, interpolation=cv2.INTER_AREA) if k < 1 else im
        res = locate(rd, small, text)
        if res:
            res["line"] = [v / k for v in res["line"]]; res["digits"] = [[d[0]] + [v / k for v in d[1:]] for d in res["digits"]]
            found += 1
        done[fn] = res or {}
        n += 1
        if n % 20 == 0:
            json.dump(done, open(out, "w")); print(f"{n} photos, {found} located, {(time.time() - t0) / n:.1f}s/photo", flush=True)
    json.dump(done, open(out, "w"))
    print(f"done {n} photos, {found} located ({100 * found / max(1, n):.0f}%)")


if __name__ == "__main__":
    main()
