"""Labelling workflow for ERP photos (no approved readings exist in the export; humans/agents create them).

Three commands, all writing under data/erp/ (NOT in git) except the final CSV which goes to benchmark/data/erp/:

  python3 erp_label.py sheets <slice_list.txt> <sheet_dir> [per_sheet=20]
      Makes HTML sheets: for every photo an enlarged, CLAHE-enhanced view of the upper-middle region (where the
      LCD is on all our meter types) next to the full photo, with an input box. A labeller types ONLY the integer
      digits as displayed (keep leading zeros, e.g. 003155), or 'X' for unreadable, or 'P' for a panel where the
      target meter is ambiguous. Sheets are self-contained; "Export CSV" copies the labels to the clipboard.
  python3 erp_label.py merge <labels_dir> <out_csv>
      Merges exported CSV fragments (filename,text) into benchmark/data/erp/labels.csv with de-duplication; rows
      labelled by two different labellers that disagree are written to conflicts.csv for a third pass.
  python3 erp_label.py stats <labels.csv>
      Counts, digit histogram, unreadable share.

Label format (labels.csv): filename,text,labeller,ts   where text is digits-only / X / P.
Rules: never label a photo from the 49-photo test set (checked by SHA256 against benchmark/data/photos.sha256).
"""
import csv
import hashlib
import html
import sys
import time
from collections import Counter
from pathlib import Path

import cv2

import paths

ERP = paths.DATA / "erp"
TEST_HASHES = {ln.split()[0] for ln in open(paths.BENCH_DATA / "photos.sha256") if ln.strip()}


def enhanced_view(img):
    """Upper 70% of the photo, upscaled to 900px wide, with CLAHE on L channel; returns JPEG bytes (base64 later)."""
    H, W = img.shape[:2]
    crop = img[: int(H * 0.72)]
    s = 900 / crop.shape[1]
    crop = cv2.resize(crop, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    lab = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
    lab[..., 0] = cv2.createCLAHE(3.0, (8, 8)).apply(lab[..., 0])
    enh = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    return cv2.imencode(".jpg", enh, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()


def thumb(img):
    s = 420 / max(img.shape[:2])
    t = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
    return cv2.imencode(".jpg", t, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()


def is_test_photo(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest() in TEST_HASHES


def sheets(list_file, out_dir, per_sheet=20):
    import base64
    names = [Path(l.strip()).name for l in open(list_file) if l.strip()]
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    made = 0
    for si in range(0, len(names), per_sheet):
        rows = []
        for n in names[si:si + per_sheet]:
            p = ERP / "photos" / n
            if not p.exists() or is_test_photo(p):
                continue
            img = cv2.imread(str(p))
            if img is None:
                continue
            e = base64.b64encode(enhanced_view(img)).decode()
            t = base64.b64encode(thumb(img)).decode()
            rows.append(f'''<div class="row" data-f="{html.escape(n)}">
<img class="enh" src="data:image/jpeg;base64,{e}"><img class="th" src="data:image/jpeg;base64,{t}">
<div class="ctl"><div class="fn">{html.escape(n)}</div>
<input type="text" inputmode="numeric" placeholder="الرقم الصحيح كما يظهر (مع الأصفار) أو X أو P" autocomplete="off">
<div class="hint">X = لا يُقرأ · P = لوحة والعداد غير واضح · لا تكتب الكسور</div></div></div>''')
        if not rows:
            continue
        page = f'''<!doctype html><html dir="rtl"><meta charset="utf-8"><title>sheet {si // per_sheet:03d}</title>
<style>body{{font-family:system-ui;background:#111;color:#eee;margin:0}} .row{{display:grid;grid-template-columns:900px 420px 1fr;gap:12px;padding:10px;border-bottom:2px solid #333;align-items:start}}
.enh{{width:900px}} .th{{width:420px}} .fn{{font-family:monospace;font-size:12px;color:#aaa}} input{{font-size:28px;width:360px;padding:8px;direction:ltr;text-align:left;letter-spacing:4px}}
.hint{{color:#888;font-size:13px;margin-top:6px}} #bar{{position:sticky;top:0;background:#222;padding:10px;z-index:9}} button{{font-size:16px;padding:8px 16px}} textarea{{width:100%;height:120px;font-family:monospace}}</style>
<div id="bar"><button onclick="exp()">Export CSV</button> <span id="cnt"></span> — اكتب اسمك: <input id="who" style="font-size:16px;width:160px;direction:ltr"></div>
{''.join(rows)}
<textarea id="out" placeholder="CSV يظهر هنا — انسخه إلى labels/<اسمك>_<رقم>.csv"></textarea>
<script>
const inputs=[...document.querySelectorAll('.row input')];
inputs.forEach((el,i)=>{{el.addEventListener('keydown',e=>{{if(e.key==='Enter'){{e.preventDefault();(inputs[i+1]||el).focus();}}}});el.addEventListener('input',()=>{{el.value=el.value.toUpperCase().replace(/[^0-9XP]/g,'');upd();}});}});
function upd(){{document.getElementById('cnt').textContent=inputs.filter(x=>x.value).length+'/'+inputs.length;}}
function exp(){{const who=document.getElementById('who').value||'anon';const ts=Math.floor(Date.now()/1000);
const lines=['filename,text,labeller,ts'];document.querySelectorAll('.row').forEach(r=>{{const v=r.querySelector('input').value;if(v)lines.push(r.dataset.f+','+v+','+who+','+ts);}});
const t=document.getElementById('out');t.value=lines.join('\\n');t.select();document.execCommand('copy');}}
</script></html>'''
        (out / f"sheet_{si // per_sheet:03d}.html").write_text(page, encoding="utf-8")
        made += 1
    print(f"{made} sheets in {out}")


def merge(labels_dir, out_csv):
    by = {}
    for f in sorted(Path(labels_dir).glob("*.csv")):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            t = r["text"].strip().upper()
            if not (t.isdigit() or t in ("X", "P")):
                continue
            by.setdefault(r["filename"], []).append((t, r.get("labeller", "?"), r.get("ts", "")))
    out = Path(out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    conflicts = []
    with open(out, "w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo)
        w.writerow(["filename", "text", "labeller", "ts", "n_labels"])
        for fn, labs in sorted(by.items()):
            texts = {t for t, _, _ in labs}
            if len(texts) == 1:
                t, who, ts = labs[0]
                w.writerow([fn, t, who, ts, len(labs)])
            else:
                conflicts.append((fn, "|".join(f"{t}:{who}" for t, who, _ in labs)))
    with open(out.parent / "conflicts.csv", "w", newline="", encoding="utf-8") as fc:
        csv.writer(fc).writerows([["filename", "labels"]] + conflicts)
    print(f"{out}: {sum(1 for _ in open(out)) - 1} rows, {len(conflicts)} conflicts")


def stats(labels_csv):
    rows = list(csv.DictReader(open(labels_csv, encoding="utf-8")))
    texts = [r["text"] for r in rows]
    print("total", len(rows), "unreadable X", texts.count("X"), "panel P", texts.count("P"))
    digs = Counter(c for t in texts if t.isdigit() for c in t)
    print("digit histogram", sorted(digs.items()))
    print("length histogram", sorted(Counter(len(t) for t in texts if t.isdigit()).items()))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "sheets":
        sheets(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 20)
    elif cmd == "merge":
        merge(sys.argv[2], sys.argv[3])
    elif cmd == "stats":
        stats(sys.argv[2])
    else:
        print(__doc__)
