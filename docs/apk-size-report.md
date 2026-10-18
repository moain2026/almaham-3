# تقرير حجم الـ APK — إصدار 0.1.1 (وكيل B)

تنفيذ `docs/prompts/agentB-apk-size.md` (وكيل A، commit `5d9ede8`). **كل الأرقام بالبايت، مقاسة، لا تقديرات.**
الجهاز: سندبوكس Linux x86_64 (4 أنوية، 7 GB RAM)، JDK 17، AGP 8.7.3، Gradle 8.11.1، NDK 27.0.12077973، build-tools 35.0.0.

## 0. الخلاصة
| | النتيجة |
|---|---|
| ما نُشر | **ملف واحد** `almaham-meter-0.1.1-arm64.apk` = **37,849,126 B** (طلب المالك: نسخة arm64 فقط للتجربة) |
| الهدف ≤ 20 MB | **لم يتحقق في الملف المنشور.** السبب: ONNX Runtime 1.31.0 الكامل = 34,208,672 B (90% من الملف) |
| الطريق إلى ~5 MB | ORT المصغّر بُني فعلاً: `libonnxruntime.so` = **2,455,568 B** (بدل 34,208,672). يحتاج نماذج `.ort` + تعديل سطرين في `MeterOcrConfig.kt` (ملك وكيل A) — §4 |
| فقدان وظيفة؟ | لا في الملف المنشور: نفس المحرك 1.31.0 ونفس النماذج `.onnx` بالبايت. ML Kit أُزيل من field فقط (كان للمقارنة) |
| تشغيل بعد R8 | **لم يُجرّب على محاكي ولا جوال بعد** (المحاكي متوقف لنقص القرص) — مطلوب من المالك: تثبيت ← التقاط ← قراءة |

