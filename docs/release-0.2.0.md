# إصدار 0.2.0 — تجربة، ملف واحد arm64 (وكيل B)

**من سوّى هذا:** وكيل B (مالك `app/demo/**` وملفات البناء)، 2026-10-18، تنفيذاً لـ `docs/prompts/agentB-build-0.2.0-arm64.md` (وكيل A، commit `fe5e9a3`).

## الرابط
- https://github.com/moain2026/almaham-3/releases/tag/v0.2.0 (pre-release)
- الملف: https://github.com/moain2026/almaham-3/releases/download/v0.2.0/almaham-meter-0.2.0-arm64.apk

## الأرقام (مقاسة)
| | |
|---|---|
| الحجم | **7,682,029 B** (`stat -c %s`) — الهدف ≤10 MB ✅ |
| sha256 | `c65869162744373c96d29cb9bcfdaa621b3623d062429d4c54b66e1b1c906e7d` |
| `aapt2 dump badging` | versionCode 3، versionName 0.2.0، native-code `arm64-v8a` فقط |
| `aapt2 dump permissions` | `CAMERA` فقط + `com.almaham.meterdemo.DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` (داخلية من androidx.core، تُضاف تلقائياً لكل تطبيق targetSdk ≥ 33، لا تظهر للمستخدم) |
| التوقيع | **مفتاح debug — للتجربة فقط** (`CN=Android Debug`). لا keystore في git |
| commit البناء | `f161ca1` |

### أكبر 15 ملفاً في الـ APK (`unzip -l | sort -k1 -n -r`، غير مضغوط)
| بايت | الملف |
|---|---|
| 2,909,396 | classes.dex |
| 2,455,560 | lib/arm64-v8a/libonnxruntime.so |
| 923,616 | assets/models/digit_reader.ort |
| 921,016 | assets/models/line_locator.ort |
| 871,141 | assets/models/digit_reader.onnx (لا يُستعمل، أُبقي بأمر وكيل A) |
| 868,554 | assets/models/line_locator.onnx (لا يُستعمل) |
| 279,256 | resources.arsc |
| 73,288 | lib/arm64-v8a/libonnxruntime4j_jni.so |
| 32,544 | lib/arm64-v8a/libimage_processing_util_jni.so |
| 18,653 | kotlin/kotlin.kotlin_builtins |
| 10,096 | lib/arm64-v8a/libandroidx.graphics.path.so |
| 6,204 | AndroidManifest.xml |
| 4,896 | lib/arm64-v8a/libsurface_util_jni.so |
| 3,989 | assets/dexopt/baseline.prof |
| المجموع غير المضغوط | 9,639,231 (487 ملف) |
- لو حُذف `.onnx` (غير مستعمل): يتوفّر ≈ 1,579,385 B مضغوطاً (790,806 + 788,579). يحتاج موافقة وكيل A.

## النماذج
أحدث ما في المستودع وقت البناء: `0735b8a` (reader) و `72d5c26` (locator). sha256: digit_reader.onnx `90dd48bf…`، line_locator.onnx `23b45a7c…`.
- التحويل: `python -m onnxruntime.tools.convert_onnx_models_to_ort <dir> --optimization_style Fixed --enable_type_reduction` (ORT 1.23.2).
- قائمة العوامل لم تتغيّر عن config 0.1.1 (diff فارغ) ⇒ الـ AAR نفسه، لا إعادة بناء.
- **MODEL_CARD.md كما هو** يذكر ft3a و 12/46؛ القياس الفعلي على النماذج الحالية = 17/46 (مطابق لرسالتي commit `0735b8a`/`72d5c26`). MODEL_CARD يحتاج تحديثاً من وكيل A.

## التطابق (إلزامي)
`scripts/parity49_ort.py` = `lab/eval_e2e.py` Engine، الوضع A، **كل الـ49**:
- المرجع: ORT 1.31.0 الكامل + `.onnx` ← exact 17/46.
- المصغّر: ORT 1.23.2 + `.ort` ← exact 17/46.
- **49/49 متطابقة** في (value, raw, status, confident)؛ 46/46 من المقروءة.
- الملفات: `benchmark/results/size/parity49_onnx_ort131.json`، `parity49_ort_minimal1232.json`.
- حدود: هذا تطابق المحرك على x86 (ORT 1.23.2 Python). ليس تشغيل libonnxruntime.so المصغّر على arm64 نفسه.

## البناء
```bash
cd app && echo "sdk.dir=/home/user/android-sdk" > local.properties
JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 ./gradlew --no-daemon :meterocr:testDebugUnitTest :demo:testFieldDebugUnitTest :demo:assembleFieldRelease
```
- `:demo:testFieldDebugUnitTest` ناجح؛ `:demo:assembleFieldRelease` ناجح (R8 مفعّل).
- `:meterocr:testDebugUnitTest`: 44، **1 فاشل**: `ReadingAssemblerTest.tooManyDigits` (متوقع TOO_MANY_DIGITS، الناتج OK). **يفشل أيضاً على HEAD بدون تعديلاتي** (`git stash` ثم الاختبار: 44/1 فاشل). الملف لوكيل A؛ لم ألمسه؛ مذكور في handoff.
- مشكلة واجهتها: AGP 8.7 يرفض `api(files("x.aar"))` داخل مكتبة (`Direct local .aar file dependencies are not supported when building an AAR`). الحل: نفس الـ AAR (نفس sha256 `877286fb…`) في مستودع Maven محلي `artifacts/ort-minimal/maven/` + سطر في `app/settings.gradle.kts`.

## التحقق بعد R8
**غير متحقق على جهاز.** السبب: المحرك المصغّر arm64 فقط، والمحاكي الوحيد في السندبوكس x86_64 بلا KVM؛ ولا محاكي arm64 قابل للتشغيل هنا.
ما فُحص ثابتاً: أصناف `ai.onnxruntime.*` (OrtEnvironment، OrtSession، OnnxTensor…) موجودة في classes.dex؛ نصوص `models/line_locator.ort` و `models/digit_reader.ort` موجودة؛ قواعد keep `ai.onnxruntime.**` و `com.almaham.meterocr.**` مطبّقة.
**التجربة الأولى على جهاز = جوال المالك.**

## سلوك القراءة
لم يتغيّر (تصغير + أحدث نماذج فقط). 17/46 في القياس — التطبيق سيغلط كثيراً. الخوارزميات المتعددة (`docs/research/multi-algo-2026-10-18.md`) **ليست** في هذا الإصدار.
