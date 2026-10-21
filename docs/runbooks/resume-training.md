# Runbook: استئناف العمل في بيئة جديدة تماماً (sandbox/جهاز جديد) — حالة 2026-10-21 12:00Z
**الهدف:** وكيل جديد يصل إلى نفس حالة وكيل S خلال ≤30 دقيقة ويواصل التدريب على نفس المعايير. كل ما يلزم **موجود في المستودعين + Contabo**؛ لا شيء يعتمد على sandbox قديم.

## 0) أين كل شيء
| ماذا | أين | ملاحظة |
|---|---|---|
| الكود، الأوزان النهائية (.pt ~1MB)، النتائج، السجلات، الوثائق | `github.com/moain2026/almaham-3` فرع **`genspark_ai_developer`** | عام — لا صور عملاء ولا أسرار |
| صور ERP (7144)، الـ49، قصّ العداد حسب النوع، manifests، أرشيف الأوزان/السجلات/النتائج، **شرائح التدريب الجاهزة** | `github.com/moain2026/almaham-3-private-data` (خاص) | `training_shards/2026-10-21_m3/` = m3 + ft6 + text_locate_all.json |
| الشرائح الاصطناعية (line_s1 893MB, scene_s1, line_crystal_opt2) | Contabo `/opt/almaham/almaham-3/data/synth/` | أو أعد توليدها (`lab/gen_det_data.py`) |
| خادم الموقع + آلة تدريب ثانية | Contabo `root@80.241.221.190` (`Host basira`) | مفتاح SSH عند المالك (انظر §6) |
| الموقع الميداني | https://basirapp.site/meter/ و `/meter/label` | systemd `almaham-webdemo`، منفذ 8700 |
| مستودع الوكيل الثاني (optical2) | `github.com/moain2026/almaham-optical2-private` | للقراءة/المراجعة فقط |

## 1) البيئة (10 دقائق)
```bash
cd /home/user && git clone -b genspark_ai_developer https://github.com/moain2026/almaham-3.git webapp && cd webapp
python3 -m venv .venv && . .venv/bin/activate && pip install -q -r requirements-lab.txt    # Python 3.13; torch 2.14 cpu, ort 1.31, cv2 5.0, numpy 2.5
git clone https://github.com/moain2026/almaham-3-private-data.git ../almaham-3-private-data   # يحتاج التوكن في ~/.git-credentials
bash scripts/private_data.sh pull            # يربط data/photos و data/erp/photos و data/erp/manifests
bash scripts/verify_photos.sh                # OK: 49/49
mkdir -p data/erp/ft && cp ../almaham-3-private-data/training_shards/2026-10-21_m3/*.npy ../almaham-3-private-data/training_shards/2026-10-21_m3/*.json data/erp/ft/
# الاصطناعي: إما scp من Contabo (أسرع) أو توليد:
scp basira:/opt/almaham/almaham-3/data/synth/line_s1_\*.npy data/synth/   # أو: cd lab && python3 gen_det_data.py line 24000 ../data/synth/line_s1 1
```
**تحقق:** `cd lab && bash eval_ckpt.sh weights/locator_m1_augv2.pt weights/reader_ft6m1_augv2.pt check && python3 eval_testset_human.py ../data/models_check check` ⇒ يجب أن يعطي **A 21/39، B 19/39، 19/34** (هذه هي الأرقام المرجعية؛ إن اختلفت فالبيئة ليست مطابقة).

## 2) الحالة الحالية للنماذج (الأفضل المقاس)
- **المحدِّد:** `lab/weights/locator_m1_augv2.pt` (Contabo، قصّ عداد كامل، حدود = الصحيح فقط).
- **القارئ:** `lab/weights/reader_ft6m1_augv2.pt`.
- المنشور على الموقع: `new = data/models_m1loc_ft6m1` (ONNX مُصدَّر بـ `export_onnx.py`).
- جارٍ عند كتابة هذا: `reader_ft6m2_s0/s1`, `reader_ft6m3_s0/s1` (sandbox)، `locator_m3_augv2` (Contabo، `lab/logs/train_locator_m3_augv2.log`). إن مات sandbox قبل اكتمالها: الأوزان الوسيطة في `lab/weights/` (تُحفظ كل 250 خطوة) — أعد التشغيل من آخر checkpoint أو من `reader_ft6m1_augv2.pt`.

