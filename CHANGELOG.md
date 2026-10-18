## [0.1.0-alpha] — 2026-10-18 — النسخة الأولية التجريبية (`v0.1.0`)
- APK تجريبي على GitHub Release؛ 49 اختبار وحدات؛ صلاحية CAMERA فقط. الأرقام والحدود في `docs/release-0.1.0.md`.

## [Unreleased] — 2026-10-18 (جولة 2، فرع genspark_ai_developer)
- meterocr: `MeterReader.read/close` @Synchronized؛ إزالة INTERNET/ACCESS_NETWORK_STATE ومزوّد التيليمتري من AAR ONNX Runtime عند دمج الـ manifest (offline فعلياً).
- lab/train_det.py: حفظ نقطة وتقييم كل 250 خطوة (كان 500).
### Added
- `docs/manifests/` (سجل البناء والهاشات، إعداد AVD)، `docs/history/2026-10-18-session-02-agentB.md`، `scripts/verify_app_build.sh` (وكيل B).
- demo: autobench intent، CaptureLog، rectcheck، x86_64 في debug؛ إصلاح كراشين (وكيل B). `docs/phone-test-emulator_x86_64_api30.md`.
- `app/meterocr/.../ForensicReader.kt` + `ForensicReaderTest.kt` + مثبّتات `test/resources/forensic/` + `lab/make_forensic_fixtures.py` (وكيل B).
- `benchmark/data/digit_boxes.json` + `digit_spans_manual.json` + `lab/make_digit_boxes.py` (وكيل B، عقد §3).
- `lab/forensic_reader.py` + `lab/eval_forensic_reader.py` (وكيل B، عقد §2).
- `app/`: مشروع Android (Kotlin + Compose + CameraX 1.5.0 + ONNX Runtime 1.31): موديول `meterocr` (config, RectGeometry, ReadingAssembler,
  ReadingValidator, PeakDecoder, MeterReader, EvidenceImage, ReadingLog) + تطبيق `demo` (شاشة إدخال، كاميرا بمستطيل/زوم/فلاش/ZSL،
  خط معالجة بعد الضغطة، وضع اختبار جماعي A/B × DigitNet/ML Kit). 35 اختبار وحدات.
- `lab/synth2.py` مولّد مشاهد بصناديق لكل رقم (DSEG OFL + إجرائي)، `det_model.py` DigitNet، `train_det.py`, `gen_det_data.py`,
  `assemble.py` (+10 اختبارات)، `export_onnx.py`, `eval_e2e.py`, `eval_reader_oracle.py`, `report.py`.
- وثائق: `docs/research/research_decision_v3.md`, `docs/benchmark_report.md` (+tables), `docs/migration-plan.md`, `app/README.md`.
### Measured
- DigitNet v1 (تدريب جزئي): 0/46 end-to-end، 3/46 قارئ فقط على قصّ مثالي، p50 50ms على CPU x86. التفاصيل في benchmark_report.md.

# Changelog
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)

## [Unreleased]
### Added
- مختبر جنائي: `lab/sevenseg4.py` `sevenseg5.py` `sevenseg6.py` `forensic_grid.py` + `docs/research/forensic-lab-2026-10-18.md`.
- `docs/research/how-they-do-it-2026-10-18.md`: تحليل Anyline/Laroca/MDPI + الحل المقترح + خطة تدريب على صور ERP المعتمدة.
- `scripts/export_erp_training.sql`: تصدير القراءات `confirmed` مع مفاتيح الصور (الجزء الصحيح فقط).
- `docs/brief/04_برومت_الوكيل_المفتوح.md`: برومت مفتوح لوكيل خارجي (يشرح الهدف والقيود والمعايير بدون فرض طريقة).

## [0.1.0] - 2026-10-18
### Added
- المستودع بهيكل cortex-memory: README, AGENTS/CLAUDE, STATUS, LESSONS, CONTRIBUTING, SECURITY, ADRs, REQ-001،
  تصميم الـ pipeline، runbooks، postmortem، سجل الجلسة.
- `docs/brief/`: المهمة الأصلية (الشرح، البرومت، البحوثات، صور التصميم — مع تمويه بيانات المشترك).
- `benchmark/data/`: ground_truth v2 (49 صورة)، meter/display/line boxes، بصمات SHA256 للصور.
- `benchmark/results/`: مخرجات PP-OCRv5/v6 و ERP baseline و SegReader + `verified_2026-10-18.txt`.
- `lab/`: كود البحث والتدريب، `paths.py` (مسارات موحّدة)، `eval_rec.py`، أوزان SegReader (s1000 و s4000)، سجلات التدريب.
- `scripts/`: `download_models.sh` (SHA256 مثبّت)، `verify_photos.sh`، `check.sh`. `requirements-lab.txt` بإصدارات مثبّتة.
### Changed
- `lab/gt.py` يقرأ ground_truth v2 (كان v1). كل المسارات المطلقة استُبدلت بـ `paths.py`.
- `train_rec.py`/`train_fast.py`: خيوط افتراضية 2 (كانت 3) وطباعة الأمر في أول سطر من السجل.
### Fixed
- 3 قراءات غلط في ground_truth v1 (23106, 23109, 23113) + 23086, 23091, 23072. انظر LESSONS.
### Deprecated
- `benchmark/data/archive/ground_truth_v1.csv`، `docs/research/archive/research_decision_v1.md`، `benchmark/results/archive/`.
- 2026-10-18 agent B: v0.1.1 pre-release = ONE APK only (owner): almaham-meter-0.1.1-arm64.apk, field, 37,849,126 B, sha256 9eaf497e…145e5c (stat/aapt2 native-code arm64-v8a). armv7/bench not published. ≤20 MB not reached: ORT 1.31 = 34,208,672 B; minimal ORT .so built 2,455,568 B but needs .ort assets (agent A). R8 build not yet run on device.
- 2026-10-18 agent B: docs — docs/apk-size-report.md (all byte tables, commands, ORT-minimal 2,455,568 B, LiteRT 4,320,480 B, parity 10/10), handoff docs/handoff/agentB-to-agentA-apk-size-0.1.1.md, release-0.1.0 §2 install note, app-build-record 0.1.1, artifacts/ort-minimal AAR.
- 2026-10-18 agent B: lab/multi_algo.py 792 deterministic exams (colours×polarity×binarizers×movements)+vote: line crop 20/46 (holdout 13/36; was 11/46), full meter rect 0/46. Not in app. docs/research/multi-algo-2026-10-18.md
