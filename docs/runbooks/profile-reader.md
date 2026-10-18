# تشغيل قارئ القالب الهندسي واستكمال تطويره

**الحالة: نموذج بحثي عامل، لا يُستخدم للفوترة الآلية.** قراءة المقاطع لا تزال ترفض معظم القصاصات الحقيقية المتاحة.
ابدأ بسجل التسليم: [`../history/2026-10-18-optical-sprint-handoff.md`](../history/2026-10-18-optical-sprint-handoff.md).

## 1. جلب الفرع الصحيح

```bash
git fetch origin
git switch --create optical-continuation --track origin/genspark_ai_developer_optical_20261018
git fetch origin 5486ed44510ca1930e1dc119eee08b47a3d6486f
```

لا تدفع إلى `origin/genspark_ai_developer`؛ ذلك فرع وكلاء آخرين. طلب الدمج البحثي: https://github.com/moain2026/almaham-3/pull/2.

## 2. المتطلبات المستقلة

Python 3.13، CPU فقط، لا نموذج ولا تدريب. من جذر المشروع:

```bash
mkdir -p data/python data/tmp
TMPDIR="$PWD/data/tmp" PIP_CACHE_DIR="$PWD/data/pip-cache" \
  python -m pip install --target data/python -r requirements-optical.txt
export PYTHONPATH="$PWD/data/python:$PWD/lab"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
```

لا نستبدل `requirements-lab.txt` الخاصة بتدريب الوكلاء. ZXing يخص مسار الهوية السابق ولا يلزم للخوارزمية الهندسية نفسها.

## 3. تجربة مرئية بأمر واحد — لا بيانات عملاء

```bash
python lab/profile_cli.py demo --out data/profile_sprint/public/demo.html
```

افتح HTML محليًا. الصور والنتائج مضمّنة داخله ولا تحتاج اتصالًا بالإنترنت.
يعرض 6 حالات محسوبة بالفعل: واضح، حجب أول، حجب ثانٍ، دمجهما، حركة، وتغير القراءة.
القالب يعرض 888888 لكن المدخل يعرض رقمًا آخر؛ الاختبارات تتحقق من عدم نسخ أرقام القالب.
هذا **عرض نتائج وليس واجهة رفع صور أو تطبيق كاميرا**.

لعرضه مؤقتًا من السندبوكس:

```bash
python -m http.server 8080 --bind 0.0.0.0 --directory "$PWD/data/profile_sprint/public"
```

يجب طلب رابط المنفذ بأداة GetServiceUrl. الرابط مؤقت ويتوقف إذا توقف السندبوكس.
**لا تخدم جذر المشروع أو data/ أو مجلد تقارير العملاء.** مجلد public مخصص للمشاهد المولدة فقط.

## 4. إنشاء ملف تعريف لعدادك — هندسة لا إجابة

ضع صورة مرجعية جيدة للشاشة أو سطر الأرقام في `data/my_meter/reference.png`.
لا تسجل القيمة الصحيحة في ملف التعريف. المطلوب مواضع الخانات الصحيحة، لا الكسور أو الوحدة.

```bash
python lab/profile_cli.py enroll \
  --image data/my_meter/reference.png \
  --profile data/my_meter/profile.json --digits 6
```

ينتج:
- `profile.json`: البكسلات المرجعية الخاصة، الهندسة، SHA256، وحالة تأكيد التخطيط.
- `profile.html`: معاينة الخانات والقياسات.
- `profile.result.json`: النتائج التشخيصية، **ولا يستبدل profile.json**.

افتح المعاينة وتحقق من: عدد الخانات، موضعها، عدم إدراج الكسور/الوحدة، وأنها من العداد المطلوب.
بدون تأكيد تبقى `verified=false` ولا يقبل القارئ قيمة. بعد التحقق أعد أمر enrollment مع `--confirm-layout`.
هذه الراية تعني أن المستخدم راجع الهندسة؛ **ليست شهادة دقة للخوارزمية أو إثبات هوية العداد**.

### عندما يفشل الاقتراح التلقائي

أنشئ ملف JSON خاصًا بمستطيلات الخانات بإحداثيات الصورة المرجعية الأصلية:

```json
[[28,36,64,116],[78,36,114,116],[128,36,164,116],[178,36,214,116],[228,36,264,116],[278,36,314,116]]
```

