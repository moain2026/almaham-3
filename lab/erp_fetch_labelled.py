"""Download exactly the ERP photos that have a readable label in benchmark/data/erp/labels_*.csv (any slice, any agent).
Usage: ERP_USER=... ERP_PASS=... python3 erp_fetch_labelled.py
Photos go to data/erp/photos/ (git-ignored). Idempotent: skips files already present and non-empty."""
import csv, glob, json, os, subprocess
from pathlib import Path
from erp_fetch import manifest, OUT, BASE

def main():
    want = set()
    for f in glob.glob(str(Path(__file__).resolve().parents[1] / "benchmark/data/erp/labels_*.csv")):
        for r in csv.DictReader(open(f)):
            if r["text"] not in ("X", "P") and "?" not in r["text"]:
                want.add(r["filename"])
    rows = manifest()
    paths = [r[1] for r in rows if Path(r[1]).name in want]
    missing = [p for p in paths if not (OUT / "photos" / Path(p).name).exists()]
    print(f"labelled readable {len(want)}, in manifest {len(paths)}, missing locally {len(missing)}", flush=True)
    lst = OUT / "labelled_missing.txt"
    lst.write_text("\n".join(missing) + "\n")
    auth = f"{os.environ['ERP_USER']}:{os.environ['ERP_PASS']}"
    cmd = (f"cat {lst} | xargs -P 8 -I{{}} sh -c 'f=$(basename {{}}); [ -s {OUT}/photos/$f ] || "
           f"curl -s -u {auth} -o {OUT}/photos/$f {BASE}{{}}'")
    subprocess.run(cmd, shell=True, check=True)
    have = sum(1 for p in paths if (OUT / "photos" / Path(p).name).exists())
    print(f"done: {have}/{len(paths)} labelled photos local", flush=True)

if __name__ == "__main__":
    main()
