# autotrain — تدريب مستمر بلا وكيل، ورفع تلقائي (2026-10-21)
**الفرع:** `auto-training` (يُدفع إليه آلياً من sandbox وContabo؛ لا يُدفع إليه يدوياً). الوكيل البشري/الخليفة يراجعه ويدمج ما يثبت في `genspark_ai_developer`.

- `train_loop.sh` — حلقة لا نهائية: تقرأ وصفة من `queue_<role>.txt` (أو تولّد بذرة جديدة من أفضل وصفة إذا فرغت)، تدرّب، تقيّم (49 A/B + 34 بالنوع + risk–coverage)، تؤرشف للخاص، تضيف صفاً في `docs/training-log/runs.md`، ثم `auto_push.sh`.
- `auto_push.sh` — يضيف الأوزان/السجلات/النتائج/الوثائق ويدفع إلى `auto-training` بحارس أسرار؛ يدمج ما دفعته الآلة الأخرى.
- `done_<role>.txt` — ما اكتمل؛ `logs/autotrain_<role>.log` — سجل الحلقة.
- التشغيل: sandbox: `ROLE=reader setsid nohup bash lab/autotrain/train_loop.sh &` (×عدد الأنوية الحرة)؛ Contabo: خدمة systemd `almaham-autotrain-locator` و`almaham-autotrain-reader` (انظر `contabo_units.sh`).
- الإيقاف: `systemctl stop almaham-autotrain-*` على Contabo؛ في sandbox اقتل العملية بـPID من السجل (لا `pkill -f`).
- **أين النتائج لاحقاً؟** `git fetch origin auto-training` → `docs/training-log/runs.md` (صف لكل تشغيل)، `lab/weights/*.pt`، `benchmark/results/engines/*`. والنسخة الكاملة (أوزان وسيطة، صور مراجعة) في الخاص `weights_archive/`, `results_archive/`.
