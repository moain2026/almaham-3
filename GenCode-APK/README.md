# GenCode-APK — دليل وكيل التحويل إلى APK

**مَن أنا:** وكيل B، اسمي في هذا المجلد **«جين كود APK» (GenCode-APK)**. أنا **وكيل التحويل**: آخذ الكود والنماذج الموجودة في المستودع وأحوّلها إلى ملف APK يتثبّت على الجوال، وأنشره على GitHub Release مع الهاش والبصمة. لا أدرّب نماذج ولا أغيّر طريقة القراءة.
- ملكيتي حسب `docs/agent-contract.md`: `app/demo/**`، ملفات البناء (`build.gradle.kts`، `settings.gradle.kts`، `proguard-rules.pro`)، `artifacts/ort-minimal/**`، و`ForensicReader.kt`.
- الباقي في `app/meterocr/**` لوكيل A. ألمسه فقط بموافقته المكتوبة في `docs/prompts/`.
- التاريخ: 2026-10-18. المستودع: `moain2026/almaham-3`، فرع `genspark_ai_developer`.

**حالياً: APK واحد فقط، لجوالات ARM64 (arm64-v8a).** لا armv7 ولا x86 ولا bench.

ملفات هذا المجلد:
| الملف | ماذا فيه |
|---|---|
| `README.md` | هذا الدليل: لماذا الحجم صغير، البيئة، البناء خطوة بخطوة، كيف يعمل التطبيق، ما يعمل وما لا يعمل |
| `build.sh` | سكربت واحد يبني الـ APK من الصفر ويطبع الهاش والبصمة |
| `HASHES.md` | كل الهاشات والبصمات لكل الإصدارات وكل الملفات المهمة |
| `SHA256SUMS-all-releases.txt` | sha256 لكل APK منشور |
| `apk-0.2.1-inside.sha256` | sha256 للملفات **داخل** APK 0.2.1 (النماذج، المحرك، الكود) |
| `REBUILD-ORT-MINIMAL.md` | كيف يُعاد بناء محرك ONNX Runtime المصغّر إذا تغيّرت عوامل النموذج |
| `LOG.md` | سجل كل ما فعلته بالترتيب، مع الـ commits |
| `AGENT-A-REPORT-2026-10-18.md` | تقرير وكيل A نهاية الجولة (PLAN.md، 19/46، المطلوب من المالك) + تعليقي: ثبّت v0.2.1 لا v0.2.0 |

---

## 1. الإصدار الحالي
| | |
|---|---|
| الإصدار | **0.2.1** (versionCode 4) |
| الرابط | https://github.com/moain2026/almaham-3/releases/download/v0.2.1/almaham-meter-0.2.1-arm64.apk |
| الحجم | **7,682,409 بايت** |
| sha256 | `8940f7372997f39dcaab120ec84c2afa2ec4865b277ad63a12bacb9cb2be3b3f` |
| بصمة شهادة التوقيع (SHA-256) | `04f129a99c0a5b0c5bec5876ebbc308bd77e47466f9260d9e0f179ff61a374a3` |
| التوقيع | مفتاح **debug** (`CN=Android Debug`): **للتجربة فقط** |
| المعمارية | arm64-v8a فقط، أندرويد 7.0+ (minSdk 24)، targetSdk 35 |
| الصلاحيات | `CAMERA` فقط |
| دقة القراءة (مقاسة على 46 صورة، سيرفر) | 19/46 (41.3%) |

---

## 2. لماذا الحجم صغير لهذه الدرجة؟ (92.7 MB ← 7.7 MB)
**الجواب القصير:** الحجم القديم كان تقريباً كله **مكتبات جاهزة** فيها أشياء لا نستعملها. نماذجنا نفسها صغيرة (حوالي 0.9 MB لكل نموذج). حذفت كل ما لا يستعمله التطبيق.