هذه إحداثيات **المثال الاصطناعي فقط**؛ لا تنسخها إلى عداد حقيقي. عدّلها بصريًا لكل طراز/قالب:

```bash
python lab/profile_cli.py enroll --image data/my_meter/reference.png \
  --profile data/my_meter/profile.json --digits 6 \
  --cells data/my_meter/cells.json --confirm-layout
```

يدعم Profile من 1 إلى 10 خانات؛ ليس كل عداد ست خانات. يجب أن تكون الخلايا مرتبة ولا تتداخل.
معايرة هندسة صورة الاختبار نفسها تدخل ضمن **oracle geometry**، لا اختبار تحديد تلقائي مستقل.

## 5. قراءة صورة جديدة أو مجموعة إطارات

```bash
python lab/profile_cli.py read --profile data/my_meter/profile.json \
  --images data/my_meter/frame1.png data/my_meter/frame2.png \
  --out data/my_meter/reading.html
```

- من 1 إلى 8 إطارات لنفس العداد ونفس سجل kWh. الصور المتطابقة بالبصمة تُحسب مرة واحدة.
- محاذاة ECC تستعمل الخلفية خارج الخانات، بحدود صغيرة للحركة والدوران؛ لا كاشف شاشة عامة من صورة شارع كاملة.
- إطاران بسجلين مختلفين/مقاطع متناقضة ⇒ رفض الدمج.
- سياسة CLI الافتراضية: **جميع المقاطع مرصودة بعد الدمج**، بالإضافة إلى شروط القارئ.
- `candidate_value` مرشح قد يكون مستنتجًا من دليل ناقص؛ **لا تستخدمه للتعبئة**. `value` قيمة مشروطة لا ضمانًا ماليًا.
- `production_approved=false` دائمًا حتى تنتهي الاختبارات الميدانية.
- `--already-aligned` يعطّل التسجيل صراحةً؛ لا تستخدمه على لقطات كاميرا مختلفة الموضع.
- الاختلاف الكبير في نسبة الأبعاد مرفوض. `profile_reader.rectify_quad` يوفر homography لأربع زوايا صريحة في API؛
  اكتشاف الزوايا آليًا وواجهة تحديدها غير منفذين هنا.

التقارير والقوالب **خاصة**؛ CLI يمنع كتابتها خارج `data/`. لا ترفعها إلى git.
الملفات محدودة 20MB والمدخلات 12MP؛ أبعاد الصور تفحص قبل فك البكسلات لتقليل خطر نفاد الذاكرة.

## 6. واجهة البرمجة

```python
from profile_cli import load_profile, read_image
from profile_reader import read_frames
from profile_policy import require_observed_segments

profile = load_profile('data/my_meter/profile.json')
raw = read_frames([read_image('data/my_meter/frame1.png')], profile, register=True)
result = require_observed_segments(raw)  # واجهة قبول CLI؛ لا تستخدم raw.value مباشرة
print(result['value'], result['status'])
```

`read_frames` يحافظ على نتائج القارئ المشروطة الأصلية لأغراض البحث. السياسة منفصلة عمدًا كي لا نمحو فشل التجربة الأولى.
ملف التعريف ليس قاعدة بيانات مشترِك: مسار `serial_identity.py` السابق منفصل، ولم يُربط بعد بهوية Profile أو الكاميرا.

## 7. الاختبارات وإعادة القياس

```bash
python -m unittest discover -s lab -p 'test_*.py' -v
python -m ruff check lab/optical_evidence.py lab/serial_identity.py \
  lab/bench_optical_evidence.py lab/test_optical_evidence.py \
  lab/profile_reader.py lab/profile_policy.py lab/profile_cli.py \
  lab/bench_profile_reader.py lab/bench_profile_policy.py lab/test_profile_reader.py
bash scripts/check.sh
python lab/bench_profile_reader.py \
  --out benchmark/results/engines/profile_reader_2026-10-18.json
python lab/bench_profile_policy.py \
  --out benchmark/results/engines/profile_policy_2026-10-18.json
```

64 اختبارًا في الملفين. scripts/check.sh لا يعيد تقييم SegReader إذا لم توجد الأصول الـ49.
الـJSON الخام كبير؛ لا تفتحه كله بأداة قراءة نصية. مثال استخراج الملخص:

