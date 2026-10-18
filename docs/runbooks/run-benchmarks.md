# Runbook: إعادة كل القياسات
**متى:** بعد أي تغيير في الحقيقة أو المحرك · **المدة:** score 1د، ERP ~1د، PP-OCR كامل 10–30د · **الصلاحيات:** —

## الخطوات (من `lab/`)
1. `python3 score.py ppocrv5_mobile ppocrv6_tiny ppocrv6_small` — يعيد التقييم من المخرجات الخام المحفوظة (سريع).
2. `python3 baseline2.py` — ERP baseline (يحتاج `data/erp_vision/`).
3. `python3 rec_only.py` — سقف القارئ على قصّ الشاشة المرجعي.
4. `python3 eval_rec.py weights/rec_w075.pt` — SegReader؛ يكتب `benchmark/results/engines/segreader_rec_w075.json`.
5. لإعادة تشغيل PP-OCR من الصفر (ثقيل): `nohup python3 run_raw.py ppocrv6_tiny > ../lab/logs/run_raw.log 2>&1 &`
   — يكتب `benchmark/results/raw/raw_<engine>.json`، ثم الخطوة 1.

## التحقق من النجاح
الأرقام تطابق `benchmark/results/verified_2026-10-18.txt`. أي اختلاف = سجّله في `docs/research/benchmark-summary.md` مع السبب.

## التراجع
المخرجات في git؛ `git checkout benchmark/results/`.
