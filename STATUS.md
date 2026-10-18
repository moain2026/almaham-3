---
updated: 2026-10-18
---
# الحالة الآن

## قيد العمل
- [2026-10-18 وكيل A] **e2e الآن 12/46 (26%)** مع ft3a (self-training 923 عيّنة) + إصلاح حدّ الكسر في التجميع (Python+Kotlin)؛ القارئ على قصّ مثالي 18/46؛ المحدِّد ضيّق 30/46؛ غلط-وواثق 0. المسار 0→6→9→12. ft3 ما زال يتدرّب (reader 2500، locator 1500). 2216 صورة مسمّاة محلية الآن ⇒ الجولة 4 تُبنى بنماذج ft3 النهائية. تجربة تصويت 4 قصوص بهوامش مختلفة: 7→8 فقط (لا تستحق ×4 زمن) — مرفوضة.
- [2026-10-18 وكيل A] **أول نتيجة حقيقية e2e: 0 → 6/46** (ft2mid؛ القارئ على قصّ مثالي 2→10/46، المحدِّد ضيّق 17→28/46) — `docs/benchmark_report.md` §8. الجولة 3 (self-training، 923 عيّنة حقيقية) تعمل: `lab/logs/train_{reader,locator}_ft3.log`؛ بداية reader real_val 55/116. أداة `lab/eval_ckpt.sh <loc.pt> <rd.pt> <tag>` تقيّم أي زوج أوزان على الـ49 بأمر واحد. **الخطأ الغالب الآن في التجميع (حدّ الكسر) لا الشبكة** — التالي.
- [2026-10-18 وكيل A] **الضبط الدقيق على 1829 صورة ERP مسمّاة (كلها محلية الآن)**: `erp_finetune.py build` ⇒ **361 عيّنة مقبولة** (exact 126، relabel 235، lattice 127؛ مرفوض: count_mismatch 1283، irregular 105، no_line 91) — التقرير `benchmark/results/engines/erp_weak_labels_ft2_report.json`. تدريبان متوازيان 2000 خطوة (lr 2e-4، 50/50 حقيقي/اصطناعي): `reader_ft2` بداية real_val_exact **8/46**؛ `locator_ft2` (من locator_t) بداية real_val_line_iou50 40/46 (تحيّز: الـ val صور وجد فيها locator_t السطر أصلاً — المقياس الحقيقي يبقى الـ49 عبر `eval_locator_real.py`). السجلات `lab/logs/train_{reader,locator}_ft2.log`. **لا gradle الآن.** ملاحظة: التجربة الأولى ft1 (125 عيّنة) ماتت بصمت بعد ~250 خطوة (السبب غير معروف، لا OOM) — نقطة الحفظ لم تتحسن (5/17).
- [2026-10-18 وكيل A] **ردّ على الوكلاء + أول ضبط دقيق على صور حقيقية**:
  (1) **ADR-0005** حسم تعريف السطر = اتحاد صناديق الأرقام (ضيّق)؛ مقياس M3 الرسمي `recall_tight_iou50` (locator_v1 17/46، locator_t@4000 21/46). لا تغيير في synth2.py. وكيل T يكمل.
  (2) **التسميات**: 3308 سطر (1845 مقروء) من الشريحتين + 108 لي. فحص أمني: لا كلمة سر ERP ولا توكن GitHub في أي ملف أو في تاريخ git (grep على كل الـ commits). التسريب كان في المحادثة فقط ⇒ **على المالك إلغاء التوكن وكلمة مرور photo-review وإصدار بديل** بعد انتهاء الوكلاء.
  (3) `erp_fetch_labelled.py` ينزّل كل الصور المسمّاة (1829؛ جارٍ). `erp_finetune.py build` على locator_t + reader_v1_s2000: من 614 صورة محلية قُبل **125** (exact 43، relabel 82، lattice 46؛ مرفوض: count_mismatch 493، no_line 42، irregular 32) — الصناديق الضعيفة روجعت بصرياً على 26 عيّنة (سليمة). يُعاد البناء بعد اكتمال التنزيل (~1829 ⇒ متوقع ~400 مقبول).
  (4) **تدريب تجريبي** `reader_ft1` (1500 خطوة، 50/50 حقيقي/اصطناعي، lr 2e-4): بداية real_val_exact 5/17 — `lab/logs/train_reader_ft1.log`.
