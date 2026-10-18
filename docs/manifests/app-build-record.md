# سجل بناء التطبيق والهاشات — 2026-10-18 (وكيل B)

هذا السجل يثبّت **بالضبط** ما بُني وقيس، حتى يمكن التحقق منه في أي سندبوكس لاحق. أعد التحقق بـ `bash scripts/verify_app_build.sh`.
قائمة sha256 لكل ملف متتبَّع في `app/` والأوزان وبيانات/نتائج القياس: [`sha256-repo-files.txt`](sha256-repo-files.txt) (100 ملف).

## 1. نقطة البناء
| البند | القيمة |
|---|---|
| المستودع / الفرع | `github.com/moain2026/almaham-3` / `genspark_ai_developer` |
| commit البناء (HEAD) | `609d816e7a41f88c3dd3d4f0e9ff5d1811bddcfd` (آخر commit يمسّ `app/`: `53a878c5f278d0fc22f0144680ccd3d48a154e03`) |
| الأمر | `cd app && ./gradlew --no-daemon :meterocr:testDebugUnitTest :demo:testDebugUnitTest :demo:assembleDebug` |
| النتيجة | BUILD SUCCESSFUL، **49 اختبار وحدات: 49 نجح، 0 فشل، 0 تخطّى** (جدول §4) |

## 2. الـ APK
| البند | القيمة |
|---|---|
| الملف | `app/demo/build/outputs/apk/debug/demo-debug.apk` (خارج git — ناتج بناء) |
| الحجم | 151,146,310 بايت |
| sha256 | `51671b8fd67dd884f189b083e29f14b3c4e1fc04c572ae4537b3fbd8734e9a85` |
| الحزمة | `com.almaham.meterdemo`، versionCode 1، versionName 0.1.0 |
| SDK | minSdk 24، targetSdk 35، compileSdk 35 |
| التوقيع | مفتاح Android Debug (`C=US, O=Android, CN=Android Debug`)، شهادة SHA-256 `04f129a99c0a5b0c5bec5876ebbc308bd77e47466f9260d9e0f179ff61a374a3`، SHA-1 `5ef72c6d7ccff60481bd15f4716c66399a00274d`، MD5 `f953a4976088a81ebd063c2ca3f9edf3` |
| ABIs | arm64-v8a، armeabi-v7a، **x86_64 (debug فقط للمحاكي)**؛ release = ARM فقط |
| مكتبات أصلية | `libonnxruntime.so` (arm64 34,208,672 / v7a 24,181,976 / x86_64 40,827,936 بايت) + `libonnxruntime4j_jni.so` |

> ملاحظة أمانة: هاش الـ debug APK **ليس قابلاً للتكرار** بين أجهزة (مفتاح debug محلي، طوابع). المرجع الثابت هو هاشات النماذج والملفات المصدرية أدناه + نجاح الاختبارات.
> بناء سابق (قبل commit A `ddc6742`، الساعة 08:32): sha256 `a1256026ff7e6f0b0054a97d88affccd892a055e3c7b040614771d202428f633`، 151,208,496 بايت — هو الذي ثُبّت على المحاكي في §5.

## 3. النماذج والأوزان المشحونة/المستعملة
| الملف | البايت | sha256 |
|---|---|---|
| `app/meterocr/src/main/assets/models/digit_reader.onnx` | 871,141 | `27e3866210f57d148c1aab1ad07080e8d003e85be0a8e9ded5dcf0e40b2d497b` |
| `app/meterocr/src/main/assets/models/line_locator.onnx` | 868,554 | `3018699719e61a8a7fafec4729e08edfc188caf4a322dff45cd9a4c826b1f3cd` |
| `lab/weights/reader_v1.pt` | — | `c00e4027bc3c78a9460e6deec09a183c3a96568680977716de6b3c11e82cf5bc` |
| `lab/weights/locator_v1.pt` | — | `70d400b0781973c8eb694f1a8521e323be41a6ed49660d67c38a0b73b406935e` |
| `lab/weights/locator_t.pt` | — | `1aea0ba42d1be327c8a49b361d8b74f2348340565be427a5efa969e1ec6589e6` |
| `lab/weights/rec_w075.pt` (SegReader قديم) | — | `d5e6183d4af40a6302f05e610fe5e7a8340114eb4a47a751e7fb5772869815d2` |
| `lab/weights/rec_w075_s1000.pt` | — | `506d7d5a5858b8e3c57ef6c199d301d6b21216f2c07c1d7e3b683246bd3f2d54` |
| `app/demo/src/main/assets/bench/ground_truth.csv` | — | `d0494d9d6af312be48a0998d5cd44c6b8acda3ba887997f28fb6d6fb4393359e` |
| `app/demo/src/main/assets/bench/meter_boxes.json` | — | `bf1eebee2d1871d8293d22926880d2b2c2d6eb5771baed5565b4cb162dc8f627` |

## 4. اختبارات الوحدات (عند HEAD أعلاه)
| الحزمة | tests | failures | errors | skipped |
|---|---|---|---|---|
| `com.almaham.meterocr.ForensicReaderTest` (وكيل B) | 4 | 0 | 0 | 0 |
| `com.almaham.meterocr.LatticeAndSegmentTest` | 3 | 0 | 0 | 0 |
| `com.almaham.meterocr.PeakDecoderTest` | 2 | 0 | 0 | 0 |
| `com.almaham.meterocr.ReadingAssemblerTest` | 12 | 0 | 0 | 0 |
| `com.almaham.meterocr.RectGeometryTest` | 18 | 0 | 0 | 0 |
| `com.almaham.meterocr.VoteTest` | 5 | 0 | 0 | 0 |
| `com.almaham.meterdemo.RectangleStateTest` | 5 | 0 | 0 | 0 |
| **المجموع** | **49** | 0 | 0 | 0 |

