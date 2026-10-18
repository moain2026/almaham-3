# almaham-meter — التطبيق التجريبي (Android, Kotlin + Compose + CameraX 1.5.0 + ONNX Runtime)

## البنية
```
app/
├── meterocr/   مكتبة مستقلة عن الواجهة (هذه هي التي تنتقل للمشروع الرئيسي)
│   ├── MeterOcrConfig.kt      كل الحدود والقيم (ملف واحد)
│   ├── RectGeometry.kt        تحويل مستطيل الشاشة → بكسلات الصورة (دوران/zoom/FILL_CENTER) — 18 اختبار
│   ├── ReadingAssembler.kt    كشف الأرقام → رقم صحيح واحد + ثقة لكل خانة (مرآة lab/assemble.py) — 12 اختبار
│   ├── ReadingValidator.kt    التحقق بالألوان (أحمر/برتقالي) — لا يمنع الحفظ
│   ├── PeakDecoder.kt         فك خرائط الحرارة
│   ├── MeterReader.kt         المحرك: محدِّد السطر (256²) → قارئ الأرقام (64×448) → تجميع، مع زمن كل مرحلة
│   ├── EvidenceImage.kt       صورة الدليل WebP 1280px، 80–200KB، EXIF (وقت + جهاز)
│   ├── ReadingLog.kt          سجل CSV لكل قراءة (§2.8)
│   └── src/main/assets/models/{line_locator,digit_reader}.onnx   (تُصدَّر من lab/export_onnx.py)
└── demo/       التطبيق: EntryScreen (بيانات وهمية) · CameraScreen (مستطيل + زوم + فلاش + ZSL) · CapturePipeline · BatchBenchmark
```

## البناء
المتطلبات: JDK 17، Android SDK 35 (build-tools 35.0.0). لا يحتاج Android Studio.
```bash
cd app
echo "sdk.dir=/path/to/android-sdk" > local.properties
JAVA_HOME=/path/to/jdk17 ./gradlew :meterocr:testDebugUnitTest :demo:testDebugUnitTest   # 35 اختبار وحدات
JAVA_HOME=/path/to/jdk17 ./gradlew :demo:assembleDebug                                     # demo/build/outputs/apk/debug/demo-debug.apk
adb install -r demo/build/outputs/apk/debug/demo-debug.apk
```
النماذج: `cd lab && python3 export_onnx.py weights/locator_v1.pt weights/reader_v1.pt ../app/meterocr/src/main/assets/models`.

## التشغيل
1. شاشة الإدخال تفتح، ويُسخَّن النموذجان فوراً في الخلفية.
2. «تصوير العداد» → كاميرا داخل التطبيق بمستطيل 78% × نسبة 1.25، يتذكّر آخر موضع. الضغطة تلتقط فوراً (ZSL إن وُجد).
3. يرجع للإدخال؛ الرقم يظهر مع شارة «قراءة تلقائية»، الخانات غير المؤكدة ملوّنة برتقالي، ثم تُحفظ صورة الدليل ويظهر حجمها.
4. «حفظ والتالي» يكتب سطراً في `Android/data/com.almaham.meterdemo/files/readings_log.csv`.

## وضع الاختبار الجماعي (49 صورة × وضعين × محركين)
```bash
adb push /path/to/correct_49_meter_photos/photos /sdcard/Android/data/com.almaham.meterdemo/files/photos
```
ثم من شاشة الإدخال: «وضع الاختبار الجماعي» → «تشغيل». المخرجات:
`files/bench_<device>.csv` (سطر لكل صورة/وضع/محرك) و `files/bench_summary_<device>.json` (exact, empty, wrong_confident, p50/p95/max, حجم الدليل).
الوضع A = مستطيل العداد من `meter_boxes.json`، B = الصورة كاملة. المحركان: `digitnet` (محركنا) و `mlkit` (خط الأساس).

## الرخص المشحونة
| المكوّن | الرخصة |
|---|---|
| DigitNet (أوزان + كود) | © moain2026 — مدرَّب على بيانات اصطناعية فقط |
| خطوط DSEG (داخل بيانات التدريب فقط، لا تُشحن) | SIL OFL 1.1 |
| ONNX Runtime Android 1.31.0 | MIT |
| CameraX 1.5.0 / AndroidX / Compose | Apache 2.0 |
| ML Kit Text Recognition 16.0.1 (للمقارنة فقط، يُحذف في المنتج) | ML Kit Terms of Service |