## 1. طريقة القياس
- حجم الملف: `stat -c%s <apk>`.
- المكوّنات: `unzip -l <apk>` + سكربت zipfile يجمع الحجم المضغوط/غير المضغوط لكل فئة (lib/*.so، classes*.dex، assets/models، res).
- المعمارية والإصدار: `aapt2 dump badging <apk>` ← `native-code: 'arm64-v8a'`، `versionName='0.1.1'`، `versionCode='2'`.
- التوقيع: `apksigner verify --print-certs` ← `CN=Android Debug` (مفتاح تجريبي).
- البصمة: `sha256sum`.

## 2. الجدول قبل/بعد
| الخطوة | الملف | البايت | sha256 |
|---|---|---|---|
| (0) الأساس 0.1.0 release universal (arm64+v7a+x86_64، ML Kit، بلا R8) | demo-release.apk | 92,724,341 (غير مضغوط 126,722,072) | `87c704ad…080201` |
| (1) flavors + R8 + ABI splits | field-arm64 | **37,849,126** | `9eaf497eaa1d48bbf83f9ab2a1684f945ff6f8756042844dfc4bd12b27145e5c` |
| | field-armv7 (بُني، **لم يُنشر**) | 27,787,924 | `64e1788f…1121db` |
| | bench-arm64 (بُني، **لم يُنشر**) | 50,659,989 | `7e84ab75…3307a` |
| | field-x86_64 (بُني للمحاكي، **لم يُنشر**) | 44,501,031 | `d9f3b8d3…eff0cf` |

### مكوّنات الأساس (مضغوط داخل الـ APK)
| المكوّن | البايت |
|---|---|
| ORT arm64 `libonnxruntime.so` | 34,208,672 |
| ORT armeabi-v7a | 24,181,976 |
| dex (غير مضغوط 45,941,900) | 12,316,158 |
| ML Kit .so arm64 | 11,064,544 |
| ML Kit .so v7a | 6,781,940 |
| نماذجنا `assets/models/*.onnx` | 1,569,841 |
| أصول أخرى (ML Kit) | 1,283,539 |
| res | 933,530 |

### مكوّنات field-arm64 بعد الخطوة (1)
| المكوّن | البايت |
|---|---|
| ORT `libonnxruntime.so` | 34,208,672 |
| نماذجنا | 1,569,841 (digit_reader.onnx 871,141 + line_locator.onnx 868,554 غير مضغوطة) |
| dex بعد R8 (غير مضغوط 2,934,152) | 1,380,132 |
| res | 459,643 |
| `libonnxruntime4j_jni.so` | 92,064 |

## 3. ما عُمل (ملفات وكيل B فقط)
1. **flavors** (`app/demo/build.gradle.kts`): بُعد `use` = `field` (بلا ML Kit) و `bench` (مع ML Kit، `versionNameSuffix "-bench"`). `com.google.mlkit:text-recognition:16.0.1` صار `benchImplementation`.
   - `MlKitBaseline.kt` (واجهة في main)، `src/bench/.../MlKitBaselineFactory.kt` (ML Kit حقيقي)، `src/field/.../MlKitBaselineFactory.kt` (`available=false`).
   - `BatchBenchmark.kt`: صفوف ML Kit تُتخطّى في field، بقية الصفوف كما هي.
2. **R8**: `isMinifyEnabled=true`، `isShrinkResources=true`، `proguard-android-optimize.txt` + `proguard-rules.pro`:
   `-keep class ai.onnxruntime.** { *; }`، `-keep class com.almaham.meterocr.** { *; }`، `-keep class androidx.camera.camera2.** { *; }`، dontwarn لـ camera/mlkit/onnxruntime.
3. **ABI splits**: `reset()` + `include("arm64-v8a","armeabi-v7a")`، `isUniversalApk=false`. x86_64 فقط مع `-Pemulator`.
4. versionCode 2، versionName 0.1.1.
- أمر البناء: `cd app && JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 ./gradlew --no-daemon :demo:assembleFieldRelease` — نجح (EXIT 0). البناء قابل للتكرار: بناءان منفصلان أعطيا نفس sha256.
- اختبارات الوحدات `:demo:testFieldDebugUnitTest` ناجحة.

## 4. ONNX Runtime — المحاولات
### (أ) الأساس 1.31.0 = 34,208,672 B لـ arm64 (مقاس أعلاه).
### (ب) بناء مصغّر — **نجح البناء، لم يُدمج**
- الأوامر:
  1. `python -m onnxruntime.tools.convert_onnx_models_to_ort models/ --optimization_style Fixed --enable_type_reduction` (بـ ORT 1.23.2 ليطابق المصدر) ← `benchmark/results/size/ort_required_operators_and_types.config`.
     العوامل: Conv(11) MaxPool(12) Cast Clip Equal ReduceMean Resize Sqrt Transpose(13) Add Div Mul Sub(14) com.microsoft FusedConv — كلها float فقط.
  2. `tools/ci_build/build.py --config MinSizeRel --android --android_abi arm64-v8a --android_api 24 --minimal_build extended --include_ops_by_config <config> --disable_exceptions --disable_rtti --disable_ml_ops --enable_reduced_operator_type_support --build_shared_lib --build_java --skip_tests --parallel 3` (السكربت كامل: `artifacts/ort-minimal/run_build.sh`).
- النتيجة (arm64): `libonnxruntime.so` = **2,455,568 B** (مضغوط gzip -9: 976,224)، `libonnxruntime4j_jni.so` = 96,832، الـ AAR = 1,252,102 B
  ← `artifacts/ort-minimal/onnxruntime-minimal-1.23.2-arm64.aar` sha256 `877286fb0b55f19571c472b52ab1a81ded295ef36cffabc5e7af2429082299b6`.
- مدة البناء ≈ 15 دقيقة (09:44→09:59 UTC)، 1023 خطوة.
- **عثرات موثّقة:**
  1. cmake الخاص بـ SDK (3.22) رُفض — ORT يحتاج ≥ 3.28. الحل: cmake 4.4.4 من pip.
  2. القرص امتلأ (37 GB) آخر البناء ففشلت خطوة اختبار الـ AAR (`No space left on device`) — **بعد** إنتاج الـ AAR و`.so`. حُرّرت مساحة بحذف مجلد البناء.
  3. بدء بناء armeabi-v7a ثم **أُوقف** بطلب المالك (نسخة arm64 فقط).
- **لماذا لم يُدمج في الملف المنشور:**
  1. البناء المصغّر **يقرأ صيغة `.ort` فقط** وليس `.onnx`. `MeterOcrConfig.kt` (ملك A) يحمّل `models/*.onnx`.
  2. المصدر المتاح v1.23.2 بينما التطبيق على 1.31.0. واجهة Java نفسها (`OrtEnvironment`/`OrtSession`/`OnnxTensor` — كل ما يستعمله `MeterReader.kt`) موجودة في 1.23.2.
  3. شرط «تحقق على المحاكي بعد التقليص» لم يتحقق بعد.
- **الحجم المتوقع بعد الدمج (حساب من مكوّنات مقاسة، ليس ملفاً مبنياً):** 37,849,126 − 34,208,672 + ~976,224 ≈ 4.6 MB تقريباً. **الرقم الحقيقي يُكتب بعد البناء الفعلي.**
### (ج) LiteRT عبر onnx2tf — قياس فقط، لم يُغيَّر `MeterReader.kt`
- التحويل: `onnx2tf -i <m>.onnx -o tfl/<m> -kat image -osd` (TF 2.21.0، onnx2tf من pip). ملاحظة: onnx2tf يحاول تنزيل بيانات معايرة من GitHub؛ أعطيته ملف npy عشوائي محلياً (للتحويل فقط).
- الأحجام: digit_reader float32 874,064 / float16 469,448؛ line_locator float32 872,372 / float16 469,564.
- runtime LiteRT 1.4.0 (`com.google.ai.edge.litert:litert:1.4.0` من Google Maven): `libtensorflowlite_jni.so` arm64 = 4,320,480 (gzip 1,745,600)، v7a = 2,867,532.
  ⇒ ORT المصغّر (2,455,568) **أصغر** من LiteRT (4,320,480) ولا يحتاج إعادة كتابة كود القراءة.

## 5. التطابق الرقمي (10 صور حقيقية، الوضع A، `lab/litert_parity.py`)
المرجع: ORT 1.31.0 + `.onnx` بنفس مدخلات `eval_e2e.py`. أول 10 صفوف من `ground_truth.csv`.
| | loc_peaks | loc_size | loc_offset | rd_peaks | rd_size | rd_offset | نفس القراءة |
|---|---|---|---|---|---|---|---|
| LiteRT float32 | 0.1032 | 1.0e-6 | 9.2e-7 | 0.0418 | 8.0e-4 | 4.8e-5 | **10/10** |
| `.ort` بـ ORT 1.31 | 0.1032 | 1.5e-8 | 1.3e-8 | 0.0418 | 1.2e-5 | 4.8e-7 | **10/10** |
| `.ort` بـ ORT 1.23.2 | 0.1032 | 1.5e-8 | 1.3e-8 | 0.0418 | 1.2e-5 | 4.8e-7 | **10/10** |

- **تفسير فرق peaks (0.10/0.04):** ليس خطأ تحويل. النموذج فيه NMS داخلي (MaxPool ثم Equal) يُبقي القيمة فقط عند القمة؛ عند بكسلين متساويين تقريباً يختار أحدهما. الفرق يظهر **بنفس الحجم حتى بين `.onnx` و`.ort` على نفس ORT**. عدد الخلايا المختلفة >1e-3: LiteRT 283/40,960 (loc) و493/197,120 (rd)؛ `.ort` 4/40,960 و297/197,120. والقيم المختلفة صغيرة (≤0.103، تحت عتبة 0.25 للمحدد، 0.042 تحت 0.30 للقارئ).
- **الحدود:** القراءة في الجدول من decode+assemble على خرائط القارئ فقط، بدون lattice re-read و segverify. ليس تقييماً كاملاً على 49 صورة.
- الملفات: `benchmark/results/size/parity_litert_fp32.json`، `parity_ort_format.json`، `parity_ort1232_format.json`.

## 6. ما يحتاجه وكيل A (السطر بالضبط)
لدمج ORT المصغّر:
1. `app/meterocr/build.gradle.kts` (أعدّله أنا إن وافقت):
   `api("com.microsoft.onnxruntime:onnxruntime-android:1.31.0")` ←
   `api(files("../../artifacts/ort-minimal/onnxruntime-minimal-1.23.2-arm64.aar"))`
   و `noCompress += listOf("onnx", "ort")`.
2. **ملفك أنت:** `MeterOcrConfig.kt` سطر 9 و10: `models/line_locator.onnx` ← `models/line_locator.ort`، و `digit_reader.onnx` ← `digit_reader.ort`. ووضع ملفي `.ort` في `assets/models/` (التحويل بالأمر في §4ب بـ ORT 1.23.2).
3. عند أي إعادة تدريب: إعادة توليد `.ort` + config + إعادة بناء ORT المصغّر (لو تغيّرت العوامل).
4. ملاحظة: `setOptimizationLevel(ALL_OPT)` مقبول في البناء المصغّر (النماذج محسّنة مسبقاً بـ `Fixed`).

## 7. ما لم يُعمل
- لم يُشغّل أي APK بعد R8 على محاكي أو جوال.
- لم يُبنَ ORT مصغّر لـ armeabi-v7a (أُوقف).
- armv7 و bench لم يُنشرا (طلب المالك).
- لا مفتاح توقيع إنتاجي (debug فقط).
