"""Automatic labelling of ERP meter photos with a vision-language model (VLM) + 3-read consensus.

Used for slice 0 (labeller_0) when no browser was available (contract §4 fallback). It is NOT human labelling:
labels produced here must be documented as machine labels in STATUS.md, and a >=10% manual sample is required.

Pipeline (all intermediate files under data/erp/vlm/, NOT in git):
  python3 erp_vlm_label.py prep  <slice_list.txt>              # enhanced + full views for new local photos -> names.txt
  python3 erp_vlm_label.py read  <A|B|C> [workers=6]           # one independent VLM read per photo -> reads_<k>.jsonl
  python3 erp_vlm_label.py label <start> <end> <labeller>      # consensus of A,B,C -> data/erp/labels/<labeller>_NNN.csv
  python3 erp_vlm_label.py review <start> <end> [n=16] [seed]  # contact sheet of n random consensus numbers for a human
  python3 erp_vlm_label.py veto  <labeller_csv> <filename>...  # set reviewed-doubtful rows to X

The three reads are deliberately different so their errors are less correlated:
  A = enhanced view (erp_label.enhanced_view: upper 72%, CLAHE), short prompt
  B = full photo (long side 1100px), same short prompt
  C = enhanced view, prompt that first asks for the number of integer digit positions; a count/length mismatch -> X
Decision rule (per photo): A==B==C -> that value; >=2 reads say P -> P; otherwise X.
Then any numeric label whose length is not 5 or 6 -> X (fraction digits leaked in, or a digit was dropped).

Measured on slice 0 (2400 photos, 2026-10-18): 1236 numeric / 1112 X / 52 P. Manual review of ~220 consensus
numbers found ~20 doubtful (mostly partially-unlit Tomas LCD segments, e.g. consensus 000437 vs true 000497) ->
consensus labels are WEAK labels (training), not evaluation ground truth.
Requires the `gsk` CLI (gsk analyze) on PATH.
"""
import csv
import json
import random
import re
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

import erp_label as L

VLM = L.ERP / "vlm"
VIEWS = {"enh": VLM / "enh", "full": VLM / "full"}
NAMES = VLM / "names.txt"
LABELS_DIR = L.ERP / "labels"

PROMPT_SHORT = (
    "Each image is a photo of an electricity meter. For EACH image, read the main kWh register: write ONLY the large "
    "integer digits exactly as displayed, keeping leading zeros (e.g. 000718). NEVER include the small/decimal fraction "
    "digits (after the decimal point, or red/smaller drum digits). Answer X if the display is unreadable (dark, covered, "
    "full glare, heavy blur) or if you are not certain of EVERY single digit. Answer P if several meters are visible and "
    "it is unclear which one is the target. Reply with only the answer token, nothing else.")
PROMPT_COUNT = (
    "Electricity meter photo. Look ONLY at the main kWh register (big LCD digits or the black/white drum wheels). "
    "Step 1: count how many LARGE integer digit positions the register has (Tomas LCD meters have 6, including leading "
    "zeros which may be faint). Step 2: read each large digit left to right. Ignore small decimal digits after the point "
    "and red drum wheels. If any digit is uncertain, ghosted, covered or glared, the answer is X. If several meters and "
    "target unclear, P. Reply exactly in the form: COUNT=<n> READING=<digits or X or P>")
READS = {"A": ("enh", PROMPT_SHORT), "B": ("full", PROMPT_SHORT), "C": ("enh", PROMPT_COUNT)}
TIMEOUT_S = 120


def names():
    return [l.strip() for l in open(NAMES) if l.strip()] if NAMES.exists() else []


def prep(list_file):
    """Writes both views for every local, non-test, decodable photo of the list; appends new ones to names.txt
    in list order (names.txt order defines the 200-photo batches, so it is append-only)."""
    for d in VIEWS.values():
        d.mkdir(parents=True, exist_ok=True)
    cur = names()
    have = set(cur)
    add = []
    for f in (Path(l.strip()).name for l in open(list_file) if l.strip()):
        p = L.ERP / "photos" / f
        if f in have or not p.exists() or p.stat().st_size < 40_000 or L.is_test_photo(p):
            continue
        img = cv2.imread(str(p))
        if img is None:
            continue
        (VIEWS["enh"] / f).write_bytes(L.enhanced_view(img))
        h, w = img.shape[:2]
        s = min(1.0, 1100 / max(h, w))
        cv2.imwrite(str(VIEWS["full"] / f), cv2.resize(img, (int(w * s), int(h * s))), [cv2.IMWRITE_JPEG_QUALITY, 90])
        add.append(f)
    NAMES.write_text("\n".join(cur + add) + "\n")
    print(f"prep: +{len(add)} photos, {len(cur) + len(add)} total in {NAMES}")