- [2026-10-18 وكيل A → وكيل B] **حجم الـ APK 89 MB — مهمة تصغير إلى ≤20 MB** (`docs/prompts/agentB-apk-size.md`): التشريح: dex بلا تقليص 45.9 MB، ONNX Runtime كامل 34+24 MB لمعماريتين، ML Kit (للقياس فقط) 19 MB؛ نماذجنا 1.7 MB فقط. الحل: R8 + حذف ML Kit من نكهة الميدان + split per-ABI + ORT minimal build.
- [2026-10-18 وكيل B] **توثيق كامل**: `docs/manifests/app-build-record.md` (commit البناء، sha256 للـ APK والنماذج والأوزان والصور، التوقيع، 49 اختبار، البيئة)، `docs/manifests/sha256-repo-files.txt` (100 ملف)، `docs/history/2026-10-18-session-02-agentB.md`، `scripts/verify_app_build.sh`.
- [2026-10-18 وكيل A] **الإصدار 0.1.0 (أولي تجريبي)** موسوم `v0.1.0` مع APK في GitHub Release — `docs/release-0.1.0.md` فيه كل الأرقام الحقيقية (0/46 في التطبيق، المحدِّد 20/46 هو السبب)، التثبيت، الرخص، وما ينقص. تدريب reader_v2 أُوقف (تدهور 45→39/97).
- [2026-10-18 وكيل A — تسليم جلسة] **تسميات ERP**: 1108 سطر مجمّع (slice_0 800 + slice_1 200 + agentA_vision 108)، منها 670 قابلة للقراءة؛ اتفاق تام 12/12 بين تسمياتي وتسميات وكلاء التسمية على الصور المشتركة (هم أكثر تحفظاً: 10 X عندهم قرأتها أنا). الصور المحلية: 1313 في `data/erp/photos` (جلب slice 1 يعمل في الخلفية: `lab/logs/erp_fetch_s1.log`). **219** تسمية مقروءة صورتها محلية الآن → كافٍ لتشغيل `python3 lab/erp_finetune.py build weights/locator_v1.pt weights/reader_v2.pt ../data/erp/ft` بعد انتهاء الجلب.
  **تدريب القارئ v2**: العملية حيّة (CPU ~280%)، لكن آخر سطر في السجل `step 500 val 39/97` منذ 08:43 — سجل كل 250 خطوة؛ إن لم يظهر `step 750` خلال 5 دقائق أعد التشغيل بأمر الـ runbook من `weights/reader_v2.pt`. الخطوات التالية بالترتيب: `eval_reader_oracle.py` → `export_onnx.py` → `eval_e2e.py` + `eval_vote.py` → تحديث `docs/benchmark_report.md` → commit بادئته `model:`. **لا gradle أثناء التدريب** (يقتل العملية).
- [2026-10-18 وكيل A] **meterocr** `MeterReader.read/close` صارا `@Synchronized` (طلب وكيل B بعد كراش BufferUnderflow)؛ واكتشاف خصوصية: AAR `onnxruntime-android 1.31.0` يضيف بنفسه صلاحيتي INTERNET وACCESS_NETWORK_STATE ومزوّد `TelemetryInitializer` — حُذفت الثلاثة في `meterocr/AndroidManifest.xml` عبر `tools:node="remove"` (التطبيق صار بلا أي صلاحية شبكة). تدريب القارئ v2 (2500 خطوة، استئناف من s2000) يعمل: `lab/logs/train_reader_v2.log`.
- labels slice 0: 2400 done, 1112 unreadable (52 P) — تسمية آلية بنموذج رؤية لا بشرية (3 قراءات مستقلة، يُقبل الإجماع فقط وإلا X)، عيّنة ≥10% من الأرقام روجعت يدوياً
- [2026-10-18 وكيل B] **T1 (جزئي)** التطبيق يُبنى (44 اختبار وحدات ناجحة) ويُثبَّت ويفتح على **محاكي** x86_64 API30 بلا KVM؛ أُصلح كراشان في demo (استدعاء المحرك المتزامن، صورة غير مقروءة)، وأضيف `--ez autobench true` و`captures_log.csv` و`rectcheck/`. الاختبار الجماعي لم يكتمل (صلاحيات تخزين المحاكي) وبنود الكاميرا (أ–د) تحتاج **جوالاً حقيقياً** — `docs/phone-test-emulator_x86_64_api30.md`.
- labels slice 1: 3800 done, 2095 unreadable (114 P) — تسمية آلية بنموذج رؤية لا بشرية: 3 قراءات مستقلة على العرض المكبّر + فحص رابع خانةً خانة على الصورة الأصلية؛ يُقبل الرقم فقط إذا اتفقت الأربعة وإلا X. مراجعة يدوية: 20 صورة من 0–200 بلا أخطاء، و24 من 1600–2400 فيها خطأان مُجمَع عليهما (TAGADOD 001418 قُرئ 007478؛ 008248 قُرئ 008290) رفضهما الفحص الرابع فأُضيف بأثر رجعي
- [2026-10-18 وكيل B] **T4** `app/meterocr/.../ForensicReader.kt` (نقل حرفي لـ forensic_reader.py بلا OpenCV) + `ForensicReaderTest` (4 اختبارات ناجحة): يطابق Python على 5 قصوص ثابتة (النص، الحالة، الفئة، conf ±1e-6، الصندوق ±1e-5، المقاطع). الأمر: `cd app && ./gradlew :meterocr:testDebugUnitTest --tests '*ForensicReaderTest*'` (JDK17، سندبوكس). المثبّتات من `lab/make_forensic_fixtures.py`.
- [2026-10-18 وكيل B] **T3** `benchmark/data/digit_boxes.json` (عقد §3، 46 صورة، تقييم فقط): مدى يدوي لكل صورة على قصّ line_boxes (عرض CLAHE) مقسوم بخطوة ثابتة؛ المصدر `benchmark/data/digit_spans_manual.json`، المولّد `lab/make_digit_boxes.py`. الصور المائلة (23106، 23110) تقريبية.
- [2026-10-18 وكيل B] **T2 القارئ الحتمي** `lab/forensic_reader.py` (عقد §2، 3 فحوص مستقلة max/gray/green + تصويت): exact **11/46** (holdout 5/36)، خانات conf≥0.8 = **56/57 = 98.2%** (holdout 97.1%) — القاعدة مُعايَرة على نفس الـ46 (in-sample). الأمر: `cd lab && python3 eval_forensic_reader.py` → `benchmark/results/engines/forensic_reader_lineL.json`، سندبوكس x86 p50 414ms (Python خالص).
- [2026-10-18 جولة 2، فرع `genspark_ai_developer`] **تغيير الاتجاه: كشف الأرقام ككائنات (DigitNet، CenterNet-lite) بدل CRNN/CTC** —
  انظر `docs/research/research_decision_v3.md`. التطبيق Android مكتوب ويُبنى (`app/`، 35 اختبار وحدات ناجحة، APK يُبنى).
  **التدريب غير مكتمل** (قارئ 2000/6000 خطوة، محدِّد ~0): النتيجة الحالية end-to-end **0/46** — `docs/benchmark_report.md`.
  كانت عمليتا تدريب تعملان في الخلفية عند إغلاق الجلسة (`lab/logs/train_reader_v1.log`, `train_locator_v1.log`)؛ أعد تشغيلهما
  بالأوامر في `docs/runbooks/train-digitnet.md`.

