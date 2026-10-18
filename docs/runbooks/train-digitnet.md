# Runbook: تدريب DigitNet كاملاً — من الصفر إلى نموذج في التطبيق

> آخر تحديث: 2026-10-18 11:45Z (وكيل A). هذا الدليل يكفي لإعادة إنتاج **كل** الأرقام في `docs/benchmark_report.md` §8 و`MODEL_CARD.md`، ولمواصلة التدريب في بيئة جديدة. الأرقام الحالية: e2e **19/46**، غلط-وواثق 0.

## 0. البيئة
```bash
git clone https://github.com/moain2026/almaham-3.git && cd almaham-3 && git checkout genspark_ai_developer
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-lab.txt          # torch 2.14 cpu، onnxruntime، opencv-headless، numpy (الإصدارات مثبّتة)
bash scripts/verify_photos.sh                # يتوقع data/photos/ (الـ49 صورة الخاصة — من المالك، ليست في git) ⇒ OK: 49/49
```
- **العتاد المستعمل:** سندبوكس x86، 4 أنوية، 8 GB، بلا GPU. على GPU كل شيء أسرع 20×، والأوامر نفسها.
- **قواعد البيئة (مُجرَّبة بالألم، `LESSONS.md`):** لا تشغّل gradle أثناء تدريب (يقتله: RSS 4 GB). استعمل `TORCH_THREADS=2` لكل تدريب (تدريبان بالتوازي كحد أقصى على 4 أنوية). لا `git stash -u` ولا rebase يلمس ملف سجل مفتوح؛ إن بدا السجل متوقفاً اقرأه من `/proc/<pid>/fd/1`.
- كل الصور الخاصة (الـ49، ERP) في `data/` — **متجاهلة في git** (ADR-0004). لا تُرفع لأي مكان عام.

## 1. الهندسة في سطرين
نموذجان متطابقان بنيوياً (`lab/det_model.py`: CenterNet-lite، 213k معامل، stride 4، ~850 KB ONNX كل واحد):
- **المحدِّد** `locator`: دخل 256×256 مشهد كامل → صندوق «سطر القراءة» (فئة واحدة؛ التعريف الرسمي ADR-0005 = اتحاد صناديق الأرقام الضيّق).
- **القارئ** `reader`: دخل 64×448 قصّ السطر (مع هامش `PAD_X/Y = 0.18/0.45`) → صناديق الخانات (11 فئة: 0–9 + نقطة).
- التجميع `lab/assemble.py` (المرآة الحرفية: `ReadingAssembler.kt`): دمج، تجميع أسطر، حدّ الكسر (نقطة / انخفاض ارتفاع <0.65 / قاعدة 6 خانات)، فجوات، شبكة الخلايا، التحقق السباعي `segverify.py`، ثم التصويت مع القارئ الحتمي `vote.py`.
- **الجزء الصحيح فقط** — الكسور لا تُقرأ أبداً (قرار المالك).

## 2. ملفات التدريب (ما يفعله كل سكربت)
| الملف | الدور | أهم المعاملات |
|---|---|---|
| `synth2.py` | مولّد البيانات الاصطناعية: شاشات LCD سباعية (خطوط DSEG OFL + مقاطع إجرائية)، لوحات عدادات، كتابة عربية، أرقام مطبوعة سلبية، `PAD_GREY=128` مطابق للتطبيق | `LINE_W=448`, `CLS_LINE=11` |
| `gen_det_data.py` | يكتب شاردات `X.npy` (uint8 NHWC) + `B.npy` (idx,cls,x1,y1,x2,y2) | `line\|scene N out seed` |
| `det_model.py` | الشبكة + `decode()` + خسائر (focal + L1 للحجم والإزاحة) | `LOCATOR_CLASSES=1`, `READER_CLASSES=11` |
| `train_det.py` | التدريب الاصطناعي الصرف؛ يحفظ ويقيّم كل 250 خطوة على هولد-أوت اصطناعي | `reader\|locator steps out shards [init]`؛ `BATCH={reader:32, locator:24}` |
| **`erp_finetune.py`** | **الضبط الدقيق على صور ERP الحقيقية** (الجزء الذي صنع كل التحسن): `build` يصنع تسميات صناديق ضعيفة من نصوص التسمية، `train` يدرّب 50/50 حقيقي/اصطناعي | انظر §4 |
| `erp_fetch.py` / `erp_fetch_labelled.py` | تنزيل صور ERP (شريحة حتمية بذرة 7) / فقط الصور التي لها تسمية مقروءة | `ERP_USER/ERP_PASS` من المالك |
| `erp_vlm_label.py` (وكلاء التسمية) | تسمية آلية بنموذج رؤية: 3–4 قراءات مستقلة + إجماع وإلا X | المخرجات في `benchmark/data/erp/labels_*.csv` |
| `export_onnx.py` | PyTorch → ONNX (NHWC 0–255، التطبيع وNMS 3×3 داخل الرسم) + فحص تطابق torch/ORT | `loc.pt rd.pt out_dir` |
| `eval_e2e.py` | القياس النهائي على الـ49: الوضعان A (مستطيل) وB (كاملة)، يكتب JSON+CSV لكل صورة وصور مراجعة في `data/review/e2e_<tag>/` | `models_dir tag` |
| `eval_reader_oracle.py` | القارئ وحده على قصّ السطر المثالي (سقف المحرك) | `reader.pt` |
| `eval_locator_real.py` (وكيل T) | المحدِّد على الـ49: `recall_tight_iou50` (الرسمي) + الواسع | `loc.pt tag` |
| `eval_vote.py` | عصبي × حتمي (`forensic_reader.py` وكيل B) × تصويت | `models_dir tag` |
| **`eval_ckpt.sh`** | **كل ما سبق بأمر واحد** لزوج أوزان | `loc.pt rd.pt tag` |
| `report.py` | جداول markdown لكل صورة | `tag` |
| `plausibility.py` (وكيل T) | فحوص معقولية القراءة (تُدمج في الألوان لاحقاً) | 13 اختباراً |
| `test_assemble.py`, `test_plausibility.py` | اختبارات بايثون — شغّلها بعد أي تعديل في التجميع | |

