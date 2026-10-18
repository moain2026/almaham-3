# benchmark/
## data/
| الملف | المحتوى |
|---|---|
| `ground_truth.csv` | **v2، المعتمد.** أعمدة: `filename, reading` (رقم نظيف بدون أصفار/كسور؛ فاضي = غير مقروء), `display_text` (الشاشة كاملة), `meter_type`, `difficulty` (clear/hard/unreadable), `uncertain` (1 = يحتاج مراجعة المالك), `notes` |
| `meter_boxes.json` | مستطيل العداد التقريبي لكل صورة [x1,y1,x2,y2] مُطبّع = **الوضع A** (يحاكي مستطيل القارئ) |
| `display_boxes.json` | مستطيل الشاشة المرجعي (46 صورة) — تقييم فقط (الوضع C) |
| `line_boxes.json` | مستطيل سطر القراءة الرئيسي (46) — تقييم فقط (الوضع L)؛ يُبنى بـ `lab/make_line_boxes.py` |
| `lcd_boxes_erp_detector.json` | مخرجات كاشف الـ ERP الخام (بكسل) — مصدر display_boxes |
| `photos.sha256` | بصمات الصور الـ49 — `scripts/verify_photos.sh` |
| `photos_manifest.json` | مصدر الصور (رسائل Telegram) |
| `archive/` | v1 (فيه أخطاء — لا تستخدم) |

الصور: 38 بدقة 1920×2560 و 11 بدقة 1440×2560 (23087–23097)، كلها عمودية.
توزيع الأنواع: TOMAS_SMART 21، SMART_MT10 11، EMETER_GREEN 6، CRYSTAL 5، TOMAS_STATIC 4، TAGADOD 2.

## results/
| المسار | المحتوى |
|---|---|
| `verified_2026-10-18.txt` | مخرجات حرفية لإعادة تشغيل كل القياسات من هذا المستودع |
| `raw/raw_<engine>.json` | مخرجات PP-OCR الخام لكل صورة ووضع (A/B) + الزمن — `score.py` يقيّمها |
| `engines/segreader_<ckpt>.json` | SegReader لكل صورة: الخام، النظيف، صح/غلط، أقل ثقة |
| `archive/` | مخرجات محسوبة على v1 |
