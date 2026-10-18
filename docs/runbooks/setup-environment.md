# Runbook: تجهيز بيئة جديدة (سندبوكس/جهاز جديد) من الصفر
**متى:** أول مرة في أي بيئة جديدة · **المدة المتوقعة:** 10–20 دقيقة · **الصلاحيات:** وصول GitHub لـ moain2026/almaham-3

## الخطوات
1. `git clone https://github.com/moain2026/almaham-3.git && cd almaham-3`
2. Python 3.13: `pip install -r requirements-lab.txt` (torch CPU من فهرس pytorch).
3. النماذج الجاهزة: `bash scripts/download_models.sh` (تُتحقق بـ SHA256؛ تنزل في `data/models/`).
4. **الصور الـ49 (خاصة، غير موجودة في git — ADR-0004):**
   - المصدر: قناة Telegram ‏@AlabbasiTech، الرسائل 23065–23113 بتاريخ 2026-10-18 (القائمة في `benchmark/data/photos_manifest.json`)،
     أو أرشيف `meters.zip` عند المالك (34MB، مجلد `correct_49_meter_photos/photos/`).
   - ضعها في `data/photos/` (أو `export METER_PHOTOS_DIR=/path`).
   - `bash scripts/verify_photos.sh` ⇒ لازم `OK: 49/49 photos match`.
   - ⚠️ **لا تخلطها** مع `maeen_latest_49_photos` (رسائل 26313–29081): تلك صور تصاميم UI وليست عدادات.
5. (اختياري، baseline الـ ERP فقط) انسخ `almaham-2/backend/models/vision/` إلى `data/erp_vision/` — AGPL، معمل فقط.
6. (اختياري، للتدريب) ولّد البيانات: `cd lab && TORCH_THREADS=2 nohup python3 gen_data.py 96000 ../data/synth/syn_a.npz 1000 > ../lab/logs/gen.log 2>&1 &`
7. (اختياري، للتطبيق) Flutter 3.35.4 / Dart 3.9.2 / Android SDK 35 / JDK 17.

## التحقق من النجاح
`bash scripts/check.sh` ⇒ `lint OK` + `OK: 49/49` + `"exact": 15, "n": 46`.

## التراجع (Rollback)
لا شي يُكتب خارج `data/` (git-ignored). احذف `data/` للبدء من جديد.
