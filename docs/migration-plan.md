# خطة النقل للمشروع الرئيسي (almaham-2)

## ماذا ينتقل كما هو
| الملف | الوجهة | لماذا كما هو |
|---|---|---|
| `app/meterocr/` (موديول كامل) | موديول Gradle `:meterocr` في مشروع Kotlin/Compose | لا يعتمد على أي واجهة؛ اعتمادياته: ORT Android (MIT) + exifinterface فقط |
| `assets/models/line_locator.onnx`, `digit_reader.onnx` | داخل الموديول نفسه | 1.7MB مجموعاً، `noCompress onnx` موجود في `build.gradle.kts` |
| `MeterOcrConfig.kt` | كما هو | كل حدّ قابل للضبط من مكان واحد (`MAX_CONSUMPTION_KWH` مثلاً يأتي من الـ ERP لاحقاً) |
| اختبارات الوحدات (35) | `src/test` في الموديول | تثبت تحويل الإحداثيات والتجميع والتنظيف والتحقق |

## ماذا يتغيّر في مشروع Kotlin + Compose (CameraX 1.5.0 موجود عندهم)
1. **شاشة الكاميرا:** استبدال `image_picker`/Intent الحالي بـ `CameraScreen.kt` (نُقلت كما هي؛ تعتمد على CameraX 1.5.0 الذي عندهم و`RectangleState.kt`).
2. **خط المعالجة:** `CapturePipeline.kt` يدخل كطبقة بين الكاميرا وشاشة الإدخال. الضغط الحالي عندهم (WebP q82) يبقى: `EvidenceImage` يبدأ من q82 وينزل حتى ≤200KB.
3. **شاشة الإدخال:** إضافة ثلاث حالات فقط: شارة «قراءة تلقائية»، تلوين الخانات غير المؤكدة (`uncertainIndices`)، ولون الحقل من `ReadingValidator`. لا تغيير في منطق الحفظ.
4. **السجل:** `ReadingRecord` يُرسل مع القراءة للـ ERP (12 حقلاً، CSV/JSON).
5. **التسخين:** `MeterReader.warmUp()` عند فتح شاشة الإدخال (ونُبقي الكائن حياً طول عمر التطبيق).
6. **حذف ML Kit** من اعتماديات المنتج (كان للمقارنة فقط).

## ماذا يتغيّر في تطبيق Flutter
- الكاميرا والقص والقراءة تبقى **Native (Kotlin)**: Flutter يستدعي `MethodChannel("meterocr")` بـ `capture()` ويستلم
  `{value, uncertainIndices, confident, status, captureToNumberMs, thumbnailPath, evidencePath, evidenceBytes}`.
- سبب القرار: بث الإطارات إلى Dart بطيء على الأجهزة الضعيفة (مرجع في `docs/brief/03_البحوثات.txt`)، ولا نريد نسختين من منطق الإحداثيات.
- يُنفَّذ كـ Flutter plugin صغير (`android/` فيه الموديول `meterocr` + Activity الكاميرا). iOS خارج النطاق (minSdk 24 أندرويد فقط حسب القيود).
- ملاحظة إصدار: المشروع الرئيسي يطلب Dart `^3.12`؛ كود Dart للقناة بسيط ولا يستخدم ميزات لغة حديثة.

## المخاطر
| الخطر | الأثر | التخفيف |
|---|---|---|
| ZSL غير مدعوم على بعض الأجهزة المتوسطة | +100–250ms في زمن الالتقاط | `isZslSupported` → `MINIMIZE_LATENCY` تلقائياً؛ القياس في `captureToNumberMs` يكشفه |
| `BitmapRegionDecoder` على JPEG كبيرة (12–50MP) | 30–120ms | نفك المستطيل فقط وليس الإطار كله (مقاس في `locatorPrepMs`) |
| فرق `PreviewView.ScaleType` بين المشروعين | قصّ خاطئ | `RectGeometry` يأخذ `PreviewScale` صراحة + 18 اختباراً |
| ORT على armeabi-v7a | أبطأ ~2× | `abiFilters` تشمل v7a؛ نقيس على جهاز 32-bit إن وُجد |
| الفجوة اصطناعي→حقيقي في الدقة | أقل من 95% | خطة التحسين في `benchmark_report.md` §6 (صور معتمدة من النظام) |
| تلوين الخانات في `OutlinedTextField` يختلف عن مكوّنهم | واجهة | `UncertainDigitsTransformation` مكوّن مستقل يُعاد استخدامه |