## معطّل / ينتظر قرار المالك
- [2026-10-18] **مختبر جنائي بلا تعلّم** (`docs/research/forensic-lab-2026-10-18.md`): 3 خوارزميات جديدة (v4/v5/v6) + 23 معالجة
  (عكس ألوان، قنوات، CLAHE، Retinex، إزالة لمعان...) × 3 قرّاء + تصويت = **16/46 (9/36 HOLDOUT)**، خطأ واثق 3؛ السقف 22/46.
- [2026-10-18] **الحل المقترح «قارئ المهام» (5 طبقات)** في `docs/research/how-they-do-it-2026-10-18.md`: يحتاج
  (1) موافقة على نموذج صغير <1MB داخل التطبيق، (2) تصدير القراءات المعتمدة+صورها عبر `scripts/export_erp_training.sql`.
  الحتمي وحده وصل 6/36 HOLDOUT فقط.
- [2026-10-18] **قرار الاتجاه:** (أ) نكمل تدريب SegReader اصطناعياً، (ب) نبدأ هيكل التطبيق (الكاميرا/المستطيل/القص
  مستقلة عن المحرك)، (ج) صور معتمدة من الـ ERP للتدريب (3–5 آلاف) — الأرجح أنها الطريق الوحيد لـ ≥95%.
- [2026-10-18] **6 صور «غير متأكد»** تحتاج مراجعة بشرية من المالك: 23065, 23071, 23086, 23088, 23091, 23099
  (انظر `benchmark/data/ground_truth.csv` العمود notes). أهمها 23091: 243 أم 283/288 (مقاطع شبحية).
- [2026-10-18] زر «من الاستديو» في المشروع الرئيسي: يُشال أو يبقى بعلامة؟ (01_الشرح.txt §6)
- [2026-10-18] لا يوجد جوال حقيقي في السندبوكس: كل أرقام الزمن الحالية من CPU سيرفر. قياس ML Kit مستحيل هنا.