def parse(kind, res):
    u = res.upper()
    if kind == "C":
        c = re.search(r"COUNT\s*=\s*(\d+)", u)
        m = re.search(r"READING\s*=\s*(\d+|X|P)", u)
        t = m.group(1) if m else "X"
        if t.isdigit() and (not c or int(c.group(1)) != len(t)):
            t = "X"
        return t
    m = re.findall(r"\b(\d{3,8}|X|P)\b", u)
    return m[-1] if m else "X"


def read_one(kind, f):
    view, prompt = READS[kind]
    err = ""
    for _ in range(3):
        try:
            r = subprocess.run(["gsk", "analyze", "-i", str(VIEWS[view] / f), "-r", prompt],
                               capture_output=True, text=True, timeout=TIMEOUT_S)
            res = json.loads(r.stdout)["data"]["results"][0]["result"].strip()
            return {"f": f, "raw": res, "t": parse(kind, res)}
        except subprocess.TimeoutExpired:
            err = "timeout"
        except Exception as e:  # malformed / failed response: retry
            err = str(e)[:200]
    return {"f": f, "raw": "ERR " + err, "t": None}


def load_reads(kind):
    p = VLM / f"reads_{kind}.jsonl"
    d = {}
    if p.exists():
        for l in open(p):
            r = json.loads(l)
            if r["t"] is not None:
                d[r["f"]] = r["t"]
    return d


def read(kind, workers=6):
    done = load_reads(kind)
    todo = [f for f in names() if f not in done]
    with ThreadPoolExecutor(workers) as ex, open(VLM / f"reads_{kind}.jsonl", "a") as fo:
        for d in ex.map(lambda f: read_one(kind, f), todo):
            fo.write(json.dumps(d, ensure_ascii=False) + "\n")
            fo.flush()
    print(f"read {kind}: {len(todo)} new")


def decide(a, b, c):
    v = [a, b, c]
    if a == b == c:
        t = a
    elif v.count("P") >= 2:
        t = "P"
    else:
        t = "X"
    if t.isdigit() and not 5 <= len(t) <= 6:
        t = "X"
    return t


def label(start, end, labeller):
    R = [load_reads(k) for k in "ABC"]
    batch = names()[start:end]
    missing = [f for f in batch if any(f not in r for r in R)]
    if missing:
        sys.exit(f"{len(missing)} photos still lack a read; run `read` first")
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    out = LABELS_DIR / f"{labeller}_{start // 200:03d}.csv"
    ts = int(time.time())
    rows = [(f, decide(*(r[f] for r in R))) for f in batch]
    with open(out, "w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["filename", "text", "labeller", "ts"])
        w.writerows([f, t, labeller, ts] for f, t in rows)
    print(out, len(rows), Counter("num" if t.isdigit() else t for _, t in rows))


def review(start, end, n=16, seed=7):
    R = [load_reads(k) for k in "ABC"]
    pool = [f for f in names()[start:end] if all(f in r for r in R) and decide(*(r[f] for r in R)).isdigit()]
    random.Random(seed).shuffle(pool)
    pick = pool[:n]
    tiles = []
    for i, f in enumerate(pick):
        im = cv2.resize(cv2.imread(str(VIEWS["enh"] / f)), (600, 570))
        cv2.putText(im, f"{i + 1}: {R[0][f]}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)
        tiles.append(im)
    while len(tiles) % 2:
        tiles.append(np.zeros_like(tiles[0]))
    for g in range(0, len(tiles), 8):
        page = tiles[g:g + 8]
        out = VLM / f"review_{start}_{end}_{g // 8}.jpg"
        cv2.imwrite(str(out), np.vstack([np.hstack(page[i:i + 2]) for i in range(0, len(page), 2)]),
                    [cv2.IMWRITE_JPEG_QUALITY, 80])
        print(out)
    json.dump(pick, open(VLM / f"review_{start}_{end}.json", "w"))


def veto(csv_path, files):
    rows = list(csv.reader(open(csv_path)))
    hit = 0
    for r in rows[1:]:
        if r[0] in files:
            r[1] = "X"
            hit += 1
    csv.writer(open(csv_path, "w", newline="")).writerows(rows)
    print(f"veto: {hit}/{len(files)} rows set to X in {csv_path}")


if __name__ == "__main__":
    cmd, a = sys.argv[1], sys.argv[2:]
    if cmd == "prep":
        prep(a[0])
    elif cmd == "read":
        read(a[0], int(a[1]) if len(a) > 1 else 6)
    elif cmd == "label":
        label(int(a[0]), int(a[1]), a[2])
    elif cmd == "review":
        review(int(a[0]), int(a[1]), int(a[2]) if len(a) > 2 else 16, int(a[3]) if len(a) > 3 else 7)
    elif cmd == "veto":
        veto(a[0], set(a[1:]))
    else:
        print(__doc__)
