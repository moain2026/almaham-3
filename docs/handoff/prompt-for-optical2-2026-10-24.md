# برومت لـ Astra/optical2 — من S، 2026-10-24 11:00 مكة
تسليمك (PR5 @2fefa78) مقبول كما وُصف: صادق ومقاس. عزلك لسبب 30/49 (resampling Android ≠ OpenCV INTER_AREA) أهم اكتشاف هندسي هذا الأسبوع.
المهمة التالية (واحدة):
1) وحِّد عقد إعادة التحجيم/letterbox في app/meterocr (MeterReader.kt:159–166 + RectGeometry.kt:101–112) مع lab/eval_e2e.py letterbox(): تجميع مساحي عند التصغير، ثنائي-خطي عند التكبير، نفس s/ox/oy ونفس التقريب. Kotlin خالص بلا OpenCV، مع اختبار وحدة يقارن المصفوفة ببكسلات Python (≤1 مستوى رمادي في ≥99.5% من البكسلات).
2) أعد harness الـ49 من JPEG الأصلي (A وB): value/raw/status/confident = 49/49. إن بقي اختلاف اعزل سببه بنفس المنهج؛ لا تغيّر ReadingAssembler.kt ولا lab/assemble.py.
3) زمن المعالجة قبل/بعد على JVM؛ التحجيم اليدوي ≤ +10 ms على 256×256 و64×448.
4) التسليم: PR + docs/handoff/optical2-to-agentS-2026-10-24-r2.md + JSON للـ49 قبل/بعد.
ممنوع: المحميات (assemble.py, det_model.py, train_det.py, erp_finetune.py, benchmark/data)، صور في Git، تدريب.
S يتولى: segverify_v3 كـveto في risk–coverage، MODEL_CARD، التشغيل على ARM64 مع المالك.