`ForensicReaderTest` يقارن Kotlin بـ Python على 5 قصوص ثابتة (`app/meterocr/src/test/resources/forensic/*.argb` + `expected.txt`، مولَّدة بـ
`lab/make_forensic_fixtures.py`): النص والحالة والفئة متطابقة، conf ±1e-6، الصندوق ±1e-5، المقاطع a..g متطابقة.

## 5. بيئة البناء والتشغيل (السندبوكس)
| البند | القيمة |
|---|---|
| المعالج / الذاكرة | x86_64، 4 أنوية، 7 GB RAM، **بلا GPU وبلا KVM** |
| JDK | OpenJDK 17.0.2 (`/usr/lib/jvm/java-17-openjdk-amd64`) |
| Gradle / AGP / Kotlin | Gradle 8.11.1 (wrapper)، AGP 8.7.3، Kotlin 2.1.0 |
| Android SDK | `/home/user/android-sdk`، platforms 34/35/36، build-tools 35.0.0 |
| المكتبات الرئيسية | CameraX 1.5.0، ONNX Runtime Android 1.31.0، Compose BOM 2024.12.01، ML Kit text-recognition 16.0.1 (للمقارنة فقط) |
| المحاكي | emulator 37.2.12، صورة `system-images;android-30;default;x86_64` rev 10، AVD `bench30` (pixel_4، 3072MB RAM، data 2GB) — الإعداد في [`avd-bench30-config.ini`](avd-bench30-config.ini) |
| تشغيل المحاكي | `emulator -avd bench30 -no-accel -no-window -no-audio -no-boot-anim -gpu swiftshader_indirect -no-snapshot -cores 3 -memory 3072` |
| Python (lab) | 3.13.14، OpenCV 5.0.0، NumPy 2.5.4 |

## 6. الصور الـ49 (اختبار فقط)
- المصدر: zip المالك (`rgwcFQnvhrHGBhdf.zip`) → `/home/user/incoming/correct_49_meter_photos/photos/` = `/home/user/work/meters.zip` (49/49 متطابقة)؛ في المستودع رابط رمزي `data/photos` (خارج git، ADR-0004).
- بصمة كل صورة: `benchmark/data/photos.sha256` (49 سطر) — **تحقّقت 49/49 مطابقة** بـ `diff` اليوم.
- بصمة القائمة كاملة: `sha256(sha256sum *.jpg) = 01c1b7e8cd634feff9bd1296dd206f51b8f6210a2d58e73218a9982fee25195c`.

## 7. نتائج قارئ B الحتمي (مرجع الأرقام)
`cd lab && python3 eval_forensic_reader.py` → `benchmark/results/engines/forensic_reader_lineL.json`:
exact 11/46 (DEV 6/10، HOLDOUT 5/36)؛ خانات conf≥0.8: 57، الصحيح 56 (98.25%)، HOLDOUT 97.06%؛ status OK 7 (6 صحيحة)؛ p50 409.1ms (Python، سندبوكس).
**القاعدة مُعايَرة على نفس الـ46 (in-sample).**

## 8. commits وكيل B في هذه الجلسة (كاملة)
| commit | الوقت (UTC) | المحتوى |
|---|---|---|
| `a4975000c4782d742e4616570f9dcacab6d3164d` | 06:59:06 | مختبر حتمي: v4/v5/v6 + 23 معالجة × 3 قرّاء (16/46 بالتصويت) |
| `a1f9b1b9db5918da835f8ae004edacf2cdcb98e3` | 07:55:36 | T2 `lab/forensic_reader.py` |
| `9432a4ff2825310d78a594d262b303104da62cc0` | 08:05:01 | T3 `benchmark/data/digit_boxes.json` |
| `7c1dcfe9de1b52891c0a8be25d1cd1b8409870f2` | 08:13:13 | T4 `ForensicReader.kt` + الاختبار |
| `19e7cd83387aff0ecd3546e53b655cb20eb6da55` | 08:39:53 | T1 إصلاحات demo + تقرير المحاكي |
| (على main) `bdf12076e273e699b808e2fb9fe80823f8854fe6` | — | تحليل Anyline/Laroca + SQL التصدير |
| (على main) `9f8a054` | — | النسخة الأصلية من مختبر الحتمي (نُقلت للفرع بـ cherry-pick = a497500) |

## 0.1.1 (وكيل B، 2026-10-18)
| الملف | البايت | sha256 | منشور |
|---|---|---|---|
| almaham-meter-0.1.1-arm64.apk (= demo-field-arm64-v8a-release.apk) | 37,849,126 | 9eaf497eaa1d48bbf83f9ab2a1684f945ff6f8756042844dfc4bd12b27145e5c | نعم، Release v0.1.1 (pre) |
| demo-field-armeabi-v7a-release.apk | 27,787,924 | 64e1788fcecbf8c23d9b8d3c2195f0fa654ccf47bc949e86c47286cbab1121db | لا |
| demo-bench-arm64-v8a-release.apk | 50,659,989 | 7e84ab75bfb337a96ae5881c405320c2aea66cbadcd69d2f1edb0c409df3307a | لا |
| onnxruntime-minimal-1.23.2-arm64.aar | 1,252,102 | 877286fb0b55f19571c472b52ab1a81ded295ef36cffabc5e7af2429082299b6 | في git: artifacts/ort-minimal/ |
الأمر: `./gradlew --no-daemon :demo:assembleFieldRelease`. التفاصيل: docs/apk-size-report.md.
