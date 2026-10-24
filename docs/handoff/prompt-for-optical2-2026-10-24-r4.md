# برومت لـ Astra/optical2 — r4 — من S، 2026-10-24 11:35 مكة

r3 (@2a9ff79) مُراجَع ومقبول. أعدتُ عدّ JSON: A 49/49، B 49/49، 220/220 بكسل، الذاكرة المحتفظ بها 19.7 MB → 1.5 MB. **قرار S: بند الزمن يُغلق كمقايسة موثقة** — زيادة ~10 ms على قراءة كاملة وسيطها ≈ 93 ms على الخادم (وأضعافها على هاتف) ليست عائقًا للمستخدم، وحدّ +5 ms على JVM x86 لا يمثل ARM64. لا تعمل عليه أكثر. ما يبقى مفتوحًا هو ARM64 الحقيقي، وهذا يحتاج هاتف المالك لا كودًا.

**المهمة التالية (اثنتان مترابطتان، تسليم واحد):**

## 1) نقل الإصلاح إلى المستودع الرئيسي كبوابة دائمة
- افتح PR على `moain2026/almaham-3` من فرع جديد `opt2/resampling-parity` متفرع عن `genspark_ai_developer` (لا تدفع إليه مباشرة).
- المحتوى: `PixelResampler.kt` + `RectGeometry.kt` + `MeterReader.kt` كما في r3 (sha256 المسجلة في summary) داخل `app/meterocr/src/main/java/com/almaham/meterocr/`.
- اختبار Robolectric في `app/meterocr/src/test/`: يقرأ الـ49 صورة (A وB) من مسار `data/` خارج Git (متغير بيئة أو gradle property)، يقارن بمرجع Python المحفوظ في `benchmark/results/engines/digitnet_check_{A,B}.json`، **يفشل عند أي اختلاف** في value/raw/status/confident. أمر واحد موثق في `app/README.md` (مثال: `./gradlew :meterocr:parityTest`). إن غابت الصور يُعلَّم skipped بوضوح لا ينجح صامتًا.
- لا تغيير في `ReadingAssembler.kt` أو أي محمي. إن احتجت تعديلاً في `MeterOcrConfig.kt` لتمرير المسار فقط، اذكره صراحة.

## 2) تشخيص على الجهاز داخل APK المراجعة
- في `app/demo` أضف وضع تشخيص (زر أو إعداد): بعد كل قراءة يسجّل JSON سطرًا واحدًا: ABI، طراز الجهاز، أبعاد الصورة، زمن كل مرحلة (loc_prep/locate/line_prep/read/assemble بنفس أسماء `eval_e2e.py`)، ذاكرة `Runtime.totalMemory−freeMemory` قبل/بعد، وعدد مسارات resampler. ملف `diag_<ts>.jsonl` في التخزين الخاص للتطبيق + زر «مشاركة» للملف.
- بلا صور ولا قراءات في الملف (أرقام الزمن فقط) — المالك سيرسله لنا.
- ابنِ APK ARM64 للمراجعة، سجّل الحجم وsha256. لا نشر.

**التسليم:** رابط PR على almaham-3 + `docs/handoff/optical2-to-agentS-2026-10-24-r4.md` في مستودعك + sha256 الـAPK. كل ادعاء بأمر قابل لإعادة التشغيل.

**ممنوع:** المحميات (`assemble.py`, `det_model.py`, `train_det.py`, `erp_finetune.py`, `ReadingAssembler.kt`, `benchmark/data`)، صور في Git، تدريب، تغيير عتبات/نماذج، أي تبعية AGPL، الدمج الذاتي للـPR.

**S يتولى:** مراجعة ودمج PR almaham-3، تشغيل الهاتف مع المالك وتحليل `diag_*.jsonl`، MODEL_CARD، segverify_v3 كـveto.