## 3) وصفة التدريب القياسية (لا تغيّرها دون توثيق)
```bash
cd lab && . ../.venv/bin/activate
# قارئ (sandbox، 1 نواة/تشغيل، ~50 دقيقة لـ3000 خطوة):
python3 - <<'PY'   # دمج ft6 + m3 -> ft6m3 (مع أوزان owner x2)
import numpy as np
for s in ("train","val"):
    Xa=np.load(f"../data/erp/ft/ft6_{s}_X.npy"); Ba=np.load(f"../data/erp/ft/ft6_{s}_B.npy")
    Xb=np.load(f"../data/erp/ft/m3_{s}_X.npy"); Bb=np.load(f"../data/erp/ft/m3_{s}_B.npy").copy(); Wb=np.load(f"../data/erp/ft/m3_{s}_W.npy"); Bb[:,0]+=len(Xa)
    np.save(f"../data/erp/ft/ft6m3_{s}_X.npy",np.concatenate([Xa,Xb])); np.save(f"../data/erp/ft/ft6m3_{s}_B.npy",np.concatenate([Ba,Bb])); np.save(f"../data/erp/ft/ft6m3_{s}_W.npy",np.concatenate([np.ones(len(Xa),np.float32),Wb]))
PY
SEED=0 AUG_SEED=0 AUG=v2 TORCH_THREADS=1 setsid nohup python3 erp_finetune.py train weights/reader_ft6m1_augv2.pt ../data/erp/ft/ft6m3 ../data/synth/line_s1 3000 weights/reader_<tag>.pt reader > logs/train_reader_<tag>.log 2>&1 < /dev/null &
# مع الاصطناعي الجديد لـ Crystal (patch optical2): ../data/synth/line_s1,../data/synth/line_crystal_opt2
# محدِّد (Contabo، 3 أنوية، ~3 ساعات لـ4000):
SEED=0 AUG_SEED=0 AUG=v2 TORCH_THREADS=3 python3 erp_finetune.py train weights/locator_m1_augv2.pt ../data/erp/ft/m3 ../data/synth/scene_s1 3000 weights/locator_<tag>.pt locator
```
الأعلام: `IGNORE_ROW=1` (إخفاء الخسارة — مقاس: لا أثر)، `SYNTH_STYLE=crystal` للمولّد، `LINE_CLIP` في eval_e2e (تجربة، مطفأ).

## 4) التقييم الإلزامي لكل نموذج (قبل أي ادعاء)
```bash
bash eval_ckpt.sh weights/<loc>.pt weights/<rd>.pt <tag>          # الـ49 (GT v3، 39 مقروءة) A/B
python3 eval_testset_human.py ../data/models_<tag> <tag>          # 34 بالنوع
python3 risk_coverage.py ../data/models_<tag> <tag>               # جدول القبول/الخطأ — المقياس الصادق («غلط-واثق» فارغ المعنى، انظر LESSONS)
python3 report_by_type.py <tag> weights/<rd>.pt ../data/erp/ft/ft6m3   # لوكيل D
bash ../scripts/archive_run.sh <tag>                              # أوزان+سجلات+نتائج -> الخاص؛ ثم commit/push العام
```
ثم صف في `docs/training-log/runs.md` + تحديث STATUS.md/CHANGELOG.md + commit + `git pull --rebase` + push. **بعد كل خطوة، لا في النهاية.**

## 5) إعادة بناء الشرائح من بيانات جديدة (عند رفع وكيل D دفعة)
```bash
git pull; bash scripts/private_data.sh pull
cd lab && bash run_tl_workers.sh "0 1 2" 3 ../data/erp/ft/text_locate_all.json      # توطين بإشراف النص (7s/صورة/نواة)؛ يتخطى الموجود
python3 - <<'PY'   # دمج نتائج العمال
import json,glob; m={}
for f in ["../data/erp/ft/text_locate_all.json"]+sorted(glob.glob("../data/erp/ft/text_locate_p5_*.json")):
    for k,v in json.load(open(f)).items():
        if k not in m or (v and not m.get(k)): m[k]=v
json.dump(m,open("../data/erp/ft/text_locate_all.json","w"))
PY
python3 build_meter_shards.py ../data/erp/ft/text_locate_all.json ../data/erp/ft/m4 --audit 40   # يستبعد الاختبار آلياً؛ افحص لوحة data/review/meter_shards_m4.jpg بعينك
```

## 6) الاتصال بـ Contabo وبالموقع
- `~/.ssh/config`: `Host basira / HostName 80.241.221.190 / User root / IdentityFile ~/.ssh/basira_vps`. **المفتاح الخاص لا يُحفظ في git** — المالك يحتفظ به (أُرسل له في البرومت النهائي)؛ أو يولّد مفتاحاً جديداً ويضيفه إلى `/root/.ssh/authorized_keys` على الخادم.
- النشر: `MODELS="new=data/models_<tag> prev=data/models_m1loc_ft6m1 shipped=data/models_repro" bash lab/webdemo/deploy_contabo.sh` ثم `curl https://basirapp.site/meter/health`.
- Caddy في docker: `/opt/basira/Caddyfile` (`lab/webdemo/caddy_snippet.txt`).
- OpenAI proxy للاستشارات: `~/.genspark_llm.yaml` (مُعطى من المنصة؛ `lab/consult.py`).

## 7) المعايير غير القابلة للتفاوض
الـ49 وtestset_human **للتقييم فقط**؛ لا صور عملاء في العام؛ لا AGPL؛ الجزء الصحيح فقط؛ أرقام حرفية بلا تقريب؛ توثيق بعد كل خطوة؛ commit+push بعد كل تغيير؛ Python/Kotlin متطابقان (أي تغيير في `assemble.py` يُعكس في `ReadingAssembler.kt` مع اختبار تكافؤ 49/49 قبل الشحن).
