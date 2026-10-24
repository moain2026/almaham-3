#!/usr/bin/env bash
# Contabo cron (every 5 min): refresh a static results snapshot the owner can open/download any time:
#   https://basirapp.site/meter/results/            (index: latest numbers + links)
#   https://basirapp.site/meter/results/snapshot.zip (runs.md, STATUS, results JSON/CSV, weights .pt, logs)
# Source = branch auto-training (fetched fresh) merged with local lab/ artefacts.
set -uo pipefail
R=/opt/almaham/almaham-3; OUT=/opt/almaham/results_public; mkdir -p "$OUT"; cd "$R"
git fetch -q origin auto-training genspark_ai_developer 2>/dev/null || true
TMP=$(mktemp -d); mkdir -p "$TMP/snap"
SRC=origin/auto-training; git rev-parse -q --verify "$SRC" >/dev/null || SRC=origin/genspark_ai_developer
git archive "$SRC" docs/training-log STATUS.md benchmark/results/engines lab/weights lab/logs 2>/dev/null | tar -x -C "$TMP/snap" 2>/dev/null || true
mkdir -p "$TMP/snap/lab/logs" "$TMP/snap/lab/weights" "$TMP/snap/docs/training-log"
cp -f lab/logs/autotrain_*.log lab/logs/train_*.log "$TMP/snap/lab/logs/" 2>/dev/null; cp -f lab/weights/*.pt "$TMP/snap/lab/weights/" 2>/dev/null
(cd "$TMP/snap" && zip -qr "$OUT/snapshot.zip.tmp" . ) && mv -f "$OUT/snapshot.zip.tmp" "$OUT/snapshot.zip"
cp -f "$TMP/snap/docs/training-log/runs.md" "$OUT/runs.md" 2>/dev/null; cp -f "$TMP/snap/STATUS.md" "$OUT/STATUS.md" 2>/dev/null
python3 - "$OUT" "$R" <<'PY'
import sys, os, re, time, subprocess, html
out, R = sys.argv[1:3]
runs = open(os.path.join(out, "runs.md"), encoding="utf-8").read() if os.path.exists(os.path.join(out, "runs.md")) else ""
rows = [l for l in runs.splitlines() if l.startswith("|") and not l.startswith("|---") and "الوسم" not in l][-25:]
def loop(f):
    p = os.path.join(R, "lab/logs", f)
    return open(p, encoding="utf-8", errors="ignore").read().splitlines()[-6:] if os.path.exists(p) else ["(no log)"]
def prog(pat):
    import glob
    fs = sorted(glob.glob(os.path.join(R, "lab/logs", pat)), key=os.path.getmtime)[-4:]
    o = []
    for f in fs:
        ls = [l for l in open(f, encoding="utf-8", errors="ignore").read().splitlines() if l.startswith("step")]
        o.append(f"{os.path.basename(f)}: {ls[-1] if ls else '...'}")
    return o
sz = os.path.getsize(os.path.join(out, "snapshot.zip")) // 1024 // 1024
H = f"""<!doctype html><html dir="rtl" lang="ar"><meta charset="utf-8"><meta http-equiv="refresh" content="300">
<title>almaham-3 — نتائج التدريب المستمر</title><style>body{{font-family:system-ui;margin:1.5em;max-width:1100px}} pre{{background:#f4f4f4;padding:.6em;overflow:auto;direction:ltr;text-align:left}} table{{border-collapse:collapse;font-size:.85em}} td,th{{border:1px solid #ccc;padding:.25em .5em}}</style>
<h1>almaham-3 — التدريب المستمر (يتحدّث كل 5 دقائق)</h1>
<p>آخر تحديث: <b>{time.strftime('%Y-%m-%d %H:%M')} بتوقيت مكة</b> &nbsp;|&nbsp; <a href="snapshot.zip"><b>تنزيل كل النتائج (snapshot.zip، {sz} MB)</b></a>: runs.md، STATUS، JSON/CSV النتائج، الأوزان .pt، السجلات &nbsp;|&nbsp; <a href="runs.md">runs.md</a> · <a href="STATUS.md">STATUS.md</a></p>
<p>المصدر: فرع <code>auto-training</code> في <a href="https://github.com/moain2026/almaham-3/tree/auto-training">GitHub</a> (يُدفع آلياً من Contabo وsandbox). الأرشيف الكامل (أوزان وسيطة، صور مراجعة) في المستودع الخاص <code>weights_archive/</code>.</p>
{('<p style="background:#fdd;padding:.6em;border:2px solid #c00"><b>تحذير: فشل الدفع إلى GitHub</b> — النتائج أدناه محلية فقط:<br>'+html.escape(open(os.path.join(R,'lab/autotrain/state/PUSH_FAILED')).read().strip().replace(chr(10),' | '))+'</p>') if os.path.exists(os.path.join(R,'lab/autotrain/state/PUSH_FAILED')) else ''}
<p>الخدمات: قارئ <b>{subprocess.run(['systemctl','is-active','almaham-autotrain-reader'],capture_output=True,text=True).stdout.strip()}</b> · محدِّد <b>{subprocess.run(['systemctl','is-active','almaham-autotrain-locator'],capture_output=True,text=True).stdout.strip()}</b> · آخر دفع ناجح: <code>{subprocess.run(['git','log','-1','--format=%h %ci','origin/auto-training'],capture_output=True,text=True,cwd=R).stdout.strip()}</code></p>
<h2>التشغيلات الجارية على Contabo</h2><pre>{html.escape(chr(10).join(prog('train_*.log')))}</pre>
<h2>حلقة القارئ</h2><pre>{html.escape(chr(10).join(loop('autotrain_reader.log')))}</pre>
<h2>حلقة المحدِّد</h2><pre>{html.escape(chr(10).join(loop('autotrain_locator.log')))}</pre>
<h2>آخر 25 صفاً من runs.md</h2><table>{''.join('<tr>'+''.join('<td>'+html.escape(c.strip())+'</td>' for c in r.strip('|').split('|'))+'</tr>' for r in rows)}</table>
<p>المرجع المنشور (new على /meter/) = locator_m1_augv2 + reader_ft6m2_s1 → الـ49: A 22/39، B 19/39؛ الاختبار البشري 21/34؛ بوابة صارمة 17 مقبولة/0 خاطئة من 73. تحليل توزيع البذور (27 محدِّد / 31 قارئ): <code>docs/research/autotrain-seed-analysis-2026-10-24.md</code>.</p></html>"""
open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(H)
PY
rm -rf "$TMP"; echo "[publish] $(date -u +%FT%TZ) ok"
