"""Evaluate lab/forensic_reader.py on the 46 readable photos (line_boxes.json crops). Contract §2 honesty check.

Usage: python3 eval_forensic_reader.py   -> benchmark/results/engines/forensic_reader_lineL.json
"""
import json

import cv2

import forensic_reader as fr
import gt
import paths
from eval_sevenseg import DEV


def main():
    lines = json.load(open(paths.LINE_BOXES))
    rows = []
    for it in gt.load():
        if not it.readable:
            continue
        im = cv2.imread(gt.PHOTOS + it.name)
        H, W = im.shape[:2]
        x1, y1, x2, y2 = lines[it.name]
        r = fr.read_line(im[int(y1 * H):int(y2 * H), int(x1 * W):int(x2 * W)])
        value = str(int(r["text"])) if r["text"] else ""
        truth6 = it.reading.zfill(len(r["text"])) if r["text"] else ""
        digit_ok = [len(truth6) == len(r["text"]) and truth6[i] == str(d["cls"]) for i, d in enumerate(r["digits"])]
        rows.append({"file": it.name, "truth": it.reading, "text": r["text"], "value": value,
                     "ok": value == it.reading, "status": r["status"], "ms": r["ms"], "dev": it.name[:5] in DEV,
                     "digits": [dict(d, ok=o) for d, o in zip(r["digits"], digit_ok)]})
    hi = [d for x in rows for d in x["digits"] if d["conf"] >= 0.8]
    hi_ok = sum(d["ok"] for d in hi)
    ok_status = [x for x in rows if x["status"] == "OK"]
    summary = {
        "exact": sum(x["ok"] for x in rows), "n": len(rows),
        "exact_dev": sum(x["ok"] for x in rows if x["dev"]), "exact_holdout": sum(x["ok"] for x in rows if not x["dev"]),
        "digits_conf_ge_0.8": len(hi), "digits_conf_ge_0.8_correct": hi_ok,
        "precision_conf_ge_0.8": round(hi_ok / len(hi), 4) if hi else None,
        "precision_conf_ge_0.8_holdout": (lambda h: round(sum(d["ok"] for d in h) / len(h), 4) if h else None)(
            [d for x in rows if not x["dev"] for d in x["digits"] if d["conf"] >= 0.8]),
        "calibration_note": "confidence rule chosen on these same 46 photos (in-sample); must be re-checked on ERP photos",
        "status_OK": len(ok_status), "status_OK_correct": sum(x["ok"] for x in ok_status),
        "empty": sum(1 for x in rows if not x["text"]),
        "ms_p50": sorted(x["ms"] for x in rows)[len(rows) // 2], "hardware": "sandbox x86 4-core, python/numpy",
    }
    print(json.dumps(summary, ensure_ascii=False))
    paths.ensure_dirs()
    json.dump({"summary": summary, "rows": rows}, open(paths.RESULTS_ENGINES / "forensic_reader_lineL.json", "w"),
              ensure_ascii=False, indent=0)
    for x in rows:
        flag = "OK " if x["ok"] else "   "
        print(flag, x["file"][:5], x["truth"], x["text"], x["status"], [(d["cls"], d["conf"]) for d in x["digits"]])


if __name__ == "__main__":
    main()