```bash
python - <<'PY'
import json
p='benchmark/results/engines/profile_policy_2026-10-18.json'
r=json.load(open(p))
print(json.dumps(r['fresh_summary'], indent=2))
print(json.dumps(r['posthoc_summary']['real'], indent=2))
PY
```

## 8. النتائج التي يجب ألا تختلط

الأوامر أعلاه، CPU سندبوكس x86_64 بخيط OpenCV/BLAS واحد. لا هاتف.

| المجموعة | النتيجة | التفسير |
|---|---|---|
| 30 مشهدًا اصطناعيًا واضحًا | 30 صحيحًا | هندسة معروفة، ليست صور ميدان |
| نفس الـ30 بعد الحركة | 30 صحيحًا | تسجيل خلفية ثابتة |
| إطار محجوب لكل مشهد | 30 رفضًا | لا اختراع للمقطع المفقود |
| إطاران بحجب متكامل | 30 صحيحًا | إثبات عمل دمج المقاطع |
| تحدي قديم: 60 مشهدًا مختلطًا | 60 صحيحًا | استُخدم لاحقًا لتشخيص السياسة |
| نفس التحدي مع حجب موضعي، قبل السياسة | 1 صحيح، **2 خاطئ**، 57 رفضًا | الفشل محفوظ في profile_reader JSON |
| نفس التحدي بعد السياسة | 60 رفضًا | تقييم post-hoc، ليس إثبات تعميم |
| تحدٍّ جديد seed=20261020، 40 مشهدًا | 40 صحيحًا | تحقق اصطناعي جديد بعد تثبيت السياسة |
| الحجب الموضعي في التحدي الجديد | 1 صحيح، 0 خطأ، 39 رفضًا | أمان أعلى مقابل رفض شبه كامل؛ ليست دقة قراءة 100% |
| أصل القصاصات الحقيقية الخمس، السياسة النهائية | 1 صحيح مرجعيًا، 0 خطأ، 4 رفض | المرجع المقبول نفسه uncertain=1؛ **0/4 مقبول على المراجع المؤكدة** |
| القصاصات مع محو الشريط، السياسة النهائية | 5 رفض، 0 خطأ | لا يعني حل الوهج عمومًا |

زمن وسيط تقريبي في التنفيذ المحفوظ: 63ms للواضح الاصطناعي، 90ms مع التسجيل، 126ms لدمج إطارين؛
والتحدي الجديد نحو 99–101ms/صورة. ليس من ضغطة الكاميرا ولا معيار أداء هاتف.

**إذن البنية تعمل، لكن التغطية الواقعية ضعيفة جدًا.** لا نُخفي ذلك تحت نجاح الاصطناعي.
الـ3/5 القديمة عند دمج الأصل مع نسخة ممحوة تخص المرشح المشروط قبل السياسة؛ لم تعد قيمة مقبولة في CLI.
تغيير الصورة برمجيًا لا يضيف مصدر معلومات ميدانيًا مستقلًا، حتى لو غيّر التقدير والعتبات المحلية.

## 9. الخطوة التالية — لا تبدأ تدريبًا عشوائيًا

1. الحصول على الأصول الخاصة وصور/فيديو جديد لنفس العداد، مع مرجع مصحح بشريًا وبيانات الطراز/السجل/عدد الخانات.
2. معايرة قالب على صورة، ثم اختبار صور **أخرى** لنفس الطراز ومواقع تصوير مختلفة؛ فصل القياس حسب العداد.
3. قياس التسجيل على حركات حقيقية. الحالة الحالية Euclidean صغيرة الحركة؛ لا ORB أو محدد شاشة عام أو كشف وحدة kWh.
4. معالجة فساد تقدير الخلفية تحت الوهج، مع مجموعة تطوير مستقلة. لا تعاير العتبات على الخمسة أو التحدي المحفوظ.
5. ربط الباركود/هوية العداد والتأكد من سجل kWh قبل الدمج؛ عدم الاعتماد على اسم ملف القالب.
6. جلب إطارات فعلية من الكاميرا دون تأخير الضغطة؛ ثم نقل primitives إلى التطبيق وقياس الهاتف.
7. يبقى أي دمج في المنتج ممنوعًا حتى قياس الدقة والتغطية والخطأ المقبول على مجموعة ميدانية مستقلة.
