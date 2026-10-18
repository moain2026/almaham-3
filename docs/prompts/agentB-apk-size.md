# برومت لوكيل B — تصغير الـ APK من 89 MB إلى أقل من 20 MB (الإصدار 0.1.1)

> انسخ من هنا إلى النهاية وأعطه لوكيل B. (كتبه وكيل A بعد تشريح `v0.1.0` بالضبط.)

---

أنت وكيل B (مالك `app/demo/**` وملفات البناء). المطلوب: إصدار `0.1.1` من نفس التطبيق بحجم **≤ 20 MB** للجوال، بدون فقدان أي وظيفة من `docs/release-0.1.0.md`. اعمل على فرع `genspark_ai_developer`، ادفع كل خطوة.

## تشريح الـ 89 MB الحالية (مقاس من `almaham3-meterocr-0.1.0-release.apk`، غير مضغوط 126.8 MB)
| المكوّن | الحجم | القرار |
|---|---|---|
| `classes*.dex` (كود Java/Kotlin بلا تقليص) | **45.9 MB** | minify + shrink بـ R8 → متوقع 4–8 MB |
| `libonnxruntime.so` arm64 | 34.2 MB | نحتاجه لكن ننزل لنسخة مصغّرة (انظر 2) |
| `libonnxruntime.so` armeabi-v7a | 24.2 MB | **split APK لكل معمارية** — لا نشحن المعماريتين في ملف واحد |
| `libmlkit_google_ocr_pipeline.so` ×2 + نماذجه | 18.0 + 1.4 MB | **حذف من الإصدار**؛ يبقى في نكهة `bench` فقط |
| نماذجنا `digit_reader.onnx` + `line_locator.onnx` | 1.7 MB | يبقى (هذا المنتج) |
| الباقي (res, jni util, baseline.prof) | ~1.3 MB | يبقى |

## المهام بالترتيب
1. **نكهتان (product flavors) في `app/demo/build.gradle.kts`:**
   - `field` — بلا ML Kit نهائياً (الاعتماد `com.google.mlkit:text-recognition` يصبح `benchImplementation` فقط). كود `BatchBenchmark` الذي يستدعي ML Kit خلف واجهة `MlKitBaseline` بتنفيذين: حقيقي في `src/bench/`، وفارغ يرجع «غير متاح» في `src/field/`.
   - `bench` — كما هو الآن (مع ML Kit) لقياس خط الأساس على الجوال.
2. **ONNX Runtime:** جرّب بالترتيب وسجّل الحجم الفعلي لكل محاولة في الجدول أدناه:
   - (أ) `com.microsoft.onnxruntime:onnxruntime-android` نفس 1.31.0 لكن مع `packagingOptions` لا تغيّر شيئاً — هذا خط الأساس 34 MB.
   - (ب) **بناء مصغّر (minimal build) من ONNX Runtime** يحتوي فقط العوامل التي تستعملها نماذجنا: `python -m onnxruntime.tools.convert_onnx_models_to_ort assets/models/` ينتج `required_operators.config`؛ ثم `build.sh --android --minimal_build --include_ops_by_config required_operators.config --disable_exceptions --disable_rtti --android_abi arm64-v8a`. نماذجنا 213k معامل بعوامل بسيطة (Conv/BN/ReLU/MaxPool/Sigmoid/Concat) → المتوقع 3–6 MB لكل معمارية. رخصة MIT تبقى. إن فشل البناء في السندبوكس خلال ساعتين، وثّق السبب وانتقل لـ(ج).
   - (ج) بديل: **LiteRT / TensorFlow Lite** (Apache-2.0، ~2–4 MB) بتحويل `.onnx → .tflite` عبر `onnx2tf`؛ لكن هذا يغيّر `MeterReader.kt` (ملك وكيل A) — **لا تنفّذه دون موافقة وكيل A**، فقط قس الحجم والتطابق العددي (max |Δ| على 10 صور) وارفع تقريراً.
3. **split APK لكل معمارية** (`splits { abi { isEnable = true; include("arm64-v8a","armeabi-v7a"); isUniversalApk = false } }`) + حدّث `docs/release-0.1.0.md` §2 بأي ملف يثبّت المستخدم (الأغلب arm64).
4. **R8:** `isMinifyEnabled = true`, `isShrinkResources = true` في `release`، مع قواعد `proguard-rules.pro` لـ ONNX Runtime (`-keep class ai.onnxruntime.** { *; }`) وCameraX. **تحقق أن الاختبار الجماعي والقراءة يعملان بعد التقليص** (R8 يكسر الانعكاس) — شغّل على المحاكي كما فعلت في T1.
5. **لا تزد حجم الملف الواحد عن 20 MB** وإلا اشرح لماذا بالأرقام.
6. **لا تلمس** `app/meterocr/**` (عدا `build.gradle.kts` فيه لتبديل اعتماد ORT — أخبر وكيل A بالسطر).

## المخرجات المطلوبة
- `docs/apk-size-report.md`: جدول (قبل/بعد كل خطوة، بالبايت، بأمر القياس `aapt2`/`unzip -l`)، وما جُرّب وفشل.
- APKات `0.1.1` (field-arm64, field-armv7, bench-arm64) + `SHA256SUMS` على GitHub Release `v0.1.1` (أنشئه بـ `gh release create`، pre-release).
- تحديث `CHANGELOG.md` و`STATUS.md`.
- **أرقام فعلية فقط.** إن لم تصل لـ 20 MB اكتب الرقم الذي وصلت له وسببه.

## الهدف الواقعي
dex ~6 MB + ORT مصغّر ~5 MB + نماذج 1.7 MB + باقي 1.3 MB ≈ **14 MB** لـ arm64. إن بقي ORT الكامل (34 MB) فالحد الأدنى الممكن ≈ 43 MB — وهذا مقبول مؤقتاً لكن ليس الهدف.
