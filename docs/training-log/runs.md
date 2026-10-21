# سجلّ التشغيلات (مرتّب زمنياً؛ الأحدث آخراً)

الأعمدة: الوسم | المرحلة | التهيئة | البيانات الحقيقية | الاصطناعية | الخطوات/الإعدادات | الآلة/الزمن | الـ49 (A/B) | اختبار بشري 34 | ملاحظة. الأرقام من ملفات `benchmark/results/engines/`.

| الوسم | المرحلة | التهيئة | حقيقي | اصطناعي | إعدادات | آلة/زمن | 49 A / B | 34 | ملاحظة |
|---|---|---|---|---|---|---|---|---|---|
| repro (المشحون v0.2.1) | loc t14500 + rd ft4a | — | — | — | — | — | 19/46 (v2) → 14/39 (v3) / 15 | 14 | المرجع المشحون |
| ft5p | rd | ft4a | ft5 (393 مقبولة من 1533 آلية) | line_s1 | 2000، AUG v1 | sandbox 25m | 19/46 | — | لا مكسب؛ تسميات آلية فقط |
| t14500_ft5augv1 | rd | ft4a | ft5 | line_s1 | 2000، **AUG v1** | sandbox 25m | 17/46 | — | ضابط التجربة |
| t14500_ft5augv2 | rd | ft4a | ft5 | line_s1 | 2000، **AUG v2** (`augment.py`) | sandbox 25m | **22/46** (v2) → 16/39 / 14 | 15 | أول مكسب مُثبَت: التعزيز +5 |
| t14500_ft6augv2 | rd | ft5_augv2 | **ft6 (498 مقبولة؛ 368 متحقَّقة بشرياً؛ محاذاة شبكة؛ استبعاد testset+siblings)** | line_s1 | 3000، AUG v2 | sandbox 25m | 15/39 / 14 | 14 (CRYSTAL 0/7) | لا مكسب ⇒ تحليل السبب الجذري (`crystal-root-cause`) |
| locator_ft5_augv2 | **loc** | t14500 | ft5 loc shards (412) | scene_s1 | 6000، AUG v2 | **Contabo** 3h10m | 14/39 / **16** | **17** (TOMAS 7/7، CRYSTAL 2/7) | أول مرة B ≥ A؛ tight IoU 26→36/46 |

## قيد التشغيل / التالي
- `text_locate.py` على الـ368 المتحقَّقة (توطين بإشراف النص) ⇒ شرائح محدِّد على صور كاملة.
- بعد الاستشارة (`docs/consult/decision-2026-10-21.md`): رأس شاشة + مصنّف نوع + ثقة معايَرة.
| m1 (shards) | — | — | **265 عيّنة من قصّ العداد الكامل** (صناديق D للعداد + text_locate للسطر + قراءة المالك؛ فلتر تسميم؛ تدقيق 40/40 صحيح) | — | `build_meter_shards.py` | sandbox | — | — | CRYSTAL 32، TAGADOD 52، TOMAS_ST 50، TOMAS_SM 94، OTHER 22، SMART_YELLOW 9، KENWELL 6 |
| locator_m1_augv2 | **loc** | locator_ft5_augv2 | m1 loc (238 تدريب / 27 تحقق) | scene_s1 | 4000، AUG v2 | **Contabo** (جارٍ) | — | — | أول محدِّد يتدرّب على قصّ العداد الكامل |
| reader_ft6m1_augv2 | rd | reader_ft6_augv2 | ft6+m1 (631 تدريب / 132 تحقق) | line_s1 | 3000، AUG v2 | sandbox 25m | 14/39 / 15 | **19** (TOMAS 7/7، OTHER 2/4، CRYSTAL 2/7) | val 101→108/132؛ مع locator_ft5_augv2. الاختبار البشري 14→17→19؛ الـ49 ثابتة (مستطيل A لا يستفيد من محدِّد العداد الكامل) |
| reader_ft6m1_mask_s0 | rd | reader_ft6_augv2 | ft6+m1 (631/132) | line_s1 | 3000، AUG v2، **IGNORE_ROW=1** (إخفاء الخسارة يمين الصحيح)، بذرة 0 | sandbox 51m (3 تشغيلات متوازية) | **16/39 / 16** | 18 (CRYSTAL 1/7) | val 108؛ الـ49 +2 لكن الاختبار البشري −1 |
| reader_ft6m1_mask_s1 | rd | reader_ft6_augv2 | ft6+m1 | line_s1 | 3000، AUG v2، IGNORE_ROW=1، بذرة 1 | sandbox 52m | 15/39 / 15 | 19 (CRYSTAL 2/7) | val 108 |
| reader_ft6m1_nomask_s1 | rd | reader_ft6_augv2 | ft6+m1 | line_s1 | 3000، AUG v2، **بدون إخفاء**، بذرة 1 (الشاهد) | sandbox 51m | 14/39 / 15 | 19 (CRYSTAL 2/7) | val 108. **الخلاصة:** الإخفاء وحده لا يحرّك شيئاً ذا دلالة (±1–2 = ضجيج البذرة)؛ غلط-واثق 0 في الستة. تعارض الأهداف ليس عنق الزجاجة الوحيد — الاصطناعي ما زال يرسم كسر Crystal صغيراً، وعدد عيّنات Crystal/الأنواع القصيرة قليل |
| m2 (shards) | — | — | **482 عيّنة قصّ عداد كامل** من 1079 تسمية D (text_locate 5 عمال؛ no_tl 578 = غير موطّن/غير مجرَّب بعد، short_unsafe 59، low_score 33، irregular 18؛ تدقيق لوحة 40: 39 صحيحة + 1 ضبابية بالكامل (CRYSTAL 321 — شرائح لا تُرى) | — | `build_meter_shards.py text_locate_all.json m2` | sandbox 17s | — | — | CRYSTAL 88، TAGADOD 90، TOMAS_SM 113، TOMAS_ST 53، OTHER 54، SMART_YELLOW 48، KENWELL 33؛ تدريب 434 / تحقق 48 |
| reader_ft6m2_s0 / _s1 | rd | reader_ft6m1_augv2 | ft6+m2 (**827** تدريب / 153 تحقق) | line_s1 | 3000، AUG v2، بذرتان 0/1 | sandbox (جارٍ، 10:03Z) | — | — | step0 val 127/153 و124/153 |
| locator_m2_augv2 | loc | locator_m1_augv2 | m2 loc (434/48) | scene_s1 | 3000، AUG v2 | Contabo (في الطابور بعد m1) | — | — | — |
