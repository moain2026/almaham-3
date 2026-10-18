# اختبار الجهاز — محاكي Android x86_64 API 30 (وكيل B، 2026-10-18)

> **ليس جوالاً حقيقياً.** السندبوكس بلا جوال وبلا KVM؛ المحاكي يعمل بمحاكاة برمجية كاملة (`-no-accel`) فهو أبطأ من أي جوال
> بعشرات المرات. **لا رقم زمن من هنا يصلح للحكم على p50/p95.** الغرض: التأكد أن التطبيق يُبنى ويُثبَّت ويفتح، واكتشاف الكراشات.

## الإعداد (قابل للتكرار)
```bash
cd app && echo "sdk.dir=/home/user/android-sdk" > local.properties
JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 ./gradlew :meterocr:testDebugUnitTest :demo:testDebugUnitTest :demo:assembleDebug
sdkmanager "emulator" "system-images;android-30;default;x86_64"
avdmanager create avd -n bench30 -k "system-images;android-30;default;x86_64" -d pixel_4
# config.ini: disk.dataPartition.size = 2147483648 (مساحة السندبوكس لا تكفي 6GB)
emulator -avd bench30 -no-accel -no-window -no-audio -gpu swiftshader_indirect -no-snapshot -cores 3 -memory 3072
adb install -r demo/build/outputs/apk/debug/demo-debug.apk
adb shell am start -n com.almaham.meterdemo/.MainActivity --ez autobench true   # يشغّل الاختبار الجماعي بلا لمس
```

## النتائج
| البند | النتيجة |
|---|---|
| البناء | ✅ `assembleDebug` ناجح؛ اختبارات الوحدات: meterocr 35 + ForensicReader 4 + demo 5 = **44 ناجحة، 0 فاشلة** |
| التثبيت والفتح | ✅ شاشة «إدخال القراءة» تظهر (أول إظهار 31 ثانية على المحاكي البرمجي) |
| (أ) الالتقاط فوري؟ | ⏳ **غير مقاس** — كاميرا المحاكي ليست كاميرا حقيقية. أضفت قياساً تلقائياً: `press_to_frame_ms` في `captures_log.csv` |
| (ب) captureToNumberMs p50/p95 لـ10 التقاطات | ⏳ **غير مقاس** (يحتاج جوالاً) — يُكتب لكل التقاط في `files/captures_log.csv` |
| (ج) حجم صورة الدليل | ⏳ غير مقاس هنا — يُكتب في `captures_log.csv` و`bench_summary` (`evidence_min_kb/max_kb`) |
| (د) الصورة المحفوظة = المستطيل؟ | ⏳ أضفت لكل التقاط صورة مصغّرة للإطار الكامل عليها القصّ المحسوب بالأحمر في `files/rectcheck/` لمقارنتها بالمستطيل الأصفر الذي رآه المستخدم |
| الاختبار الجماعي | ❌ **لم يكتمل على المحاكي**: صلاحيات التخزين في API 30 تمنع التطبيق من قراءة الصور المدفوعة بـ adb root (EACCES)، والدفع بدون root ممنوع إلى `Android/data`. على **جوال حقيقي** الدفع العادي بـ `adb push` يعمل (المجلد يملكه shell عبر FUSE). الحل الدائم المقترح: زر «استيراد الصور» داخل التطبيق (SAF) — لم يُنفَّذ بعد |

## (هـ) الكراشات التي وُجدت وأُصلحت في `app/demo/**`
1. **كراش عند الفتح** `BufferUnderflowException` في `MeterReader.run` ← سببه استدعاء المحرك من خيطين معاً (التسخين في شاشة الإدخال + الاختبار الجماعي) و`MeterReader` يعيد استعمال مخزن إدخال واحد. **الإصلاح في demo:** كل الاستدعاءات داخل `synchronized(reader)`. **ملاحظة لوكيل A (meterocr):** الأفضل جعل `MeterReader.read` نفسه `@Synchronized` أو مخزن لكل استدعاء.
2. **كراش الاختبار الجماعي** عند صورة غير قابلة للقراءة (EACCES) ← الآن تُتخطّى الصورة بدل إسقاط التشغيل كله.
3. تحذير ONNX Runtime (`ORTTelemetry UnsatisfiedLinkError` + `Receiver not registered` في finalizer) — غير قاتل، من مكتبة ORT 1.31 نفسها. **لوكيل A:** يُستحسن تعطيل TelemetryInitializer في الـ manifest (`tools:node="remove"`).

## إضافات للتطبيق
- `--ez autobench true` يفتح الاختبار الجماعي ويشغّله مباشرة (للمحاكي والجوال وCI).
- `CaptureLog.kt` → `files/captures_log.csv`: press→frame، press→number، زمن المحرك، حجم الدليل، أبعاد الخام/القصّ، الدوران، ZSL، الزوم.
- `rectcheck/`: صورة تحقق المستطيل لكل التقاط.
- `debug` يحوي x86_64 (للمحاكي)؛ `release` يبقى ARM فقط.

## المطلوب لإكمال T1
جوال أندرويد متوسط حقيقي (موصول بـ adb أو يسلّمه المالك): `adb install` ثم `adb push photos/ .../files/photos` ثم `--ez autobench true`،
و10 التقاطات حقيقية ثم `adb pull .../files/captures_log.csv .../files/rectcheck/ .../files/bench_*`.
