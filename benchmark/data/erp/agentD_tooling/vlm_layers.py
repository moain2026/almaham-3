"""Agent D — 4 independent VLM readings per photo (gsk understand_images), different inputs/prompts.

Usage (from repo root, venv active):  python3 benchmark/data/erp/agentD_tooling/vlm_layers.py <list.txt> <work_dir>
  list.txt: one filename per line (files in data/erp/photos/)
  writes <work_dir>/layers.csv : filename,L1,L2,L3,L4,type   (appends; resumable)

  L1 enhanced (erp_label.enhanced_view: top 72%, 900px, CLAHE) — plain prompt
  L2 enhanced — strict prompt with per-type rules
  L3 tight display crop from a DIFFERENT preprocessing (no CLAHE, gamma, 2x sharpen of the upper 60%) — careful prompt
  L4 original photo (<=1600 px) — digit-by-digit with ANSWER: line, also returns TYPE: line
No credentials are used here. Test photos (benchmark/data/photos.sha256) are skipped.
"""
import csv
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "lab"))
import cv2  # noqa: E402
import numpy as np  # noqa: E402
import erp_label  # noqa: E402

PH = REPO / "data" / "erp" / "photos"
TYPES = ["TOMAS_STATIC", "TOMAS_SMART", "SMART_MT10", "CRYSTAL", "EMETER_GREEN", "TAGADOD", "HPL", "OTHER"]

P1 = ("This is an enlarged photo of an electricity meter. Read ONLY the large integer digits of the main LCD reading, exactly as displayed "
      "including leading zeros. Ignore small fraction digits after the decimal point and any serial numbers. If any single digit is uncertain "
      "(glare, ghost segments, blur, cut off), answer X. If the display is unreadable or there is no meter display answer X. If several meters "
      "are shown and the target is unclear answer P. Answer with only the digits, or X, or P.")
P2 = ("Electricity meter LCD photo. Task: transcribe the main kWh reading, INTEGER part only. Tomas meters show 6 big integer digits then small "
      "decimals. TAGADOD meters (blue backlit LCD) show 7 equal-size digits where the LAST one is the decimal (after a small dot): drop it and report "
      "the first 6. CRYSTAL meters show a short reading like 21.48 with a second smaller line (A, V, Hz, kW) — report only the integer part of the "
      "kWh line without adding zeros. SMART MT10 (yellow) and green-board meters show 6 integer digits then 2 decimals. Three-phase HPL meters "
      "may show 7 integer digits. Keep leading zeros exactly as shown; do not add zeros that are not displayed. Mechanical drum counters: report "
      "only the black integer drums, skip the red decimal drum. Ignore the second display line and serial numbers. If any digit is ambiguous, "
      "partly hidden, ghosted or glared, answer X. If several meters are shown and the target is unclear answer P. Answer with only the digits, "
      "or X, or P.")
P3 = ("You are a careful data labeller. Look at the electricity meter's main display and write the integer kWh reading exactly as displayed, "
      "keeping leading zeros that are displayed. Do not include decimal digits (small digits after the dot; the 7th digit of TAGADOD; the red "
      "drum). Ignore secondary lines, voltages, currents and serial numbers. Output X if even one integer digit is not certain or the display is "
      "unreadable; output P if several meters are visible and which one is meant is unclear. Output ONLY the digits, X or P, with no explanation.")
P4 = ("Original photo of an electricity meter. Find the main kWh display. Go digit by digit from left to right through the INTEGER part only "
      "(stop at the decimal point; on 7-digit TAGADOD blue LCDs the last digit is a decimal; on drum counters skip the red drum; on CRYSTAL meters "
      "read only the upper kWh line). For each digit check carefully which segments are really dark versus faint ghost segments: 0 vs 8, 1 vs 7, "
      "3 vs 9, 5 vs 6, 2 vs 7 are common mistakes. Include every displayed leading zero, do not invent zeros. If any digit is not certain answer X. "
      "If several meters and unclear which, answer P.\nAlso classify the meter as one of: TOMAS_STATIC (Tomas 'Static kWh Meter', small "
      "yellow/green LCD), TOMAS_SMART (Tomas 'Bi-Directional Smart Meter', large grey LCD), SMART_MT10 (yellow 'SMART MT10-ALPHA' / DMC), "
      "CRYSTAL (brand CRYSTAL, two-line LCD), EMETER_GREEN (green circuit board visible behind clear cover), TAGADOD (brand TAGADOD, blue backlit "
      "LCD, 7 digits), HPL (three-phase HPL meter), OTHER.\nLast two lines must be exactly:\nTYPE: <type>\nANSWER: <digits or X or P>")


