## [Unreleased] — 2026-10-18 (جولة 2، فرع genspark_ai_developer)
- meterocr: `MeterReader.read/close` @Synchronized؛ إزالة INTERNET/ACCESS_NETWORK_STATE ومزوّد التيليمتري من AAR ONNX Runtime عند دمج الـ manifest (offline فعلياً).
- lab/train_det.py: حفظ نقطة وتقييم كل 250 خطوة (كان 500).
### Added
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
