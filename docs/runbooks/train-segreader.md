# Runbook: تدريب SegReader
**متى:** تجربة تدريب جديدة · **المدة:** ~16 دقيقة لكل 1000 خطوة على 3 خيوط (سندبوكس) · **الصلاحيات:** —

## قبل البدء (لا تعلّق السندبوكس — postmortem 2026-10-18)
- `free -m` لازم ≥ 5GB متاحة (train_fast يحمّل npz كامل: 888MB uint8 لـ 96k عينة).
- استخدم `TORCH_THREADS=2` واتركه في الخلفية. لا تنتظره بأمر طويل؛ راقب بـ `tail -n 3 ../lab/logs/<run>.log`.

## الخطوات (من `lab/`)
1. بيانات (لو غير موجودة): `nohup python3 gen_data.py 96000 ../data/synth/syn_a.npz 1000 > ../lab/logs/gen.log 2>&1 &`
2. تدريب جديد:
   `TORCH_THREADS=2 nohup python3 train_fast.py <steps> 0.75 weights/<name>.pt ../data/synth/syn_a.npz > ../lab/logs/<name>.log 2>&1 &`
3. استكمال من نقطة: أضف المسار كوسيط خامس، مثال (هذا ما أنتج v2 تقريباً):
   `TORCH_THREADS=2 nohup python3 train_fast.py 4000 0.75 weights/rec_w075_v3.pt ../data/synth/syn_a.npz weights/rec_w075.pt > ../lab/logs/v3.log 2>&1 &`
   ⚠️ `OneCycleLR` يبدأ من جديد عند الاستكمال (warm-up جديد).
4. السجل يطبع كل 1000 خطوة: `step N loss X real K/46`. «real» = تقييم على الـ 46 للمراقبة فقط — **ممنوع** اختيار
   checkpoint أو معاملات بناءً عليه بشكل متكرر (تسرب؛ REQ-001.18). للاختيار نحتاج مجموعة validation منفصلة (اصطناعية أو صور ERP).
5. بعد الانتهاء: `python3 eval_rec.py weights/<name>.pt`.

## التحقق من النجاح
- سطر في `docs/research/benchmark-summary.md` §3 (الأمر، الخطوات، الخسارة، الحقيقي، الوزن، السجل).
- commit للوزن (< 5MB) + السجل + ملف النتائج، ثم push.

## التراجع
الأوزان القديمة محفوظة بأسمائها؛ لا تكتب فوق `rec_w075.pt`.
