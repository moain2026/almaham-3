"""Fetch a deterministic slice of the ERP meter photos (photos.alabasi.uk) for labelling/training. Never in git.

Usage: ERP_USER=... ERP_PASS=... python3 erp_fetch.py <slice_index> <slice_count> [n_per_slice]
Every agent takes a different slice_index (0..slice_count-1) of the SAME shuffled list (seed 7), so slices never
overlap. Files land in data/erp/photos/. The manifest comes from Packages/{Mabar,Hodeidah}-files.json.
"""
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import paths

BASE = "https://photos.alabasi.uk/"
OUT = paths.DATA / "erp"
MIN_BYTES, MAX_BYTES = 40_000, 2_500_000


def manifest():
    cache = OUT / "all_meter_photos.json"
    if cache.exists():
        return json.load(open(cache))
    auth = f"{os.environ['ERP_USER']}:{os.environ['ERP_PASS']}"
    rows = []
    for city in ("Mabar", "Hodeidah"):
        raw = subprocess.run(["curl", "-s", "-u", auth, f"{BASE}Packages/{city}-files.json"], capture_output=True, check=True).stdout
        d = json.loads(raw)
        mr = [x for x in d if "/meter-readings/" in x["path"] and x["path"].endswith(".jpg") and MIN_BYTES < x["size"] < MAX_BYTES]
        random.Random(7).shuffle(mr)
        rows += [(city, x["path"], x["size"], x["package"]) for x in mr]
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(rows, open(cache, "w"))
    return rows


def main(idx, count, n):
    rows = manifest()
    mine = rows[idx::count][:n]
    (OUT / "photos").mkdir(parents=True, exist_ok=True)
    lst = OUT / f"slice_{idx}_of_{count}.txt"
    lst.write_text("\n".join(r[1] for r in mine) + "\n")
    auth = f"{os.environ['ERP_USER']}:{os.environ['ERP_PASS']}"
    cmd = (f"cat {lst} | xargs -P 6 -I{{}} sh -c 'f=$(basename {{}}); [ -s {OUT}/photos/$f ] || "
           f"curl -s -u {auth} -o {OUT}/photos/$f {BASE}{{}}'")
    subprocess.run(cmd, shell=True, check=True)
    have = sum(1 for r in mine if (OUT / "photos" / Path(r[1]).name).exists())
    print(f"slice {idx}/{count}: {have}/{len(mine)} photos in {OUT / 'photos'}")


if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 1000)
