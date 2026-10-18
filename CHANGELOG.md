# Changelog
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)

## [Unreleased]
### Added
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
