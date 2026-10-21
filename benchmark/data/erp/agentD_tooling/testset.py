"""Agent D — frozen human test set (benchmark/data/erp/testset_human.csv + testset_human.sha256).

  python3 testset.py add <cand.csv> <batch>          cand.csv: filename,reading,meter_type[,difficulty]  -> rows with notes 'review1:<batch>'
  python3 testset.py review2 <r2.csv> <batch>         r2.csv: filename,reading (my blind 2nd reading, later session, different crop)
        match   -> notes 'frozen:<r1>+<batch>'  (sha256 written)
        mismatch-> row REMOVED from the test set and reported (the photo also must not stay as a trusted training label)
Columns (spec): filename,reading,meter_type,difficulty,notes.  Only 'frozen:*' rows are final; sha256 file lists frozen rows only.
"""
import csv
import hashlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
TS = REPO / "benchmark" / "data" / "erp" / "testset_human.csv"
SH = REPO / "benchmark" / "data" / "erp" / "testset_human.sha256"
PH = REPO / "data" / "erp" / "photos"
TEST49 = {ln.split()[0] for ln in open(REPO / "benchmark" / "data" / "photos.sha256") if ln.strip()}
COLS = ["filename", "reading", "meter_type", "difficulty", "notes"]


def load():
    return {r["filename"]: r for r in csv.DictReader(open(TS, encoding="utf-8"))} if TS.exists() else {}


def save(rows):
    with open(TS, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, COLS, lineterminator="\n")
        w.writeheader()
        for k in sorted(rows):
            w.writerow(rows[k])
    fz = [k for k in sorted(rows) if rows[k]["notes"].startswith("frozen:")]
    with open(SH, "w") as f:
        for k in fz:
            f.write(f"{hashlib.sha256(open(PH / k, 'rb').read()).hexdigest()}  {k}\n")
    from collections import Counter
    c = Counter(rows[k]["meter_type"] for k in fz)
    print(f"testset: frozen {len(fz)} {dict(sorted(c.items()))} | review1 pending {len(rows) - len(fz)}")


cmd, src, batch = sys.argv[1], sys.argv[2], sys.argv[3]
rows = load()
if cmd == "add":
    for r in csv.DictReader(open(src)):
        fn = r["filename"]
        if fn in rows or hashlib.sha256(open(PH / fn, "rb").read()).hexdigest() in TEST49:
            continue
        rows[fn] = {"filename": fn, "reading": r["reading"], "meter_type": r["meter_type"],
                    "difficulty": r.get("difficulty") or "clear", "notes": f"review1:{batch}"}
elif cmd == "review2":
    bad = []
    for r in csv.DictReader(open(src)):
        fn = r["filename"]
        if fn not in rows or not rows[fn]["notes"].startswith("review1:"):
            continue
        if r["reading"].strip() == rows[fn]["reading"]:
            rows[fn]["notes"] = f"frozen:{rows[fn]['notes'].split(':', 1)[1]}+{batch}"
        else:
            bad.append((fn, rows[fn]["reading"], r["reading"]))
            del rows[fn]
    print(f"review2 mismatches: {len(bad)} {bad}")
save(rows)
