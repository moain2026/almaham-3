# الانتقال الكامل إلى بيئة جديدة — فرع التجارب البصرية

هذا الدليل خاص بـ `genspark_ai_developer_optical_20261018` و[PR #2](https://github.com/moain2026/almaham-3/pull/2).
الفرع **نسخة مستودع كاملة** مبنية على main، وليس حزمة ملفات فرق فقط. لا يدمج تلقائيًا تحديثات تطبيق الوكلاء الآخرين في فرعهم.

## اختبار الانتقال الذي نُفذ بالفعل

استُنسخ الفرع من GitHub عند `7842d07` إلى دليل جديد، وأنشئت virtualenv بلا system-site-packages،
وثُبتت كل المتطلبات من `requirements-optical.txt`. نجحت 64/64 اختبارات، وأُعيد توليد العرض،
وأُعيدت القياسات الثلاثة. تطابقت قرارات 360 حالة profile/policy (value/status/states/candidates)
بالإضافة إلى توقعات القصاصات والتصويت المحفوظ واختبارات الباركود. الأزمنة ليست معيار تطابق.
السجل الكامل: [`../../benchmark/results/verified_fresh_environment_2026-10-18.txt`](../../benchmark/results/verified_fresh_environment_2026-10-18.txt).
التغييرات اللاحقة لذلك المرجع تخص دليل الانتقال والتوثيق وسجل التحقق، لا خوارزميات الاستدلال.

## ما رُفع إلى الفرع؟

1. كل ملفات المستودع الأصلية المتتبعة عند نقطة البداية: تعليمات ومتطلبات وبيانات benchmark وأصول الكود والأوزان الموجودة سلفًا.
2. المحركات الجديدة: `lab/optical_evidence.py` و`lab/profile_reader.py` و`lab/profile_policy.py` و`lab/serial_identity.py`.
3. التشغيل: `lab/profile_cli.py` و`requirements-optical.txt`.
4. القياس: `lab/bench_optical_evidence.py` و`lab/bench_profile_reader.py` و`lab/bench_profile_policy.py`.
5. الاختبارات: `lab/test_optical_evidence.py` و`lab/test_profile_reader.py`، 64 اختبارًا.
6. النتائج الخام، بما فيها الأخطاء: `benchmark/results/engines/{optical_evidence,profile_reader,profile_policy}_2026-10-18.json`.
7. سجل التحقق `benchmark/results/verified_optical_sprint_2026-10-18.txt`، وتقارير البحث والخطة والتسليم وSTATUS/CHANGELOG.
8. دليل التشغيل التفصيلي: [`profile-reader.md`](profile-reader.md).
9. سجل التنفيذ والمهام التالية: [`../history/2026-10-18-optical-sprint-handoff.md`](../history/2026-10-18-optical-sprint-handoff.md).

## ما لا يدخل Git العام؟

- `data/research/`: نسخ خمس قصاصات ARGB/PNG، لوحة مراجعة، سجلات ومسودات تجارب محلية.
- `data/profile_sprint/`: العرض المولد وتقارير ومسودات وسجلات التشغيل.
- `.venv`، `data/python`، pip cache، ملفات Python المترجمة، ذاكرة الأدوات المؤقتة وإعدادات الاعتماد.
- **الأصول الـ49 غير موجودة في هذه البيئة أصلًا**؛ لا توجد حزمة ترفعها هذه الجلسة ولا ينبغي ادعاء حفظها.

الكود والنتائج النهائية والتوثيق كلها في Git. المواد المحلية الصغيرة المفيدة تُسلّم في **أرشيف خاص منفصل**،
ولا تُنشر صور العملاء في الفرع العام. لا حاجة إلى نقل حزم Python المثبتة أو caches؛ تُثبَّت من ملف المتطلبات.

## الاستعادة الموصى بها من GitHub

تحتاج Git وPython 3.13 وإنترنت لتنزيل حزم PyPI. جميع الأوامر من مساحة عملك المسموح بها:

```bash
git clone --single-branch --branch genspark_ai_developer_optical_20261018 \
  https://github.com/moain2026/almaham-3.git almaham-3-optical
cd almaham-3-optical

# المرجع المثبت يحتوي قصاصات الاختبار وقارئات المقارنة من فرع الوكلاء؛ لا يغير checkout.
git fetch origin \
  5486ed44510ca1930e1dc119eee08b47a3d6486f:refs/handoff/fixture_source

mkdir -p data/tmp
TMPDIR="$PWD/data/tmp" python3.13 -m venv .venv
export PATH="$PWD/.venv/bin:$PATH"
TMPDIR="$PWD/data/tmp" PIP_CACHE_DIR="$PWD/data/pip-cache" \
  python -m pip install -r requirements-optical.txt
export PYTHONPATH="$PWD/lab"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1

python -m pip check
python -m unittest discover -s lab -p 'test_*.py' -v
bash scripts/check.sh
python lab/profile_cli.py demo --out data/profile_sprint/public/demo.html
```

في البيئات التي اسم مفسر Python 3.13 فيها `python` بدل `python3.13`، استعمل الاسم المناسب بعد التحقق بـ`python --version`.
لا تضف `--system-site-packages`: اختبار النقل يستهدف بيئة معزولة فعلًا.

### إعادة القياسات دون استبدال نتائج Git الأصلية

```bash
python lab/bench_optical_evidence.py --barcode --peers --out data/reproduced_optical.json
python lab/bench_profile_reader.py --out data/reproduced_profile.json
python lab/bench_profile_policy.py --out data/reproduced_policy.json
```

قارن التوقعات وحالات القبول والرفض، **لا الأزمنة**؛ الأزمنة تتغير مع الجهاز والحمل.
الصور المرجعية تستخرج من Git بالبصمة، لا تعتمد على بقاء `data/research` أو السندبوكس القديم.
الاختبار الاصطناعي والعرض لا يحتاجان صورًا خاصة أصلًا.

### لماذا fetch إضافي؟

القصاصات وقارئا `forensic_reader` و`multi_algo` موجودة في التزام ثابت من فرع الوكلاء، لا في شجرة فرعنا.
الـharness يستخدم `git show` لذلك المرجع. الاستنساخ بـ`--single-branch` وحده لا يكفي لتشغيل مقارنات الصور.
أمر fetch أعلاه يحفظ المرجع محليًا تحت `refs/handoff/fixture_source` ويمنع فقده بجمع القمامة.
لا تدفع هذا المرجع أو صور القصاصات إلى فرعنا العام.

## الاستعادة من الأرشيف الخاص عند تعذر GitHub

الأرشيف المرفق بالمحادثة اسمه `almaham_optical_handoff_2026-10-18.tar.gz`، ويحتوي:
- `source.bundle`: مستودع Git قابل للاستنساخ، يشمل فرع التسليم والمرجع المثبت للقصاصات؛ لا credentials أو `.git/config`.
- `data/research/` و`data/profile_sprint/`: المخرجات المحلية المفيدة كما كانت، بما فيها العرض.
- `MANIFEST.json`: أسماء الملفات وأحجامها وبصمات SHA256 ومرجع المصدر.
- `RESTORE.txt`: أوامر الاستعادة.

بعد فك الأرشيف في مجلد خاص:

```bash
git clone --branch genspark_ai_developer source.bundle almaham-3-optical
cd almaham-3-optical
git fetch ../source.bundle refs/handoff/fixture_source:refs/handoff/fixture_source
# اسم الفرع داخل bundle محلي؛ لا تتركه مطابقًا لاسم فرع الوكلاء عند إعادة ربط GitHub.
git branch -m optical-continuation
git branch --unset-upstream
# إعادة ضبط origin إذا أردت متابعة العمل على GitHub بدل ملف bundle المحلي:
git remote set-url origin https://github.com/moain2026/almaham-3.git
# الدفع لاحقًا يكون إلى optical-continuation/فرع جديد، لا genspark_ai_developer.
```

يمكن نسخ مجلدَي data الخاصين من الأرشيف إلى جذر clone. لا تنسخ virtualenv من جهاز آخر.
ثم نفّذ تثبيت المتطلبات والاختبارات أعلاه. **bundle يحفظ الكود والمرجع دون GitHub، لكنه لا يتضمن حزم PyPI للتثبيت دون إنترنت.**
بصمة الأرشيف النهائية تُرسل في المحادثة؛ الرابط الخاص لا يُنشر داخل هذا المستودع العام.

## أين يبدأ الوكيل التالي؟

1. اقرأ سجل التسليم وخطة A-01 إلى A-04 قبل تعديل أي خوارزمية.
2. أعد الاختبارات والعرض للتأكد من سلامة البيئة.
3. راجع النتائج السلبية، خاصة ضعف التغطية على الحقيقي: السياسة النهائية تقبل 1/5 ومرجعها غير مؤكد؛ ليست دقة ميدانية مثبتة.
4. اطلب صورًا وإطارات جديدة مستقلة. لا تضبط على الخمس ولا تسمِّ نسخ Gamma فيديوهات حقيقية.
5. لا تدفع إلى فرع الوكلاء `origin/genspark_ai_developer`. استخدم فرع عمل جديدًا وPR مستقلًا أو حدّث PR #2 باتفاق.
6. لا تعتمد رابط عرض السندبوكس كنسخة احتياطية؛ HTML يُعاد توليده بأمر demo.