## 3. المرحلة الاصطناعية (مرة واحدة؛ البيانات موجودة في `data/synth/`، 11 GB)
```bash
cd lab
python3 gen_det_data.py line  16000 ../data/synth/line_a  11   # و line_b 12، line_c 13   (~15 دقيقة لكل أمر)
python3 gen_det_data.py scene 12000 ../data/synth/scene_a 21   # و scene_b 22، scene_c 23؛ وكيل T: scene_t1..t3 بذور 201–203
TORCH_THREADS=2 nohup python3 train_det.py reader  6000  weights/reader_v1.pt  ../data/synth/line_a,../data/synth/line_b  > logs/train_reader_v1.log 2>&1 &
TORCH_THREADS=3 nohup python3 train_det.py locator 20000 weights/locator_t.pt  ../data/synth/scene_t1,../data/synth/scene_t2,../data/synth/scene_t3 > logs/train_locator_t.log 2>&1 &
```
ما حدث فعلاً: القارئ v1 توقف عند 2000 خطوة (`reader_v1_s2000.pt`، 74/195 اصطناعي)؛ المحدِّد T توقف تلقائياً عند 14500 (أفضل 165/196 اصطناعي، ضيّق حقيقي 26/46) — `docs/training-log-agentT.md`. **درس:** استئناف القارئ بـ lr 5e-4 أفسده (45→39/97) ⇒ lr 2e-4 للضبط الدقيق.

## 4. مرحلة الضبط الدقيق على ERP (هي التي رفعت 0 → 19/46)
### 4.1 التسميات
وكلاء التسمية يدفعون `benchmark/data/erp/labels_slice_<k>.csv` (`filename,text,labeller,ts,n_labels`؛ `X` غير مقروء، `P` جزئي). **تحذير:** آلية، خطؤها 10–17% في المراجعة اليدوية؛ لا تُستعمل كحقيقة تقييم. الصور الـ49 مستبعدة بـ SHA256 تلقائياً في `build`.

### 4.2 الحلقة (self-training) — كما نُفّذت حرفياً
```bash
cd lab
ERP_USER=… ERP_PASS=… python3 erp_fetch_labelled.py                                   # ينزّل كل صورة لها تسمية مقروءة إلى data/erp/photos/
python3 erp_finetune.py build weights/<locator>.pt weights/<reader>.pt ../data/erp/ft/ftN   # تسميات صناديق ضعيفة
TORCH_THREADS=2 nohup python3 erp_finetune.py train weights/<reader_init>.pt  ../data/erp/ft/ftN ../data/synth/line_b,../data/synth/line_c   <steps> weights/reader_ftN.pt  reader  > logs/train_reader_ftN.log  2>&1 &
TORCH_THREADS=2 nohup python3 erp_finetune.py train weights/<locator_init>.pt ../data/erp/ft/ftN ../data/synth/scene_b,../data/synth/scene_c <steps> weights/locator_ftN.pt locator > logs/train_locator_ftN.log 2>&1 &
bash eval_ckpt.sh weights/locator_X.pt weights/reader_Y.pt <tag>     # على الـ49 (تقييم فقط)
```
**قاعدة `build` (حتمية، مسجّلة في `ftN_report.json`):** يُقبل المثال إذا وجد القارئ عدد خانات = طول النص (أو أنقذته شبكة خلايا منتظمة بنفس العدد)، والخلايا منتظمة (نسبة الخطوة ≤1.5، الارتفاعات ≥0.75)؛ الفئات := نص التسمية. يُنتج شاردات للقارئ (`ftN_{train,val}`) وللمحدِّد (`ftN_loc_{train,val}`، الصندوق = اتحاد الخانات حسب ADR-0005). التقسيم 85/15 بأول 8 أحرف من اسم الملف.

