---
req: REQ-001
status: draft   # تصميم مبدئي؛ يُعتمد عند بدء M4
updated: 2026-10-18
---
# المعمارية: الالتقاط الذكي وقراءة العداد

## الملخص
Flutter للواجهة (شاشة الإدخال + الاختبار الجماعي)، و **Kotlin native** للكاميرا والقص والقراءة، يرجع لـ Flutter
الرقم + الثقة + الصورة المقصوصة فقط. السبب: بث الإطارات من الكاميرا لـ Dart ثقيل على الجوالات الضعيفة
(03_البحوثات §1)، والمشروع الرئيسي فيه تطبيق Kotlin يستخدم CameraX أصلاً.

## حقائق المشروع الرئيسي (almaham-2، مقروءة من الكود 2026-10-18)
| الجزء | الحقيقة | المصدر |
|---|---|---|
| تطبيق التحصيل/القارئ | Flutter، Dart SDK ^3.12، `minSdkVersion = flutter.minSdkVersion` (=24) | `collector-app-flutter/collector_app/pubspec.yaml`, `android/app/build.gradle` |
| شاشة القراءة الحالية | `ReaderCaptureScreen` تستخدم `image_picker` (`imageQuality: 80`, `maxWidth: 1600`) = كاميرا النظام | `lib/screens/reader_launcher_screen.dart:960-973` |
| تطبيق الموظف | Kotlin + Compose، minSdk 24، compile/target 36، CameraX 1.5.0 | `employee-mobile-android/app/build.gradle.kts`, `gradle/libs.versions.toml` |
| كاميرا العداد (Kotlin) | `ImageCapture` بـ `CAPTURE_MODE_MINIMIZE_LATENCY`، يكتب ملف ثم يحوّله | `ui/screens/readings/MeterCamera.kt:81-136` |
| ضغط الصورة (Kotlin) | WebP جودة 82، أقصى بُعد 1920 | `ui/screens/readings/MeterPhotoWebpEncoder.kt:12-14` |
| نماذج رؤية | `lcd-detector-v1.onnx`, `digit-reader-v3.onnx` (YOLO، AGPL)، `ssd_int.traineddata` (Apache-2.0)، `swift-yolo` (MIT، غير مستخدم) | `backend/models/vision/OPEN_SOURCE_MODELS.md` |

| بيئة السندبوكس | Flutter 3.35.4 / Dart 3.9.2 (مقفول) ≠ Dart ^3.12 في المشروع الرئيسي | `dart --version` |

**الاستنتاج للنقل:** وحدة Kotlin مستقلة (`meter-capture`) تُستدعى من Flutter عبر Platform Channel، وتقدر تنضم لتطبيق
الموظف مباشرة. minSdk 24.

## الطبقات المقترحة (app/)
```
app/                                  Flutter (UI فقط)
  lib/features/reading_entry/         شاشة الإدخال، الشارة، التلوين، التحقق المنطقي (Dart نقي + اختبارات)
  lib/features/bulk_test/             الاختبار الجماعي + التقرير
  lib/core/config.dart                كل الحدود والقيم (لا أرقام سحرية)
  android/meter-capture/ (Kotlin)     CameraX + المستطيل + تحويل الإحداثيات + القص + المحرك + الضغط
     geometry/RectMapper.kt           شاشة→صورة (rotation, FILL_CENTER, zoom) — دالة نقية + اختبارات كل الاتجاهات
     image/Cropper.kt, Encoder.kt     القص في الذاكرة، 1280px، WebP/JPEG 80–200KB، EXIF
     engine/LineLocator.kt            محدِّد السطر (ONNX)
     engine/SegReader.kt              القارئ (ONNX) + Preprocess مطابق لـ lab/prep.py حرفياً
     engine/Cleaner.kt                الأصفار، الكسور، النص الثانوي
```

## التدفق بعد الضغطة (الهدف p50 < 300ms)
1. التقاط (ZSL أو MINIMIZE_LATENCY؛ يُقارن مع آخر إطار ImageAnalysis) — ممنوع أي UI انتظار.
2. `RectMapper`: مستطيل الشاشة → مستطيل الصورة. 3. قص في الذاكرة.
4. نسخة صغيرة → `LineLocator` (256px) → قصّ السطر → `SegReader` (48×192) → نص + ثقة لكل خانة.
5. `Cleaner` → رقم. 6. **إرجاع الرقم لـ Flutter فوراً** (الشاشة تتسكر والرقم يظهر).
7. بعد الظهور: ضغط الصورة 1280px وحفظها + السجل (REQ-001.13).
8. التحقق المنطقي في Dart (أحمر/برتقالي/خانة ضعيفة/اختيار بديل منطقي) — لا يمنع الحفظ.

## المحرك (lab → app)
- التدريب والتقييم في `lab/` (PyTorch). التصدير ONNX (opset ثابت) ثم INT8.
- **التطابق الحرفي:** `lab/prep.py::to_input` (رمادي، ارتفاع 48، حشو يمين بالوسيط، تطبيع percentile 1–99) لازم
  يتطابق مع Kotlin؛ اختبار golden: نفس 46 قصّ → نفس tensor (فرق < 1e-3).
- المفردات `0123456789.`، blank=0، فك ترميز greedy (`rec_model.greedy_decode`).

## الاختبار
- وحدات: RectMapper (0/90/180/270، FILL_CENTER، زوم 1/2/3، مستطيل على الحافة)، Cropper، Cleaner، Validation.
- تكامل: الاختبار الجماعي على الجوال على الوضعين A و B مع تقرير CSV.

## المخاطر
- تحويل الإحداثيات (أخطر جزء — البرومت §5.2). ZSL لا يعمل مع الفلاش ON/AUTO.
- الفجوة بين البيانات الاصطناعية والحقيقية. شاشات SMART MT10 الباهتة (قد نحتاج قفل التعريض على المستطيل).
- حجم ONNX Runtime (~5–7MB تقديراً — يُقاس)؛ البديل LiteRT.
