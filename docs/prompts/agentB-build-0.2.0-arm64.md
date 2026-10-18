# برومت لوكيل B — بناء الإصدار 0.2.0: ملف APK واحد (arm64) صغير بأحدث النماذج

> انسخ من هنا إلى النهاية وأعطه لوكيل B. كتبه وكيل A (2026-10-18) بعد قراءة `docs/handoff/agentB-to-agentA-apk-size-0.1.1.md` و`docs/apk-size-report.md`.

---

أنت وكيل B، مالك `app/demo/**` وملفات البناء. مهمتك: **إصدار 0.2.0 = ملف APK واحد فقط لجوالات arm64-v8a**، أصغر ما يمكن، بأحدث نماذج موجودة في المستودع، منشور على GitHub Release مع sha256. المالك يريد تجربته على جواله اليوم.

## 0. من أين تسحب
```bash
git clone https://github.com/moain2026/almaham-3.git && cd almaham-3
git checkout genspark_ai_developer
git pull --rebase origin genspark_ai_developer      # 4 وكلاء يدفعون على نفس الفرع — اسحب قبل كل خطوة
```
اقرأ أولاً بالترتيب: `STATUS.md` → `docs/release-0.1.0.md` → `docs/apk-size-report.md` → `app/meterocr/src/main/assets/models/MODEL_CARD.md` → `LESSONS.md`.

## 1. الموافقة التي كنت تنتظرها (من وكيل A)
**موافق** على تعديلاتك في ملفات `meterocr` التالية — وهذه فقط:
1. `app/meterocr/build.gradle.kts`: استبدال
   `api("com.microsoft.onnxruntime:onnxruntime-android:1.31.0")`
   بـ `api(files("../../artifacts/ort-minimal/onnxruntime-minimal-1.23.2-arm64.aar"))`
   وإضافة `androidResources { noCompress += listOf("onnx", "ort") }`.
2. `app/meterocr/src/main/java/com/almaham/meterocr/MeterOcrConfig.kt` **سطران فقط**:
   `LOCATOR_MODEL_ASSET = "models/line_locator.ort"` و`READER_MODEL_ASSET = "models/digit_reader.ort"`.
3. إضافة ملفي `.ort` إلى `app/meterocr/src/main/assets/models/` (بجانب `.onnx`، لا تحذف `.onnx` — يستعملها `lab/eval_e2e.py`).
4. `app/meterocr/src/main/AndroidManifest.xml`: تأكد أن إزالة INTERNET/ACCESS_NETWORK_STATE/التيليمتري ما زالت تعمل مع الـ AAR المصغّر (قد لا يعلنها أصلاً — تحقق بـ `aapt2 dump permissions`؛ المطلوب: **CAMERA فقط**).

**ممنوع** لمس أي ملف آخر في `app/meterocr/**` (`MeterReader.kt`, `ReadingAssembler.kt`, `Vote.kt`, `SegmentVerifier.kt`, ...) أو أي شيء في `lab/**`. إن احتجت تعديلاً فيها: اكتب الطلب في `docs/handoff/` وتوقف.

## 2. النماذج — استعمل الأحدث في المستودع، لا تدرّب شيئاً
- الملفان الرسميان دائماً: `app/meterocr/src/main/assets/models/{line_locator,digit_reader}.onnx` + `MODEL_CARD.md` (آخر من دفعهما يكتب الأرقام). بعد `git pull` اقرأ MODEL_CARD واكتب أرقامه في ملاحظات الإصدار كما هي.
- حوّلهما إلى `.ort` بنفس الأمر الذي استعملته في التقرير (ORT 1.23.2، `--optimization_style Fixed --enable_type_reduction`). **تحذير:** إن تغيّر النموذج (commit جديد ببادئة `model:`) فقد تتغير مجموعة العوامل ⇒ أعد توليد `required_operators_and_types.config` وقارنه بالقديم؛ إن اختلف، أعد بناء الـ AAR المصغّر بـ `artifacts/ort-minimal/run_build.sh` قبل البناء.
- **تحقق التطابق إلزامي قبل النشر:** `lab/litert_parity.py` أو ما يعادله: الـ `.ort` على ORT المصغّر يعطي نفس القراءة على **الـ49 صورة كلها** (الوضع A) مقارنةً بـ `.onnx` على ORT الكامل. اكتب العدد (مثلاً 46/46) في التقرير. إن اختلفت صورة واحدة، لا تنشر — اكتب أيّها ولماذا.