| الخطوة | ماذا حذفت | الحجم بعدها (بايت) |
|---|---|---|
| البداية 0.1.0 | — | 92,724,341 |
| ① نسخة لكل معالج (ABI split) | كانت 3 نسخ من كل مكتبة في ملف واحد (arm64 + armv7 + x86_64). الآن نسخة arm64 فقط | ↓ |
| ② حذف ML Kit من نسخة field | مكتبة Google للمقارنة فقط (11,064,544 B لـ arm64 + أصولها) | ↓ |
| ③ R8 (تقليص الكود) | الكود المجمّع نزل من 45,941,900 إلى 2,934,152 بايت (غير مضغوط): R8 يحذف كل دالة وصنف لا يُستدعى | **37,849,126** (0.1.1) |
| ④ **ONNX Runtime مصغّر** | المحرك الكامل `libonnxruntime.so` = **34,208,672 B** فيه مئات العوامل (operators) لكل أنواع النماذج. بنيته من المصدر بـ **16 عاملاً فقط**، وهي ما يستعمله نموذجانا، ونوع float فقط، بلا exceptions ولا RTTI ولا ML ops. الناتج **2,455,560 B** (أصغر 14 مرة) | **7,682,029** (0.2.0) |
| النموذج الجديد ft4a | نفس الحجم تقريباً | **7,682,409** (0.2.1) |

**ما يوجد الآن داخل الـ APK** (غير مضغوط، `unzip -l`):
| بايت | الملف | ما هو |
|---|---|---|
| 2,909,396 | classes.dex | كل كود Kotlin بعد R8 (Compose، CameraX، تطبيقنا) |
| 2,455,560 | lib/arm64-v8a/libonnxruntime.so | المحرك المصغّر |
| 923,616 | assets/models/digit_reader.ort | نموذج قراءة الأرقام (يُستعمل) |
| 921,016 | assets/models/line_locator.ort | نموذج إيجاد سطر الأرقام (يُستعمل) |
| 871,141 | assets/models/digit_reader.onnx | نسخة onnx: **لا تُستعمل**، أبقيتها بأمر وكيل A |
| 868,554 | assets/models/line_locator.onnx | **لا تُستعمل** |
| 279,256 | resources.arsc | النصوص والموارد |
| 73,288 | lib/arm64-v8a/libonnxruntime4j_jni.so | جسر Java ↔ المحرك |

- **هل فقدنا شيئاً؟** لا. القراءة نفسها بالضبط: على الـ49 صورة كلها، المحرك المصغّر و`.ort` أعطيا **49/49 نتيجة متطابقة** مع المحرك الكامل و`.onnx` (القيمة والنص الخام والحالة والثقة). الملفات: `benchmark/results/size/parity49_*.json`.
- **الثمن:**
  1. المحرك المصغّر لا يقرأ إلا `.ort`.
  2. لا يدعم إلا عوامل النموذجين الحاليين. لو أضاف وكيل A عاملاً جديداً في نموذج مستقبلي، يجب إعادة بناء المحرك (`REBUILD-ORT-MINIMAL.md`).
  3. مبني لـ arm64 فقط.
- **توفير ممكن لاحقاً:** حذف ملفي `.onnx` يوفّر ≈1.58 MB، فيصير الحجم ≈6.1 MB. هذا ينتظر موافقة وكيل A.

---

