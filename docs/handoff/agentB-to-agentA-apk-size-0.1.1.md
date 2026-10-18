# من وكيل B إلى وكيل A — نتيجة برومت حجم الـ APK (0.1.1)

رد على `docs/prompts/agentB-apk-size.md`. التقرير الكامل بالأرقام: `docs/apk-size-report.md`.

## باختصار
- **منشور:** GitHub Release `v0.1.1` (pre-release) = **ملف واحد فقط** `almaham-meter-0.1.1-arm64.apk`، **37,849,126 B**، sha256 `9eaf497eaa1d48bbf83f9ab2a1684f945ff6f8756042844dfc4bd12b27145e5c` + `SHA256SUMS`.
  المالك طلب أثناء العمل: «إصدار واحد فقط، تلفون 64، بقية الإصدارات ما أحتاجها الآن». لذلك **armv7 و bench بُنيا وقيسا لكن لم يُنشرا**.
- **لم أصل لـ 20 MB في الملف المنشور.** السبب بالرقم: ORT 1.31.0 = 34,208,672 B من 37,849,126.
- **ORT المصغّر نجح:** `libonnxruntime.so` arm64 = **2,455,568 B**. لم أدمجه لأنه يحتاج تعديلاً في ملفك (تحت).
- **لم أغيّر أي ملف لك.** لا `MeterReader.kt` ولا `MeterOcrConfig.kt` ولا `app/meterocr/build.gradle.kts`.

## الخطوات مقابل البرومت
| # | المطلوب | الحالة | الرقم |
|---|---|---|---|
| 1 | flavors field/bench + MlKitBaseline | ✅ | bench-arm64 50,659,989 B؛ field بدون ML Kit |
| 2أ | الأساس ORT 1.31 | ✅ مقاس | 34,208,672 B (arm64)، 24,181,976 (v7a) |
| 2ب | ORT مصغّر | ✅ بُني arm64، ❌ لم يُدمج | .so 2,455,568 B، AAR 1,252,102 B |
| 2ج | LiteRT | ✅ قياس فقط | runtime 4,320,480 B؛ نماذج fp32 874,064 + 872,372؛ 10/10 نفس القراءة |
| 3 | ABI splits | ✅ | arm64 + v7a (x86_64 فقط بـ `-Pemulator`) |
| 4 | R8 + proguard | ✅ بُني | dex 12,316,158 ← 1,380,132 B مضغوط |
| 4 | التحقق على المحاكي بعد R8 | ❌ **لم يُعمل** | المحاكي متوقف (امتلاء القرص). المالك سيجرب على جواله |
| 5 | لا ملف > 20 MB | ❌ | 37,849,126 B — السبب أعلاه |
| — | release v0.1.1 | ✅ ملف واحد | بطلب المالك |
| — | CHANGELOG/STATUS | ✅ سطر لكل خطوة، لم أحذف شيئاً من أسطرك | |

## التطابق الرقمي (10 صور، الوضع A، `lab/litert_parity.py`)
max|Δ| مقابل ORT 1.31 + `.onnx`:
- LiteRT fp32: peaks loc 0.1032 / rd 0.0418، size ≤ 8.0e-4، offset ≤ 4.8e-5 — **10/10 نفس القراءة**.
- `.ort` (ORT 1.31 و 1.23.2): peaks نفس 0.1032 / 0.0418، size ≤ 1.2e-5، offset ≤ 4.8e-7 — **10/10**.
- فرق peaks سببه NMS داخل نموذجك (MaxPool+Equal) عند قمم متعادلة؛ يظهر بنفس الحجم بين `.onnx` و`.ort` على نفس المحرك، فهو ليس خطأ تحويل. القيم ≤ 0.103 (تحت عتبات 0.25/0.30).
- **حدود:** decode+assemble فقط، بدون lattice re-read و segverify. ليس الـ49 كاملة.

## المطلوب منك (للوصول ~5 MB)
1. **موافقتك** أن أغيّر هذا السطر في `app/meterocr/build.gradle.kts`:
   ```
   api("com.microsoft.onnxruntime:onnxruntime-android:1.31.0")
   →
   api(files("../../artifacts/ort-minimal/onnxruntime-minimal-1.23.2-arm64.aar"))
   ```
   و `noCompress += listOf("onnx", "ort")`.
2. **في ملفك** `MeterOcrConfig.kt` سطر 9 و10: `.onnx` ← `.ort`. وإضافة `line_locator.ort` و `digit_reader.ort` في `assets/models/`. أمر التحويل (ORT **1.23.2** ليطابق المحرك):
   `python -m onnxruntime.tools.convert_onnx_models_to_ort models/ --optimization_style Fixed --enable_type_reduction`
3. **ملاحظتان:**
   - المحرك المصغّر من مصدر **v1.23.2** وليس 1.31.0. واجهة Java التي تستعملها (OrtEnvironment، OrtSession، SessionOptions، OnnxTensor) موجودة.
   - المصغّر فيه **فقط** العوامل الحالية (`benchmark/results/size/ort_required_operators_and_types.config`). أي عامل جديد بعد إعادة التدريب = إعادة بناء المحرك (~15 دقيقة، `artifacts/ort-minimal/run_build.sh`).
4. **حجم متوقع بعد الدمج** (حساب من مكوّنات مقاسة، ليس ملفاً مبنياً): ≈ 4.6 MB. سأكتب الرقم الحقيقي بعد البناء.

## ملفاتي في هذه الخطوة
- `app/demo/build.gradle.kts`، `app/demo/proguard-rules.pro`
- `app/demo/src/main/.../MlKitBaseline.kt`، `src/bench/.../MlKitBaselineFactory.kt`، `src/field/.../MlKitBaselineFactory.kt`، `BatchBenchmark.kt`
- `lab/litert_parity.py`
- `benchmark/results/size/*`
- `artifacts/ort-minimal/*`
- `docs/apk-size-report.md`، هذا الملف، §2 في `docs/release-0.1.0.md`، `docs/manifests/app-build-record.md`
- commits: `9d9ecb8`، `0ff0227`، `e659e43`، + commit التوثيق هذا.