def ask(prompt, path, timeout=150):
    for _ in range(3):
        try:
            r = subprocess.run(["gsk", "understand_images", "-r", prompt, "-i", path], capture_output=True, text=True, timeout=timeout)
            return json.loads(r.stdout)["data"]["results"][0]["result"].strip()
        except Exception:
            pass
    return "ERR"


def norm(t):
    t = t.strip().upper().strip(".`*\"' ")
    t = t.split()[0] if t.split() else "X"
    return t if re.fullmatch(r"\d+|X|P", t) else "X"


def alt_view(img):
    """Different preprocessing from enhanced_view: upper 60%, gamma 0.8 on gray-world balanced image, unsharp mask, 1100 px wide."""
    H = img.shape[0]
    c = img[int(H * 0.05): int(H * 0.62)].astype(np.float32)
    c = c * (c.reshape(-1, 3).mean() / (c.reshape(-1, 3).mean(0) + 1e-6))
    c = np.clip(255 * (np.clip(c, 0, 255) / 255) ** 0.8, 0, 255).astype(np.uint8)
    s = 1100 / c.shape[1]
    c = cv2.resize(c, None, fx=s, fy=s, interpolation=cv2.INTER_LANCZOS4)
    b = cv2.GaussianBlur(c, (0, 0), 3)
    return cv2.addWeighted(c, 1.6, b, -0.6, 0)


def job(n, work):
    p = PH / n
    if not p.exists():
        return None
    if erp_label.is_test_photo(p):
        return [n, "SKIP_TEST", "", "", "", ""]
    img = cv2.imread(str(p))
    if img is None:
        return [n, "BADIMG", "", "", "", ""]
    e = work / "enh" / n
    a = work / "alt" / n
    o = work / "orig" / n
    e.write_bytes(erp_label.enhanced_view(img))
    cv2.imwrite(str(a), alt_view(img), [cv2.IMWRITE_JPEG_QUALITY, 88])
    s = 1600 / max(img.shape[:2])
    im = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA) if s < 1 else img
    cv2.imwrite(str(o), im, [cv2.IMWRITE_JPEG_QUALITY, 90])
    l1 = norm(ask(P1, str(e)))
    l2 = norm(ask(P2, str(e)))
    l3 = norm(ask(P3, str(a)))
    t4 = ask(P4, str(o))
    l4 = norm(t4.rsplit("ANSWER:", 1)[-1]) if "ANSWER:" in t4 else "X"
    ty = "OTHER"
    m = re.search(r"TYPE:\s*([A-Z_]+)", t4.upper())
    if m and m.group(1) in TYPES:
        ty = m.group(1)
    return [n, l1, l2, l3, l4, ty]


def main():
    names = [Path(x.strip()).name for x in open(sys.argv[1]) if x.strip()]
    work = Path(sys.argv[2])
    for d in ("enh", "alt", "orig"):
        (work / d).mkdir(parents=True, exist_ok=True)
    out = work / "layers.csv"
    done = {r[0] for r in csv.reader(open(out))} if out.exists() else set()
    todo = [n for n in names if n not in done]
    new = not out.exists()
    with ThreadPoolExecutor(12) as ex, open(out, "a", newline="") as fo:
        w = csv.writer(fo)
        if new:
            w.writerow(["filename", "L1", "L2", "L3", "L4", "type"])
        for res in ex.map(lambda n: job(n, work), todo):
            if res:
                w.writerow(res)
                fo.flush()
    print(f"layers: {len(todo)} new -> {out}")


if __name__ == "__main__":
    main()
