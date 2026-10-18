# lab/ — البحث والتدريب (Python)
كل المسارات من `paths.py`. شغّل السكربتات من داخل `lab/`. البيانات الخاصة في `../data/` (انظر runbooks).

| الملف | الدور |
|---|---|
| `paths.py` | كل المسارات + متغيرات البيئة |
| `gt.py` | تحميل الحقيقة v2 + قص المستطيل |
| **المحرك** | |
| `rec_model.py` | SegReader (CNN + CTC، 48×192، مفردات `0-9.`) + `greedy_decode` |
| `prep.py` | تجهيز القصّ للقارئ — **لازم يطابقه Kotlin حرفياً** |
| `synth.py` | مولّد أسطر seven-segment اصطناعية (شبح، كسور، أسطر ثانوية، وهج، ضبابية، منظور، JPEG) |
| `synth_scene.py` | مولّد مشاهد عداد كاملة لتدريب محدِّد السطر (لوحات، كتابة عربية، باركود) — لم يُدرَّب بعد |
| `gen_data.py` | توليد npz مسبقاً (`N out seed`) |
| `train_fast.py` | تدريب من npz (`steps width out npz[,npz] [resume]`) |
| `train_rec.py` | تدريب بتوليد مباشر (أبطأ) + `load_real`/`real_eval` |
| `eval_rec.py` | تقييم checkpoint على الـ46 (وضع L) ← `benchmark/results/engines/` |
| `locate.py` + `eval_locate.py` | محدّد سطر كلاسيكي (مرفوض: 17/46) |
| **المحركات الجاهزة** | |
| `engines.py`, `run_raw.py`, `score.py` | PP-OCR عبر RapidOCR: تشغيل خام ثم تقييم |
| `bench_rapid.py` | نسخة أقدم (تكتب `engines/rapid_*.json`) |
| `yolo_onnx.py`, `baseline2.py`, `bench_baseline.py` | نموذج الـ ERP (AGPL، معمل فقط) |
| `rec_only.py`, `rec_oracle.py` | سقف القارئ على قصّ الشاشة المرجعي |
| **أدوات مراجعة بصرية** (تكتب في `data/review/`) | `crop.py`, `cropabs.py`, `enh.py`, `enh2.py`, `multi.py`, `det_vis.py`, `det_enh.py`, `find_displays.py`, `make_display_boxes.py`, `make_line_boxes.py` |

`weights/`: `rec_w075_s1000.pt` (v1، 7/46)، `rec_w075.pt` (v2، 15/46). `logs/`: سجلات التدريب.
`assets/fonts/`: خطوط المولّد الاصطناعي (OFL / DejaVu).
