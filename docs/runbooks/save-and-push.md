# Runbook: حفظ ورفع الشغل (بعد كل خطوة)
**متى:** نهاية كل خطوة/تجربة/جلسة · **المدة:** 2 دقيقة · **الصلاحيات:** push على moain2026/almaham-3

## الخطوات
1. حدّث: `STATUS.md` (قيد العمل/تم)، `docs/history/<date>-session-NN.md`، `CHANGELOG.md` [Unreleased]،
   و `LESSONS.md` لو صار خطأ، و `docs/research/benchmark-summary.md` لو فيه رقم جديد.
2. `bash scripts/check.sh`
3. تأكد ما فيه بيانات خاصة: `git status --short` — ممنوع أي `data/`, `*.jpg` من الصور الـ49, `*.npz`, `*.onnx`.
4. `git add -A && git commit -m "<type>: <وصف>"` (Conventional Commits).
5. `git push origin main` (في السندبوكس: استدعِ أداة `setup_github_environment` أولاً).

## التحقق من النجاح
`git status` نظيف و `git log origin/main -1` = آخر commit.

## التراجع
`git revert <sha>` (لا `push -f` على main).
