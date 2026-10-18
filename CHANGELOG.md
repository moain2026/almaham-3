# Changelog
Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)

## [Unreleased]
### Added
- تسليم بيئة جديدة: `docs/runbooks/optical-fresh-environment.md`، تحديث README، وتحقق clone نظيف وvirtualenv مستقلة.
- `benchmark/results/verified_fresh_environment_2026-10-18.txt`: 64 اختبارًا ناجحًا، إعادة توليد العرض، وتطابق قرارات 360 حالة profile/policy مع النتائج المحفوظة.
- تعليمات أرشيف Git bundle خاص ونسخ المخرجات المحلية المفيدة دون نشر صور العملاء أو الاعتمادات أو بيئات Python في الفرع العام.
- جولة تنفيذ محددة بنصف ساعة: `profile_reader.py` + `profile_policy.py` + `profile_cli.py`، قالب هندسي وتسجيل خلفية ECC وكشف فقد المقاطع ودمج الإطارات دون تدريب.
- 32 اختبارًا إضافيًا (64 إجمالًا)، تحقق تشغيل enroll/read، تبعيات مستقلة `requirements-optical.txt`، وعرض HTML مولد بلا صور عملاء.
- قياس مجمد + تحدٍّ جديد للسياسة؛ النتائج الخام بما فيها خطآن قبل السياسة محفوظة في `profile_reader_2026-10-18.json` و`profile_policy_2026-10-18.json`.
- دليل التشغيل `docs/runbooks/profile-reader.md`؛ ملف الاستكمال `docs/history/2026-10-18-optical-sprint-handoff.md` يحفظ الخطة والخطوات وما لم يُنجز.
- القيود: السياسة النهائية تقبل 1/5 قصاصات فقط ومرجعها غير مؤكد؛ لا ادعاء بلوغ الدقة الميدانية أو اعتماد إنتاجي.
- تجربة مستقلة بلا تدريب: `optical_evidence.py` (إلغاء إضاءة محلية + غموض المقاطع)، `serial_identity.py` (باركود + مطابقة سجل)،
  harness ببصمات مدخلات ثابتة ومقارنة بفرع الوكلاء + 32 اختبارًا. تقرير `docs/research/optical-evidence-2026-10-18.md` ونتائج JSON كاملة.
- أفضل احتمال جديد 4/5 قصاصات فقط، لا نتيجة على الـ46 أو الصورة الكاملة؛ فشل حسم خطأين تحت محو المقاطع محفوظ صراحةً.
- تدقيق تصويت الـ46: توثيق شرط استبعاد الإجابات ذات الخانة الواحدة؛ فصل سقف الفرضيات عن استحالة الخوارزميات، والثقة عن الاتفاق.
### Fixed
- تحذيرا pyflakes قديمان في `forensic_grid.py` (استيراد ومتغير استثناء غير مستخدمين)، دون تغيير التوقعات.
### Added (previous experiments)
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
