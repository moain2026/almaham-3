"""Agent D — merge the 4 VLM layers + my own visual reading (layer 5) into labels_agentD.csv and raw_layers_agentD.csv.

Usage: python3 finalize_batch.py <work_dir> <batch_tag>
  work_dir/layers.csv      : filename,L1,L2,L3,L4,type          (vlm_layers.py)
  work_dir/review/index.csv: k,filename                         (review_sheet.py)
  work_dir/mine.csv        : k,mine[,type]  my reading (digits / X / P / ?) and optional type override
Rule: digits accepted ONLY if L1==L2==L3==L4==mine (literally). Otherwise X (P if all five say P).
Type: my override if given, else L4's TYPE.
Appends to benchmark/data/erp/labels_agentD.csv and ../almaham-3-private-data/erp/manifests/raw_layers_agentD.csv (dedup by filename).
"""
import csv
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PRIV = REPO.parent / "almaham-3-private-data"
OUT = REPO / "benchmark" / "data" / "erp" / "labels_agentD.csv"
RAW = PRIV / "erp" / "manifests" / "raw_layers_agentD.csv"
TEST = {ln.split()[1] for ln in open(REPO / "benchmark" / "data" / "photos.sha256") if ln.strip()}

work, tag = Path(sys.argv[1]), sys.argv[2]
L = {r["filename"]: r for r in csv.DictReader(open(work / "layers.csv"))}
idx = {r["k"]: r["filename"] for r in csv.DictReader(open(work / "review" / "index.csv"))}
mine = {}
for r in csv.DictReader(open(work / "mine.csv")):
    mine[idx[r["k"]]] = (r["mine"].strip().upper(), (r.get("type") or "").strip())
ts = int(time.time())


def load(p, key="filename"):
    return {r[key]: r for r in csv.DictReader(open(p, encoding="utf-8"))} if p.exists() else {}


old = load(OUT)
oldraw = load(RAW)
new = raw = 0
for fn, r in L.items():
    if fn in TEST or r["L1"] in ("SKIP_TEST", "BADIMG") or fn not in mine:
        continue
    m, ty = mine[fn]
    ty = ty or r["type"]
    v = [r["L1"], r["L2"], r["L3"], r["L4"], m]
    if len(set(v)) == 1 and m.isdigit():
        text, conf = m, "4/4"
    elif len(set(v)) == 1 and m == "P":
        text, conf = "P", "P"
    else:
        text, conf = "X", "X"
    if fn not in old:
        new += 1
    old[fn] = {"filename": fn, "text": text, "labeller": "agentD", "ts": ts, "n_labels": 5, "meter_type": ty, "confidence": conf}
    oldraw[fn] = {"filename": fn, "batch": tag, "L1_enh": r["L1"], "L2_enh_strict": r["L2"], "L3_alt_careful": r["L3"],
                  "L4_orig_digitwise": r["L4"], "L4_type": r["type"], "L5_agentD_eye": m, "meter_type": ty, "final": text}
    raw += 1
cols = ["filename", "text", "labeller", "ts", "n_labels", "meter_type", "confidence"]
with open(OUT, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, cols, lineterminator="\n")
    w.writeheader()
    for k in sorted(old):
        w.writerow(old[k])
RAW.parent.mkdir(parents=True, exist_ok=True)
rc = ["filename", "batch", "L1_enh", "L2_enh_strict", "L3_alt_careful", "L4_orig_digitwise", "L4_type", "L5_agentD_eye", "meter_type", "final"]
with open(RAW, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, rc, lineterminator="\n")
    w.writeheader()
    for k in sorted(oldraw):
        w.writerow(oldraw[k])
# summary
from collections import Counter
acc = Counter(r["meter_type"] for r in old.values() if r["text"].isdigit())
xs = sum(1 for r in old.values() if r["text"] == "X")
ps = sum(1 for r in old.values() if r["text"] == "P")
print(f"batch {tag}: {raw} rows ({new} new) | total {len(old)} | accepted {sum(acc.values())} X {xs} P {ps} | by type {dict(sorted(acc.items()))}")