### 4.3 الجولات المنفَّذة (كل الأرقام على الـ46 المقروءة)
| جولة | مبنية بـ | صور محلية → مقبولة | تدريب | e2e A | القارئ L | المحدِّد ضيّق |
|---|---|---|---|---|---|---|
| ft2 | locator_t@8000 + reader_v1_s2000 | 614 → 361 | reader 2000 / locator 2000 | 6 | 10 | 28 |
| + إصلاح حدّ الكسر (`assemble.py` 0.8→0.65 + قاعدة 6 خانات) | — | — | — | 9 | — | — |
| ft3 | ft2 | 1829 → 923 | reader 2500 (ذروة real_val 71/116 @1250) / locator 1500 | 12 (ft3a) · 14 (نهائي) | 18 · 16 | 30 |
| ft4 | ft3 | 2216 → 1703 | reader 3000 (real_val 152/194 @1500–2750) / locator 1500 (193/194) | **19** (مع locator_t14500) · 18 (مع locator_ft4@500) | 19 | 31 (ft4a) |
الأوزان: `lab/weights/{reader,locator}_ft{2,3,4}.pt`, `reader_ft3a.pt`, `reader_ft4a.pt`, `locator_t14500.pt` (كلها في git، ~950 KB لكل واحد).

### 4.4 كيف تختار ما تشحنه (لمنع التسريب)
1. اختر نقطة الحفظ بـ `real_val_*` في سجل التدريب (ERP فقط)، **لا** بالـ49.
2. أكّد على الـ49 بـ `eval_ckpt.sh`؛ الشرط: `exact` أعلى **و** `wrong_confident == 0`.
3. انسخ `../data/models_<tag>/*.onnx` إلى `app/meterocr/src/main/assets/models/`، حدّث `MODEL_CARD.md` (المصدر، الأرقام، الأمر)، commit برسالة تبدأ بـ `model:` ⇒ وكيل التطبيق يعيد البناء (ويحوّل إلى `.ort` حسب `docs/release-0.2.0.md`).
4. أضف سطراً في `docs/benchmark_report.md` §8 و`STATUS.md`.

## 5. ما تبقّى من التدريب (بالترتيب)
1. **ft4 ينتهي الآن** (reader 2750/3000) → `eval_ckpt.sh weights/locator_t14500.pt weights/reader_ft4.pt t14500_ft4final` و`… weights/locator_ft4.pt …`. اشحن إن تحسّن (§4.4).
2. **ft5**: بعد اكتمال تنزيل التسميات الجديدة (4,329 مقروءة الآن؛ ~15k عند اكتمال الشرائح الأربع). ابدأ المحدِّد من `locator_t14500.pt` (توصية وكيل T). الأوامر في `docs/PLAN.md` §3.
3. **اختيار السطر بعد القراءة**: قراءة أعلى 3 مرشحات للمحدِّد واختيار من يعطي 6 خانات منتظمة — في `assemble.py` + `ReadingAssembler.kt` (أكبر مصدر خطأ متبقٍّ، ~8 صور).
4. **خانات باهتة (Tomas)**: تدريب موجّه بعيّنات هذا النوع + تعزيز تباين منخفض في `synth2.py`.
5. **مجموعة اختبار أكبر**: 300–500 صورة ERP بتسمية **بشرية** مجمّدة؛ 46 صورة = ±7% ضوضاء.
6. **المحدِّد على الحقيقي من الصفر** (لا ضبط فقط) إذا بقي <60% بعد ft5.
7. **المحرك الحتمي الثالث**: `multi_algo.py` (B، 20/46 على قصّ) و`profile_reader.py` (فرع optical) — يُقاسان بـ `eval_vote.py` قبل أي دمج.

## 6. التحقق قبل أي push يمس المحرك
```bash
cd lab && python3 test_assemble.py && python3 test_plausibility.py
cd ../app && JAVA_HOME=<jdk17> ./gradlew :meterocr:testDebugUnitTest      # فقط إذا لا تدريب يعمل
```
`ReadingAssembler.kt` و`MeterOcrConfig.kt` يجب أن يطابقا `assemble.py`/`CONFIG` حرفياً (اختبارات `ReadingAssemblerTest`).