## 3. البيئة التي بنيت فيها (مقاسة)
| | |
|---|---|
| النظام | Debian GNU/Linux 13 (trixie)، Linux 6.1.155 x86_64 |
| العتاد | 4 أنوية، 7 GB RAM، قرص 37 GB (كان ممتلئاً 91%، انتبه للمساحة) |
| Java | OpenJDK **17.0.2**، `JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64` |
| Gradle | **8.11.1** (من `app/gradle/wrapper`، يُنزَّل تلقائياً) |
| Android Gradle Plugin | **8.7.3** |
| Kotlin | **2.1.0** (+ compose plugin 2.1.0) |
| Android SDK | `/home/user/android-sdk`: platforms android-34/35/36، build-tools 30.0.3/34.0.0/**35.0.0**، NDK **27.0.12077973** |
| compileSdk / targetSdk / minSdk | 35 / 35 / 24 |
| مكتبات | CameraX 1.5.0، Compose BOM 2024.12.01، coroutines 1.9.0، exifinterface 1.3.7 |
| المحرك | ONNX Runtime **1.23.2 minimal** (MIT)، محلي في `artifacts/ort-minimal/maven/` |
| أدوات التحويل (Python) | Python 3.13، venv فيه `onnxruntime==1.23.2` (لتحويل `.onnx` ← `.ort`، ويجب أن يطابق إصدار المحرك) |
| لإعادة بناء المحرك فقط | cmake ≥ 3.28 (استعملت 4.4.4 من pip)، ninja، مصدر ORT v1.23.2 |
| الشبكة | Gradle يحتاج Google Maven + Maven Central أول مرة. المحرك المصغّر لا يحتاج شبكة |
| لا يوجد | محاكي arm64، KVM، `gh` CLI (النشر بـ GitHub API عبر curl) |

**ممنوع:** لا تحدّث Gradle/AGP/Kotlin/Java، فالإصدارات أعلاه مقفلة ومجرّبة. لا تبنِ بـ gradle في سندبوكس يجري فيه تدريب.

---

## 4. كيف أبني الـ APK خطوة بخطوة
الأسرع: `bash GenCode-APK/build.sh` (يعمل كل ما يلي ويطبع الهاش). أو يدوياً:

### 4.0 السحب
```bash
git clone https://github.com/moain2026/almaham-3.git && cd almaham-3
git checkout genspark_ai_developer
git pull --rebase origin genspark_ai_developer      # عدة وكلاء على نفس الفرع: اسحب قبل كل خطوة
```

### 4.1 النماذج: `.onnx` إلى `.ort` (كل مرة يتغيّر فيها النموذج)
وكيل A يضع النماذج الرسمية في `app/meterocr/src/main/assets/models/*.onnx` (commit يبدأ بـ `model:`). التطبيق يقرأ `.ort`، فيجب التحويل:
```bash
python3 -m venv ~/ort123env && ~/ort123env/bin/pip install onnxruntime==1.23.2 onnx numpy
mkdir -p /tmp/conv && cp app/meterocr/src/main/assets/models/*.onnx /tmp/conv/
~/ort123env/bin/python -m onnxruntime.tools.convert_onnx_models_to_ort /tmp/conv \
    --optimization_style Fixed --enable_type_reduction
cp /tmp/conv/*.ort app/meterocr/src/main/assets/models/
```
- **مهم:** إصدار onnxruntime في التحويل = **1.23.2** (نفس المحرك المصغّر). لا تحوّل بـ 1.31.
- قارن قائمة العوامل:
  ```bash
  diff <(grep -v '^#' /tmp/conv/required_operators_and_types.config) \
       <(grep -v '^#' benchmark/results/size/ort_required_operators_and_types.config)
  ```
  - فارغ: المحرك الحالي يكفي.
  - غير فارغ: أعد بناء المحرك (`REBUILD-ORT-MINIMAL.md`) وإلا سيتعطل التطبيق عند فتح النموذج.

### 4.2 التطابق (إلزامي قبل النشر)
```bash
cd lab
python3 ../scripts/parity49_ort.py /tmp/conv onnx /tmp/a.json            # ORT 1.31 كامل + .onnx (يحتاج torch+cv2)
~/ort123env/bin/pip install opencv-python-headless
~/ort123env/bin/python ../scripts/parity49_ort.py /tmp/conv ort /tmp/b.json  # ORT 1.23.2 + .ort
python3 -c "import json;a=json.load(open('/tmp/a.json'))['rows'];b=json.load(open('/tmp/b.json'))['rows'];print(sum(a[k]==b[k] for k in a),'/',len(a))"
```
**يجب 49/49.** إن اختلفت صورة واحدة: لا تنشر. الصور الـ49 في `data/photos` خارج git (رابط الصور في `STATUS.md`)، ولا تُرفع أبداً.

### 4.3 الإصدار
`app/demo/build.gradle.kts`: زِد `versionCode` بواحد وغيّر `versionName`.

### 4.4 البناء
```bash
cd app
echo "sdk.dir=$ANDROID_HOME" > local.properties          # مثلاً /home/user/android-sdk (الملف في .gitignore)
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
./gradlew --no-daemon :demo:testFieldDebugUnitTest :meterocr:testDebugUnitTest
./gradlew --no-daemon :demo:assembleFieldRelease
# الناتج:
ls -la demo/build/outputs/apk/field/release/demo-field-arm64-v8a-release.apk
```
مدة البناء تقريباً 45 ثانية مع الكاش، وأول مرة بضع دقائق.

**ماذا يحدث داخل `assembleFieldRelease` (التحويل من كود إلى APK):**
1. **Gradle** يقرأ `settings.gradle.kts` (الوحدتان `:meterocr` و`:demo` + مستودع Maven المحلي للمحرك).
2. **meterocr** (مكتبة): Kotlin ← bytecode، وتُجمَع مع الأصول (`assets/models/*`) ومع AAR المحرك (`libonnxruntime.so` + `libonnxruntime4j_jni.so` + أصناف `ai.onnxruntime.*`).
3. **demo** (التطبيق): Kotlin + Compose ← bytecode. يُدمج مع meterocr وCameraX وCompose.
4. **flavor `field`**: يأخذ `src/field/` (بدون ML Kit). نسخة `bench` تأخذ `src/bench/` (مع ML Kit).
5. **R8**: يحوّل كل الـ bytecode إلى `classes.dex` ويحذف غير المستعمل. القواعد في `app/demo/proguard-rules.pro` و`app/meterocr/consumer-rules.pro` تحمي `ai.onnxruntime.**` و`com.almaham.meterocr.**` و`androidx.camera.camera2.**` من الحذف، لأن المحرك يستدعيها من C عبر JNI بالاسم.
6. **shrinkResources**: يحذف الموارد غير المستعملة.
7. **ABI split**: `include("arm64-v8a")`، فلا تدخل إلا مكتبات arm64.
8. **التغليف**: zip فيه dex + `lib/arm64-v8a/*.so` + `assets/` + `resources.arsc` + `AndroidManifest.xml`. ملفات `.onnx`/`.ort` تبقى بلا ضغط إضافي (`noCompress`).
9. **zipalign + التوقيع**: بمفتاح debug `~/.android/debug.keystore` (Android Studio/Gradle ينشئه تلقائياً) بنظام APK Signature Scheme v2.

### 4.5 الفحص (اكتب المخرجات في ملاحظات الإصدار)
```bash
A=demo/build/outputs/apk/field/release/demo-field-arm64-v8a-release.apk
BT=$ANDROID_HOME/build-tools/35.0.0
$BT/aapt2 dump badging $A | grep -E "versionName|native-code"     # يجب: arm64-v8a فقط
$BT/aapt2 dump permissions $A                                     # يجب: CAMERA فقط
$BT/apksigner verify -v --print-certs $A                          # البصمة
unzip -l $A | sort -k1 -n -r | head -15
stat -c %s $A ; sha256sum $A
unzip -p $A assets/models/digit_reader.ort | sha256sum             # يطابق الملف في assets؟ (النموذج الصحيح دخل)
```

### 4.6 النشر
```bash
cp $A almaham-meter-X.Y.Z-arm64.apk && sha256sum almaham-meter-X.Y.Z-arm64.apk > SHA256SUMS
gh release create vX.Y.Z almaham-meter-X.Y.Z-arm64.apk SHA256SUMS --prerelease --title "..." --notes-file notes.md
```
بدون `gh`، أنشئ الإصدار بـ `POST https://api.github.com/repos/moain2026/almaham-3/releases` ثم ارفع بـ `POST https://uploads.github.com/repos/.../releases/<id>/assets?name=<file>` (طريقتي، `build.sh --publish`). التوكن من `setup_github_environment` في `~/.git-credentials`. **لا توكن في أي ملف أو commit. لا APK في git.**

### 4.7 التوثيق
سطر في `STATUS.md` و`CHANGELOG.md` (لا تحذف أسطر الآخرين)، و`docs/release-X.Y.Z.md`، وتحديث `HASHES.md` و`LOG.md` هنا. commit بعد كل خطوة، `git pull --rebase` قبل كل push. الـ commit الذي يغيّر الـ AAR يبدأ بـ `build(meterocr):`.

---

## 5. كيف يعمل التطبيق (بدقة)
**الوحدات:**
- `app/demo`: التطبيق والشاشات. `com.almaham.meterdemo`، ملكي.
- `app/meterocr`: محرك القراءة. `com.almaham.meterocr`، ملك وكيل A.

1. **الفتح** (`MainActivity.kt`): ينشئ `MeterReader` مرة واحدة ويستدعي `warmUp()` (يشغّل النموذجين على صورة رمادية فارغة كي لا تتأخر أول قراءة). الشاشة الأولى `EntryScreen`.
2. **الكاميرا** (`CameraScreen.kt`): CameraX تعرض المعاينة مع **مستطيل** يحركه المستخدم ويغيّر حجمه (`RectangleState.kt`). عند الضغط تُلتقط صورة JPEG كاملة الدقة في الذاكرة.
3. **القص** (`CapturePipeline.cropFromJpeg`): يحوّل المستطيل من إحداثيات الشاشة إلى إحداثيات الصورة (`RectGeometry`)، ويفك **منطقة المستطيل فقط** من الـ JPEG (`BitmapRegionDecoder`)، ثم يدوّرها حسب EXIF. **الصورة الكاملة لا تُحفظ على القرص.**
4. **القراءة** (`MeterReader.read`، المحرك):
   1. **المحدِّد** `line_locator.ort`: القص يُصغَّر مع حواف رمادية إلى 256×256 ← خريطة حرارية 64×64 ← أقوى سطر أرقام (`PeakDecoder`، عتبة 0.25).
   2. قص السطر مع هامش (18% أفقي، 45% رأسي) ← 448×64.
   3. **القارئ** `digit_reader.ort` ← خريطة 11 فئة (0–9 + فاصلة) 112×16 ← مرشحو الخانات (عتبة 0.30).
   4. **التجميع** (`ReadingAssembler`): ترتيب من اليسار، فصل الأرقام العشرية الصغيرة، شبكة 6 خانات، وإعادة قراءة الخانات الناقصة من الخريطة بعتبة 0.08.
   5. **تحقق 7 مقاطع** (`SegmentVerifier`): كل خانة تُفحص بالبكسلات.
   6. **القارئ الحتمي** (`ForensicReader`، ملكي): يقرأ نفس السطر بلا ذكاء اصطناعي (3 قنوات لون + تصويت).
   7. **التصويت** (`Vote`) بين العصبي والحتمي ← رقم + ثقة لكل خانة.
5. **العرض** (`EntryScreen`): الرقم في الخانة، **الخانات غير الواثقة ملوّنة**. المستخدم يصحح ويحفظ. الكسور لا تُقرأ (الجزء الصحيح فقط)، والأصفار في البداية تُحذف.
6. **الدليل** (`EvidenceImage`): صورة القص فقط، JPEG مضغوطة (هدف 80–200 KB)، في مجلد التطبيق الخاص. سجل الالتقاط في `CaptureLog.kt` (`captures_log.csv`).
7. **الاختبار الجماعي** (`BatchBenchmark.kt`): `adb shell am start -n com.almaham.meterdemo/.MainActivity --ez autobench true` يقرأ الصور من `/sdcard/Android/data/com.almaham.meterdemo/files/photos/` ويكتب `bench_<device>.csv`. في field لا يوجد ML Kit، فصفوفه تُتخطى.
8. **الخصوصية:** لا إنترنت ولا تحليلات ولا تيليمتري. الصلاحية الوحيدة الكاميرا. `allowBackup=false`.

---

## 6. ما يعمل وما لا يعمل (صراحة)
| | الحالة |
|---|---|
| البناء من الصفر بالأوامر أعلاه | ✅ يعمل (EXIT 0)، مُكرَّر عدة مرات بنفس الهاش لنفس المدخلات |
| المحرك المصغّر = المحرك الكامل في النتائج | ✅ 49/49 (على x86 بـ Python ORT 1.23.2، وليس `.so` arm64 نفسه) |
| الحجم ≤ 10 MB | ✅ 7,682,409 |
| الصلاحيات CAMERA فقط | ✅ (+ صلاحية androidx داخلية `DYNAMIC_RECEIVER_NOT_EXPORTED_PERMISSION` لا يراها المستخدم) |
| **تشغيل 0.2.x على جهاز** | ❌ **غير متحقق**: المحاكي هنا x86_64 بلا KVM، والمحرك arm64 فقط. جوال المالك أول جهاز |
| دقة القراءة | ⚠️ **19/46 (41%)** فقط. التطبيق يغلط كثيراً. المشكلة الأكبر إيجاد سطر الأرقام (`docs/research/multi-algo-2026-10-18.md`) |
| اختبار `ReadingAssemblerTest.tooManyDigits` | ❌ يفشل (44 اختبار، 1 فاشل) وكان يفشل قبل تعديلاتي. لوكيل A |
| `:demo:testFieldDebugUnitTest` | ✅ |
| armv7 / x86 / bench | ❌ غير منشورة (المحرك المصغّر arm64 فقط؛ لـ armv7 أعد بناءه بـ `--android_abi armeabi-v7a`) |
| مفتاح توقيع إنتاجي | ❌ debug فقط. للإنتاج: keystore خارج git + `signingConfigs` |
| الخوارزميات المتعددة (792 فحصاً) | ❌ ليست في التطبيق (في `lab/multi_algo.py` فقط) |

## 7. مشاكل واجهتها وحلولها
1. **`Direct local .aar file dependencies are not supported when building an AAR`**: AGP 8.7 يرفض `api(files("x.aar"))` في مكتبة. **الحل:** نفس الـ AAR في مستودع Maven محلي `artifacts/ort-minimal/maven/com/almaham/ort/onnxruntime-minimal-arm64/1.23.2/` (aar + pom)، و`maven { url = uri("../artifacts/ort-minimal/maven") }` في `app/settings.gradle.kts`، و`api("com.almaham.ort:onnxruntime-minimal-arm64:1.23.2")`.
2. **cmake 3.22 من SDK رُفض لبناء ORT** (يحتاج ≥ 3.28). **الحل:** `pip install cmake` (4.4.4) و`--cmake_path /usr/local/bin/cmake`.
3. **القرص امتلأ** أثناء بناء ORT. **الحل:** احذف `build_*` بعد نسخ الـ AAR، وكاش pip، وصور AVD.
4. **نموذج جديد وصل بعد البناء بثوانٍ** (0.2.0 ← 0.2.1). **الدرس:** `git pull` مباشرة قبل التحويل، وبعد البناء تحقق أن `unzip -p <apk> assets/models/*.ort | sha256sum` = الملف في المستودع، وأن `.ort` محوّل من `.onnx` الحالي.
5. **onnx2tf** يحاول تنزيل بيانات من GitHub (فشل). **الحل:** ملف npy محلي. (لـ LiteRT فقط، غير مستعمل في التطبيق.)
6. **محاكي API30**: الصور المدفوعة بـ root لا يقرأها التطبيق (scoped storage). لم يُحل؛ اقتراح: زر استيراد SAF.
