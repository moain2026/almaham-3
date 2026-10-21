"""Agent D — cheap meter-TYPE-only pass (1 VLM call per photo on a 900 px thumbnail) to select diverse batches.

Usage: python3 classify_types.py <list.txt> <out.csv>      (appends; resumable)  -> filename,type
The type here is only for SELECTION; the final meter_type is confirmed by L4 + my own look in the batch.
"""
import csv
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2

REPO = Path(__file__).resolve().parents[4]
PH = REPO / "data" / "erp" / "photos"
TYPES = ["TOMAS_STATIC", "TOMAS_SMART", "SMART_MT10", "CRYSTAL", "EMETER_GREEN", "TAGADOD", "HPL", "OTHER", "NONE"]
P = ("Classify the electricity meter in this photo. Answer with exactly one label:\n"
     "TOMAS_STATIC = Tomas 'Single Phase Static kWh Meter', small 8-digit LCD;\n"
     "TOMAS_SMART = Tomas 'Single Phase Bi-Directional Smart Meter', big 6+2 digit LCD;\n"
     "SMART_MT10 = yellow front 'SMART MT10-ALPHA' (DMC);\n"
     "CRYSTAL = brand 'CRYSTAL', LCD with a second smaller line;\n"
     "EMETER_GREEN = green circuit board visible behind a clear cover (Emeter);\n"
     "TAGADOD = brand 'TAGADOD', blue backlit LCD, '100000 10000 1000 100 10 1 0.1' scale above;\n"
     "HPL = brand 'HPL' (often three-phase);\n"
     "OTHER = any other meter (Kenwell, Veto, drum counter, ...);\n"
     "NONE = no meter display visible.\nAnswer only the label.")


def job(n, tmp):
    img = cv2.imread(str(PH / n))
    if img is None:
        return [n, "BADIMG"]
    s = 900 / max(img.shape[:2])
    f = tmp / n
    cv2.imwrite(str(f), cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    for _ in range(3):
        try:
            r = subprocess.run(["gsk", "understand_images", "-r", P, "-i", str(f)], capture_output=True, text=True, timeout=120)
            t = json.loads(r.stdout)["data"]["results"][0]["result"].upper()
            m = [x for x in TYPES if re.search(r"\b" + x + r"\b", t)]
            return [n, m[0] if m else "OTHER"]
        except Exception:
            pass
    return [n, "ERR"]


names = [Path(x.strip()).name for x in open(sys.argv[1]) if x.strip()]
out = Path(sys.argv[2])
tmp = Path("/tmp/agD/typethumb")
tmp.mkdir(parents=True, exist_ok=True)
done = {r[0] for r in csv.reader(open(out))} if out.exists() else set()
todo = [n for n in names if n not in done and (PH / n).exists()]
with ThreadPoolExecutor(16) as ex, open(out, "a", newline="") as fo:
    w = csv.writer(fo, lineterminator="\n")
    for res in ex.map(lambda n: job(n, tmp), todo):
        w.writerow(res)
        fo.flush()
print(f"typed {len(todo)} -> {out}")
