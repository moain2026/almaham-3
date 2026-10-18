# سجل تدريب الوكيل T (المحدِّد / locator فقط)

تقسيم العمل (قرار المالك 2026-10-18): الوكيل T يدرّب **المحدِّد** فقط، والوكيل A يدرّب القارئ.

## العتاد
- CPU: Intel Xeon @ 2.80GHz، 4 أنوية، 8GB RAM، **بلا GPU**. torch 2.14.1+cpu، Python 3.12.3.
- الـ sandbox يُعلَّق بين الجلسات (حدّ الجلسة ~4 ساعات)؛ التدريب يُستأنف من آخر checkpoint (المعامل الخامس لـ `train_det.py`) ويُكتب `RESUME step N` في اللوغ.

## البيانات (اصطناعية، بذور T = 1xx/2xx، لا تتقاطع مع A)
```
cd lab
python3 gen_det_data.py scene 12000 ../data/synth/scene_t1 201
python3 gen_det_data.py scene 12000 ../data/synth/scene_t2 202
python3 gen_det_data.py scene 12000 ../data/synth/scene_t3 203
```
(وُلّدت أيضاً line_t1..t4 بالبذور 101–104، 16000 لكلٍّ — محفوظة محلياً عند T فقط، ليست في git.)

## التدريب
```
TORCH_THREADS=3 nohup python3 train_det.py locator 20000 weights/locator_t.pt ../data/synth/scene_t1,../data/synth/scene_t2,../data/synth/scene_t3 > logs/train_locator_t.log 2>&1 &
```
إيقاف مبكر: إذا لم يتحسّن `val` الاصطناعي 3000 خطوة متتالية.

## المقياس على الصور الحقيقية
`python3 eval_locator_real.py <ckpt> <tag>` — قصّ الوضع A (`meter_boxes.json`) ← letterbox 256 كما في `eval_e2e.py` ← أعلى قمة (عتبات التطبيق `LOC_PEAK_MIN=0.25`, `LINE_MIN_H=6`) ← IoU مع `line_boxes.json`. نجاح = IoU>0.5. هدف M3: ≥ 95% (44/46). الـ46 للتقييم فقط، لا يُضبط عليها شيء.

خط الأساس: `python3 eval_locator_real.py weights/locator_v1.pt v1` ⇒ **20/46 (43.5%)**، وُجد سطر في 38، IoU الوسيط 0.425، ~26ms/صورة (CPU، PyTorch).

## أحداث
- 08:31Z بدء التدريب (20000 خطوة). 08:41Z العملية قُتلت عند الخطوة ~1000 (مهلة أداة الـ shell في الـ sandbox، ليست مشكلة في الكود) ⇒ RESUME step 1000 بـ 19000 خطوة متبقية (OneCycle يبدأ من جديد)، والعملية الآن منفصلة (setsid).
- step 1000 (قبل الاستئناف): val 33/196، سطر حقيقي 8/46 (`eval_locator_real.py /tmp/loc_s1000.pt t_s1000`).

- 09:20Z المهمة 4: نُزّلت كل صور ERP المسمّاة (1400/1400 من labels_slice_0+1) إلى data/erp/photos (خارج git). الأمر: منطق `erp_fetch.py 0 1 100000` مفلتراً على الملفات المسمّاة فقط. `lab/erp_finetune.py` موجود من A (290f456) — التشغيل عنده لأنه يحتاج reader؛ المحدِّد locator_t متاح له.

- 09:35Z **تشخيص (step 4000):** المحدِّد يجد السطر في 42/46 لكن صندوقه أقصر من المرجع: نسبة الارتفاع الوسيطة 0.54 والعرض 0.90 والإزاحة الرأسية ~0. السبب في التعريف: `synth2.py` يعرّف LINE = اتحاد صناديق الأرقام (ضيّق)، بينما `line_boxes.json` حزمة من `display_boxes` (ارتفاعها الوسيط 1.25× ارتفاع الأرقام، حتى 2.5×). ⇒ IoU>0.5 مع المرجع الواسع صعب حتى لو كان الموقع صحيحاً.
  أضفت مقياساً ثانياً في `eval_locator_real.py`: `recall_tight_iou50` = IoU مع اتحاد صناديق `digit_boxes.json` (نفس تعريف التدريب). لم أغيّر المقياس الأساسي.
  | ckpt | مرجع line_boxes | مرجع ضيّق digit_boxes |
  |---|---|---|
  | locator_v1 (A) | 20/46 | 17/46 |
  | locator_t step 4000 | 12/46 | 21/46 |
  أيضاً 6 صور (23074, 23085, 23086, 23088, 23091, 23092) أعلى قمة فيها على سطر آخر (إزاحة >1.1 ارتفاع)، والسطر الصحيح ضمن أعلى 5 قمم في 4 منها.

- 10:00Z ملاحظة: المقياس الحقيقي الضيّق يتذبذب بين الـ checkpoints (4000: 21، 6000: 28، 8000: 23) بينما val الاصطناعي ثابت ~150/196 ⇒ فجوة المجال (synthetic→real) هي العامل الرئيسي، وn=46 صغير (±3 صور ضوضاء). تنبيه منهجي: اختيار الـ checkpoint بأعلى نتيجة على الـ46 = ضبط على مجموعة الاختبار (ممنوع). لذلك الاختيار النهائي يكون بالـ val الاصطناعي (أو تحقق حقيقي منفصل من ERP إن توفّرت له صناديق)، وأرقام الـ46 تُنشر للمعلومة فقط. step 6000 (tight 28/46) محفوظ في git (7cecb73) للمرجع.

