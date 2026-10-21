"""Fetch a SMALL, deterministic batch of ERP photos that already have a readable label (digits), by direct URL —
no 250 MB packages. Credentials ONLY from env ERP_USER/ERP_PASS (never written anywhere).

Usage: ERP_USER=… ERP_PASS=… python3 erp_fetch_batch.py <n> [--type-balanced] [--out DIR]
  * reads benchmark/data/erp/labels*.csv  -> filename -> text (digits only; X/P skipped)
  * reads data/erp/manifests/{Mabar,Hodeidah}-files.json -> filename -> server path
  * skips files already present in OUT (default: data/erp/photos, i.e. the private repo link)
  * deterministic order (seed 7) so every agent/run gets the same next batch; writes OUT/../manifests/fetched.csv
"""
import csv, glob, json, os, random, subprocess, sys
from pathlib import Path
import paths

BASE = "https://photos.alabasi.uk/"
n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else paths.DATA / "erp" / "photos"
out.mkdir(parents=True, exist_ok=True)
labels = {}
for f in sorted(glob.glob(str(paths.BENCH_DATA / "erp" / "labels*.csv"))):
    for r in csv.DictReader(open(f, encoding="utf-8")):
        if r["text"].strip().isdigit():
            labels[r["filename"]] = r["text"].strip()
where = {}
for c in ("Mabar", "Hodeidah"):
    for x in json.load(open(paths.DATA / "erp" / "manifests" / f"{c}-files.json")):
        if "/meter-readings/" in x["path"] and x["path"].endswith(".jpg"):
            where[x["path"].rsplit("/", 1)[-1]] = x["path"]
cand = sorted(fn for fn in labels if fn in where and not (out / fn).exists())
random.Random(7).shuffle(cand)
batch = cand[:n]
auth = f"{os.environ['ERP_USER']}:{os.environ['ERP_PASS']}"
# server is slow (~30 KB/s per connection) -> 6 parallel curls
lst = out.parent / "manifests" / "_batch.txt"
lst.parent.mkdir(exist_ok=True)
lst.write_text("".join(f"{fn}\t{where[fn]}\n" for fn in batch))
subprocess.run(f"cat {lst} | xargs -P 6 -L 1 sh -c 'curl -s -f -u \"$0\" -o \"{out}/$1\" \"{BASE}$2\"' \"{auth}\"", shell=True)
ok = sum(1 for fn in batch if (out / fn).exists() and (out / fn).stat().st_size > 20_000)
for fn in batch:  # drop truncated downloads so they are retried next time
    if (out / fn).exists() and (out / fn).stat().st_size <= 20_000:
        (out / fn).unlink()
man = out.parent / "manifests" / "fetched.csv"
man.parent.mkdir(exist_ok=True)
new = not man.exists()
with open(man, "a", newline="") as f:
    w = csv.writer(f)
    if new:
        w.writerow(["filename", "text", "server_path"])
    for fn in batch:
        if (out / fn).exists():
            w.writerow([fn, labels[fn], where[fn]])
print(f"fetched {ok}/{len(batch)} labelled photos -> {out} | total local labelled: {sum(1 for fn in labels if (out/fn).exists())} | remaining: {len(cand)-len(batch)}")
