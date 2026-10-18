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

## كل 500 خطوة (الخطوة العامة = خطوة اللوغ بعد الاستئناف + 1000)
- 0: loss 15.707 val 0/196
- 500: loss 8.054 val 0/196
- 1000: loss 3.666 val 33/196
- 1500: loss 3.092 val 70/196

## Checkpoints
| step | val اصطناعي | loss | سطر حقيقي IoU>0.5 | وقت |
|---|---|---|---|---|
| 2000 | 108/196 | 2.782 | 17/46 (37.0%), IoU med 0.419, found 44 | 08:53Z |