- 10:08Z المهمة 4: نُزّلت كل صور ERP المسمّاة الجديدة بـ `ERP_USER=… python3 erp_fetch_labelled.py` ⇒ 2349 صورة محلياً (من 2383 مسمّاة مقروءة). A بدأ `locator_ft2` من locator_t@~6000 على 361 عيّنة ضعيفة.

- 10:50Z أضفت إلى `eval_locator_real.py` مقياس `recall_tight_top3` (أفضل IoU بين أعلى 3 قمم فوق العتبة) لقياس ما يربحه اختيار السطر بعد القارئ. على الأوزان الحالية (~12.5k): tight **31/46**، top3 31/46 (أي أن القمم الأخرى فوق LOC_PEAK_MIN=0.25 قليلة؛ الأخطاء الـ15 صناديق ضعيفة التطابق IoU 0.15–0.5 أكثر منها سطراً خطأ، و3 صور (23074, 23088, 23092) سطر خطأ تماماً).
- 10:45Z رفعت `lab/plausibility.py` + 13 اختبار + `docs/research/agentT-algorithms-2026-10-18.md` (2927b68).

- 11:05Z **end-to-end A/B (المهمة 3):** locator_t@14000 + reader_ft3a (قارئ A الحالي في التطبيق):
  `python3 export_onnx.py /tmp/loc_s14000.pt weights/reader_ft3a.pt /tmp/models_t14 && python3 eval_e2e.py /tmp/models_t14 t14000`
  ⇒ **A: 16/46 exact** (كان 12/46 مع locator_ft3a)، wrong_confident 0، digit_acc 0.484، p50 18.5ms؛ B: 12/46. العتاد: Xeon 2.8GHz CPU، ORT خيطان (ليس جوالاً).
  حسب القاعدة (تجاوز أفضل e2e A في `digitnet_*.json`) نُسخ ONNX إلى `app/meterocr/src/main/assets/models/` (line_locator.onnx من locator_t@14000، digit_reader.onnx = reader_ft3a بدون تغيير). الأوزان: `lab/weights/locator_t14000.pt`.
  تحفّظ: الفرق 4 صور على n=46 (ضمن ضوضاء معتبرة)، والاختيار بالـ46 يحمل تحيّزاً — يُؤكَّد على ERP val وعلى الجوال. `MODEL_CARD.md` لم أعدّله (app/** ملك A) — يحتاج تحديثاً من A.

- 11:03Z e2e step 14500: locator_t@14500 + reader_ft3a.pt: A exact 17/46, wrong_confident 0, p50 18.3ms (best previous A = 16). cmd: export_onnx.py + eval_e2e.py /tmp/models_t14500 t14500
## كل 500 خطوة (الخطوة العامة = خطوة اللوغ بعد الاستئناف + 1000)
- 0: loss 15.707 val 0/196
- 500: loss 8.054 val 0/196
- 1000: loss 3.666 val 33/196
- 1500: loss 3.092 val 70/196

- 2000: loss 2.782 val 108/196
- 2500: loss 2.507 val 93/196
- 3000: loss 2.243 val 105/196
- 3500: loss 2.055 val 138/196
- 4000: loss 2.007 val 134/196
- 4500: loss 1.895 val 131/196
- 5000: loss 1.804 val 134/196
- 5500: loss 1.705 val 145/196
- 6000: loss 1.657 val 150/196
- 6500: loss 1.601 val 149/196
- 7000: loss 1.617 val 153/196
- 7500: loss 1.545 val 151/196
- 8000: loss 1.525 val 151/196
- 8500: loss 1.492 val 150/196
- 9000: loss 1.409 val 152/196
- 9500: loss 1.444 val 151/196
- 10000: loss 1.424 val 154/196
- 10500: loss 1.364 val 158/196
- 11000: loss 1.342 val 160/196
- 11500: loss 1.298 val 165/196
- 12000: loss 1.330 val 156/196
- 12500: loss 1.260 val 162/196
- 13000: loss 1.206 val 165/196
- 13500: loss 1.190 val 163/196
- 14000: loss 1.200 val 164/196
- 14500: loss 1.228 val 161/196
## Checkpoints
| step | val اصطناعي | loss | سطر حقيقي IoU>0.5 | وقت |
|---|---|---|---|---|
| 2000 | 108/196 | 2.782 | 17/46 (37.0%), IoU med 0.419, found 44 | 08:53Z |
| 4000 | 134/196 | 2.007 | 12/46 (26.1%), IoU med 0.424, found 42 | 09:14Z |
| 6000 | 150/196 | 1.657 | 15/46 (32.6%), IoU med 0.396, tight 28/46, found 43 | 09:34Z |
| 8000 | 151/196 | 1.525 | 11/46 (23.9%), IoU med 0.365, tight 23/46, found 41 | 09:54Z |
| 10000 | 154/196 | 1.424 | 11/46 (23.9%), IoU med 0.371, tight 21/46, found 40 | 10:15Z |
| 12000 | 156/196 | 1.330 | 15/46 (32.6%), IoU med 0.396, tight 23/46, found 40 | 10:35Z |
| 14000 | 164/196 | 1.200 | 17/46 (37.0%), IoU med 0.432, tight 26/46, found 42 | 10:55Z |
