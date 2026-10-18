# المساهمة
- الفروع: `feat/…` `fix/…` `docs/…` `exp/…` · Commits: [Conventional Commits](https://www.conventionalcommits.org/) `feat: …` `fix: …` `exp: …`
- كل PR: يربط متطلباً (`REQ-001.x`) أو مشكلة، يمر بـ `bash scripts/check.sh`، يحدّث CHANGELOG و STATUS.
- **تعريف "مكتمل":** كود + اختبار + توثيق + STATUS محدّث + ملف جلسة في `docs/history/` + push.
- **أي رقم جديد:** يُحفظ مخرجه في `benchmark/results/` ويُكتب الأمر والعتاد في `docs/research/benchmark-summary.md`.
- **تجربة تدريب:** سجلها في `lab/logs/` (يبدأ بالأمر)، ووزنها في `lab/weights/` لو أقل من 5MB، وسطر في benchmark-summary.
