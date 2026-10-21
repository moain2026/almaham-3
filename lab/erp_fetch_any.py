"""Fetch a deterministic batch of ERP meter photos that have NO previous label (agent D, for meter-type diversity).

Same pattern as erp_fetch_batch.py: direct URL, credentials ONLY from env ERP_USER/ERP_PASS, seed 7 order,
skips files already present in OUT and any file that appears in benchmark/data/erp/labels*.csv.
Usage: ERP_USER=… ERP_PASS=… python3 erp_fetch_any.py <n> [--par 10] [--out DIR] [--list-out FILE]
Appends to OUT/../manifests/fetched_any.csv (filename,server_path). --list-out writes the names fetched in this run.
"""
import csv, glob, json, os, random, subprocess, sys
from pathlib import Path
import paths

BASE = "https://photos.alabasi.uk/"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
arg = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
out = Path(arg("--out", paths.DATA / "erp" / "photos"))
par = int(arg("--par", 10))
out.mkdir(parents=True, exist_ok=True)
labelled = set()
for f in sorted(glob.glob(str(paths.BENCH_DATA / "erp" / "labels*.csv"))):
    for r in csv.DictReader(open(f, encoding="utf-8")):
        labelled.add(r["filename"])
where = {}
for c in ("Mabar", "Hodeidah"):
    for x in json.load(open(paths.DATA / "erp" / "manifests" / f"{c}-files.json")):
        if "/meter-readings/" in x["path"] and x["path"].endswith(".jpg"):
            where[x["path"].rsplit("/", 1)[-1]] = x["path"]
cand = sorted(fn for fn in where if fn not in labelled)
random.Random(7).shuffle(cand)
cand = [fn for fn in cand if not (out / fn).exists()]
batch = cand[:n]
auth = f"{os.environ['ERP_USER']}:{os.environ['ERP_PASS']}"
lst = out.parent / "manifests" / "_batch_any.txt"
lst.write_text("".join(f"{fn}\t{where[fn]}\n" for fn in batch))
subprocess.run(f"cat {lst} | xargs -P {par} -L 1 sh -c 'curl -s -f --max-time 300 -u \"$0\" -o \"{out}/$1\" \"{BASE}$2\"' \"{auth}\"", shell=True)
for fn in batch:  # drop truncated downloads so they are retried next time
    p = out / fn
    if p.exists() and (p.stat().st_size <= 20_000 or b"\xff\xd9" not in open(p, "rb").read()[-2048:]):
        p.unlink()
got = [fn for fn in batch if (out / fn).exists()]
man = out.parent / "manifests" / "fetched_any.csv"
new = not man.exists()
with open(man, "a", newline="") as f:
    w = csv.writer(f, lineterminator="\n")
    if new:
        w.writerow(["filename", "server_path"])
    for fn in got:
        w.writerow([fn, where[fn]])
if "--list-out" in sys.argv:
    Path(arg("--list-out", "")).write_text("".join(fn + "\n" for fn in got))
print(f"fetched {len(got)}/{len(batch)} unlabelled photos -> {out} | remaining unlabelled: {len(cand) - len(got)}")