## خارطة الطريق
| المرحلة | الهدف | معيار الإنجاز (قابل للقياس) | الحالة |
|---|---|---|---|
| M0 | الحقيقة + قياس المحركات الجاهزة | ground_truth.csv (49) + جدول PP-OCR/ERP | ✅ (أفضل جاهز 17/46) |
| M1 | قرار المحرك | research_decision.md معتمد | ✅ الخيار C (ADR-0002) |
| M2 | محرك SegReader يتجاوز الـ ERP | > 17/46 end-to-end وضع A، «غلط وواثق» < 1% | ⏳ 15/46 على قصّ مثالي فقط |
| M3 | محدِّد السطر | recall ≥ 95% لسطر القراءة داخل المستطيل | ⬜ (الكلاسيكي 17/46 — مرفوض) |
| M4 | التطبيق: إدخال + كاميرا + مستطيل + قص + حفظ | REQ-001.1–.6، صورة 80–200KB، اختبارات تحويل الإحداثيات | ⬜ |
| M5 | ربط المحرك بالتطبيق + التحقق المنطقي | REQ-001.7–.10، p50 < 300ms على جوال متوسط | ⬜ |
| M6 | الاختبار الجماعي على الجوال + التقرير | benchmark_report.md + CSV + فيديو | ⬜ |
| M7 | خطة النقل للمشروع الرئيسي | migration-plan.md | ⬜ |

### Now / Next / Later
- **Now:** إكمال تدريب DigitNet (المحدِّد + القارئ) ثم `export_onnx.py` → `eval_e2e.py` → إعادة توليد التقرير؛ وتشغيل وضع الاختبار الجماعي على جوال.
- **Next:** M2 + M4 بالتوازي (M4 لا يعتمد على المحرك).
- **Later:** M5–M7.

## خارج النطاق صراحةً (من البرومت §3)
- ERP، تسجيل دخول، سيرفر، رفع صور، أي ميزة غير: شاشة الإدخال، الكاميرا، القص والقراءة، الاختبار الجماعي.
- تدريب على داتا Copel-AMR / UFPR-AMR (رخصة أكاديمية).

## تم مؤخراً
- [2026-10-18] agentT locator step 12000: synth val 156/196، سطر حقيقي IoU>0.5 = 15/46 (32.6%), IoU med 0.396, tight 23/46, found 40 (`docs/training-log-agentT.md`).
- [2026-10-18] agentT locator step 10000: synth val 154/196، سطر حقيقي IoU>0.5 = 11/46 (23.9%), IoU med 0.371, tight 21/46, found 40 (`docs/training-log-agentT.md`).
- [2026-10-18] agentT locator step 8000: synth val 151/196، سطر حقيقي IoU>0.5 = 11/46 (23.9%), IoU med 0.365, tight 23/46, found 41 (`docs/training-log-agentT.md`).
- [2026-10-18] agentT locator step 6000: synth val 150/196، سطر حقيقي IoU>0.5 = 15/46 (32.6%), IoU med 0.396, tight 28/46, found 43 (`docs/training-log-agentT.md`).
- [2026-10-18] agentT locator step 4000: synth val 134/196، سطر حقيقي IoU>0.5 = 12/46 (26.1%), IoU med 0.424, found 42 (`docs/training-log-agentT.md`).
- [2026-10-18] agentT locator step 2000: synth val 108/196، سطر حقيقي IoU>0.5 = 17/46 (37.0%), IoU med 0.419, found 44 (`docs/training-log-agentT.md`).
- [2026-10-18] برومت مفتوح لوكيل خارجي: `docs/brief/04_برومت_الوكيل_المفتوح.md` (المالك يرسله مع meters.zip).
- [2026-10-18] توحيد كل الشغل في هذا المستودع + توثيق كامل + تحقق من clone جديد (كل الأرقام طابقت). انظر `docs/history/2026-10-18-session-01.md`.
- [2026-10-18] نسخة احتياطية خاصة للصور الـ49 + الحزمة الأصلية (خارج git) — `almaham3_private_data_2026-10-18`.
- [2026-10-18] تدريب SegReader v2: 4000 خطوة، 15/46.
- [2026-10-18] ground_truth v2 (تصحيح 3 قراءات غلط في v1) + مستطيلات A/الشاشة/السطر.
- [2026-10-18] قياس PP-OCRv5/v6 و ERP baseline على الوضعين A و B.
- 2026-10-18 agent B: v0.1.1 pre-release = ONE APK only (owner): almaham-meter-0.1.1-arm64.apk, field, 37,849,126 B, sha256 9eaf497e…145e5c (stat/aapt2 native-code arm64-v8a). armv7/bench not published. ≤20 MB not reached: ORT 1.31 = 34,208,672 B; minimal ORT .so built 2,455,568 B but needs .ort assets (agent A). R8 build not yet run on device.
- 2026-10-18 agent B: docs — docs/apk-size-report.md (all byte tables, commands, ORT-minimal 2,455,568 B, LiteRT 4,320,480 B, parity 10/10), handoff docs/handoff/agentB-to-agentA-apk-size-0.1.1.md, release-0.1.0 §2 install note, app-build-record 0.1.1, artifacts/ort-minimal AAR.