## 3. البناء
```bash
cd app && echo "sdk.dir=$ANDROID_HOME" > local.properties
JAVA_HOME=<jdk17> ./gradlew :meterocr:testDebugUnitTest :demo:testDebugUnitTest      # يجب 0 فاشل (كان 49 اختباراً)
JAVA_HOME=<jdk17> ./gradlew :demo:assembleFieldRelease                                   # نكهة field (بلا ML Kit)، arm64 فقط
```
- `versionCode = 3`, `versionName = "0.2.0"`.
- التوقيع: مفتاح debug مقبول مؤقتاً (اكتب ذلك صراحة في الملاحظات). **لا تُنشئ keystore جديداً وتضعه في git.**
- `splits.abi`: arm64-v8a فقط لهذا الإصدار (المالك: «إصدار واحد، تلفون 64»). لا تبنِ v7a ولا bench ولا x86.
- R8 مفعّل كما في 0.1.1. **التحقق بعد R8 إلزامي** هذه المرة: ثبّت على المحاكي (`-Pemulator` لبناء x86_64 محلي للفحص فقط، لا يُنشر) وشغّل `--ez autobench true` على الـ49 حتى النهاية؛ إن كسر R8 شيئاً (انعكاس في ORT/CameraX) أصلح `proguard-rules.pro`. إن تعذّر المحاكي (قرص/ذاكرة)، وثّق السبب بالضبط واكتب «غير متحقق على جهاز» في الملاحظات — لا تخفِه.

## 4. التحقق قبل النشر (كلها بأوامر، اكتب المخرجات)
```bash
aapt2 dump badging <apk> | grep -E "versionName|native-code"     # 0.2.0 ، arm64-v8a فقط
aapt2 dump permissions <apk>                                     # CAMERA فقط
unzip -l <apk> | sort -k1 -n -r | head -15                        # أكبر 15 ملفاً — يذهب للتقرير
stat -c %s <apk> ; sha256sum <apk>
```
الهدف: **≤ 10 MB** (المتوقع من أرقامك: dex 1.4 + ORT مصغّر 2.5 + نماذج 1.7 + باقي ≈ 6 MB). إن تجاوزت 10 MB اكتب الرقم وسببه بالبايت — لا تقرّب.

## 5. النشر
```bash
gh release create v0.2.0 almaham-meter-0.2.0-arm64.apk SHA256SUMS --prerelease \
  --title "0.2.0 — تجربة (arm64، ملف واحد)" --notes-file /tmp/notes.md
```
ملاحظات الإصدار (`/tmp/notes.md`) تحتوي حرفياً: الحجم بالبايت، sha256، «موقّع بمفتاح debug — للتجربة فقط»، صلاحية CAMERA فقط، أرقام MODEL_CARD كما هي (مطابقة كاملة x/46، غلط-وواثق، المحدِّد)، نتيجة التطابق `.ort` (x/46)، هل تُحقق على محاكي بعد R8 أم لا، وأمر التثبيت `adb install -r`.
**لا تضع الـ APK في git** (`dist/*.apk` متجاهل). الـ AAR المصغّر (1.25 MB) مقبول في `artifacts/`.

## 6. التوثيق (إلزامي، بعد كل خطوة لا في النهاية)
- `docs/release-0.2.0.md`: ما تغيّر عن 0.1.1، جدول الحجم قبل/بعد بالبايت، التحققات، ما لم يُتحقق.
- `docs/apk-size-report.md`: أضف قسم 0.2.0.
- `CHANGELOG.md` + `STATUS.md`: سطر لكل خطوة بتوقيت. لا تحذف أسطر الآخرين.
- commit بعد كل خطوة، `git pull --rebase` قبل كل push. رسالة الـ commit الذي يغيّر الـ AAR تبدأ بـ `build(meterocr):` ليراها وكيل A.

## 7. ما لا تفعله
- لا تدرّب نماذج، لا تلمس `lab/**`، لا تعدّل `benchmark/data/**`، لا تضيف تسميات.
- لا تلمس الصور الـ49 ولا تنشرها ولا ترفعها لأي خدمة.
- لا تضيف أي اعتماد شبكي/تحليلات/تيليمتري. لا AGPL/GPL (ممنوع Ultralytics، نموذج ERP).
- لا تغيّر سلوك القراءة (الأرقام، الكسور، الألوان، صورة الدليل) — هذا الإصدار «تصغير + أحدث نماذج» فقط.
- لا gradle في نفس السندبوكس الذي يعمل فيه تدريب وكيل A أو T (ينهار التدريب). إن كنت في سندبوكس مستقل فلا مشكلة.
- لا توكنات/كلمات مرور في الملفات أو في رسائل الـ commit.

## 8. التسليم لوكيل A
عند الانتهاء اكتب `docs/handoff/agentB-to-agentA-0.2.0.md`: رابط الـ Release، الحجم، sha256، نتيجة التطابق، ما تغيّر في `meterocr` (الأسطر بالضبط)، وأي شيء لم يُتحقق. وكيل A سيعيد قياس `eval_e2e` على نفس النماذج ويؤكد الأرقام.
