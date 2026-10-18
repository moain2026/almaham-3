# AGENTS.md — almaham-3 (قراءة العداد)

## ابدأ هنا (بالترتيب، قبل أي أمر)
1. `STATUS.md` — وين وصلنا، وإيش التالي.
2. `LESSONS.md` — أخطاء سابقة لا تكررها.
3. `docs/brief/02_البرومت.txt` — المتطلبات الأصلية (المرجع النهائي عند أي تعارض).
4. `docs/history/` — آخر ملف جلسة.

## تجهيز البيئة
`docs/runbooks/setup-environment.md`. باختصار:
`pip install -r requirements-lab.txt && bash scripts/download_models.sh` ثم ضع الصور الـ49 في `data/photos/`
وشغّل `bash scripts/verify_photos.sh` (لازم 49/49).

## الأوامر
| الغرض | الأمر (من جذر المستودع) | المتوقع الآن |
|---|---|---|
| فحص كامل | `bash scripts/check.sh` | lint OK + `"exact": 15` |
| تقييم SegReader | `cd lab && python3 eval_rec.py weights/rec_w075.pt` | 15/46 |
| ERP baseline | `cd lab && python3 baseline2.py` | A 17/46, B 12/46 |
| PP-OCR (إعادة تقييم من المخرجات الخام) | `cd lab && python3 score.py ppocrv5_mobile ppocrv6_tiny ppocrv6_small` | 4/6/10 من 46 (A) |
| PP-OCR تشغيل كامل | `cd lab && python3 run_raw.py ppocrv6_tiny` | دقائق، CPU ثقيل |
| توليد بيانات اصطناعية | `cd lab && python3 gen_data.py 96000 ../data/synth/syn_a.npz 1000` | ~25 دقيقة، 888MB |
| تدريب | `docs/runbooks/train-segreader.md` | |

## القواعد (إلزامية)
- **الصور الـ49 للاختبار فقط.** ممنوع تدخل التدريب أو اختيار المعاملات بشكل يتسرّب منه الجواب. (REQ-001.12)
- **ممنوع رفع:** صور العملاء، `data/`، `*.npz`، نماذج ONNX لأطراف ثالثة، نماذج الـ ERP (AGPL)، أي سر. (ADR-0004)
- **الحقيقة الوحيدة:** `benchmark/data/ground_truth.csv` (v2). النسخة v1 في `archive/` فيها 3 قراءات غلط — لا تستخدمها.
- **أي رقم يُعلن** لازم: الأمر الذي أنتجه + ملف المخرجات في `benchmark/results/` + العتاد (سندبوكس أو جوال، أي جوال).
  أرقام السندبوكس للمقارنة النسبية فقط؛ معايير الزمن تُقاس على جوال.
- **لا تعليق للسندبوكس:** التدريب والعمليات الثقيلة في الخلفية بـ `nohup … &` و `TORCH_THREADS=2` (اترك نواتين)،
  ولا أمر ينتظر أكثر من دقيقتين. لا تحمّل ملفات npz كاملة كـ float32. (postmortem 2026-10-18)
- **وثّق وارفع بعد كل خطوة:** حدّث `STATUS.md` + ملف الجلسة في `docs/history/` + `CHANGELOG.md`، ثم commit و push.
- قرار ← `docs/adr/` · مشكلة أخذت > 30 دقيقة ← `LESSONS.md` · حادثة ← `docs/postmortems/`.
- Commits بصيغة Conventional Commits (`feat:` `fix:` `docs:` `chore:` `exp:` للتجارب).

## حدود البيئة (السندبوكس الحالي)
4 أنوية x86، 8GB RAM، 37GB قرص، بدون GPU، بدون جوال. Flutter 3.35.4 / Dart 3.9.2 / Android SDK 35 / JDK 17.
