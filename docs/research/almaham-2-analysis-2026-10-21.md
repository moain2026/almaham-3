# تحليل مستودع `moain2026/almaham-2` (المشروع الرئيسي) لصالح almaham-3 — وكيل S، 2026-10-21 02:20Z

> سؤال المالك: «بدأت أدرّب نماذج فيه — هل فيه ما نستفيد منه أو ندرّب فوقه؟». الجواب بعد فحص كامل للمستودع (423 MB، HEAD `71ca69f`).

## 1. النماذج الموجودة (`backend/models/vision/`)
| الملف | ما هو | الرخصة | هل نستعمله؟ |
|---|---|---|---|
| `lcd-detector-v1.onnx` (10.8 MB) | **Ultralytics YOLO11n**، 960×960، 8 فئات شاشات: `tomas_2018_2019, tomas_2020, tomas_2021_2022, conlog, tajaddod, crystal, veto, iraqi_mechanical` — مدرَّب 2026-08-23 على `D:\alabasi2026\meter-training-data\datasets` | **AGPL-3.0** (مكتوبة في metadata الملف) | **لا يُشحن ولا يُدرَّب فوقه** (ADR-0003). يُستعمل **في المعمل فقط** كـ baseline (هو «ERP 17/46» في التقارير) و**كمُسمٍّ آلي لنوع العداد** (8 فئات = بالضبط التنويع الذي نحتاجه) |
| `digit-reader-v3.onnx` (10.8 MB) | YOLO11n، 960×960، 10 فئات أرقام | AGPL-3.0 | نفس الحكم. مفيد كـ**مُقترِح صناديق خانات ضعيفة** في المعمل فقط (بديل لـ`erp_finetune.py build` عندما يفشل قارئنا) |
| `swift-yolo-electric-meter-v1.tflite` (2.9 MB) | Seeed SSCMA، كاشف أرقام 192×192 | **MIT** | مرخّص لنا؛ لكنه tflite لا يُحوَّل لـ ORT المصغّر بسهولة، وغير مقاس. **تجربة لاحقة اختيارية** |
| `tessdata/ssd_int.traineddata` | Tesseract سباعي | Apache-2.0 | ضعيف على صورنا تاريخياً؛ لا |

## 2. أدوات التدريب (`tools/meter-vision-training/`)
- `train-digit-cnn-v5.py`: مصنّف خانة واحدة صغير (depthwise CNN، SiLU) يتدرّب على **قصوص خانات موثّقة** من ملفات `digit-labels-tight.json` + `field-digit-labels.json` (+ `digit-labels-self.json` للتدريب الذاتي)، مع تقسيم حسب القصّ وWeightedRandomSampler. **الملفات نفسها غير موجودة في المستودع** (كانت على `D:\...` عند المالك).
- **القيمة:** المنهج (تقسيم حسب العداد، أوزان للتوازن، SEED ثابت) سليم؛ ملفات التسمية `digit-labels-tight.json` إن وُجدت عند المالك فهي **صناديق خانات بشرية** — ثمينة. **طلب من المالك:** هل ما زالت عندك `D:\alabasi2026\meter-training-data\`؟

## 3. **الاكتشاف الأهم: قاعدة ERP تحوي القراءة البشرية لكل صورة**
`backend/migrations/20260704_billing_meter_readings.sql` + `billing-meter-reading-entry.service.ts`:
```
billing_meter_readings(
  meter_id, previous_reading_kwh, current_reading_kwh, consumption_kwh, is_rollover,
  photo_storage_key, photo_checksum_sha256, photo_mime_type, status, reading_source, captured_at, ...)
```
- **كل صورة قراءة = صف فيه `current_reading_kwh` الذي أدخله المحصّل**، مع sha256 الصورة ومسارها وحالة الاعتماد.
- السكربت جاهز من الوكيل A: `scripts/export_erp_training.sql` (يأخذ `floor(current_reading_kwh)` للصور `confirmed`/`actual`).
- **الأثر:** بدل تسمية آلية بخطأ 10–17% (4,306 صورة)، نحصل على **~23,000 قراءة بشرية معتمدة** مجاناً. وعمود `previous_reading_kwh` يعطينا **مدخل `plausibility.py`** جاهزاً.
- **التحذير (S1 Copel-AMR):** قراءة المحصّل ليست خالية من الخطأ (يكتب رقماً خاطئاً أحياناً، أو يقرأ من عداد مجاور في لوحة). الحل القياسي: **اتفاق مصدرين مستقلين** = قراءة المحصّل **و** قراءة آلية (نموذجنا/ERP-YOLO في المعمل) ⇒ تسمية «ذهبية»؛ الاختلاف ⇒ مراجعة D. هذا يرفع جودة التسمية فوق أي مصدر وحده.

## 4. ما ليس في المستودع (ولا نحتاجه)
- لا صور عملاء (جيد). لا أوزان `.pt` قابلة للتدريب فوقها (ONNX فقط، وAGPL). لا بيانات التدريب الأصلية.
- `collector-app-flutter/` و`employee-mobile-android/`: التطبيقات الهدف للنقل لاحقاً (`docs/migration-plan.md`).

## 5. القرارات
1. **لا تدريب فوق نماذج almaham-2** (AGPL + لا أوزان). المعمارية الحالية DigitNet تبقى.
2. **طلب فوري من المالك:** تشغيل `scripts/export_erp_training.sql` على قاعدة ERP (أو إعطاء وكيل D وصولاً للقراءة فقط) ⇒ `erp_training_export.csv` (reading_id, meter_id, photo_key, photo_sha256, reading_int, source, captured_at) ⇒ يُرفع للمستودع الخاص `erp/manifests/`. **هذا أعلى عائد/جهد في المشروع كله.**
3. **نسخ `lcd-detector-v1.onnx` إلى المستودع الخاص** (`erp/tools_agpl_lab_only/`) لاستعمال معملي واحد: تصنيف نوع العداد لكل صورة ⇒ `meter_type` آلي لـ23,797 صورة ⇒ موازنة الأنواع وفلترة Crystal/Veto/Tajaddod للتسمية ذات الأولوية. يُوثَّق أنه لا يدخل المنتج.
4. تحديث برومت D: إن وصل `erp_training_export.csv` تتحوّل مهمته من «قراءة من الصفر» إلى «**تأكيد/نفي قراءة المحصّل**» (أسرع 5×) + بناء مجموعة الاختبار من التي اتفق عليها مصدران + عينه.
