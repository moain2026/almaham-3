# عقد التكامل بين الوكيلين (2026-10-18)

وكيلان يعملان بالتوازي على نفس المستودع. هذا الملف هو المرجع الوحيد لتقسيم الملكية وصيغ التبادل. أي تغيير فيه يكون بـ PR.

## 1. ملكية الملفات (من يكتب أين)
| المسار | المالك | الآخر |
|---|---|---|
| `app/meterocr/**` (المحرك: config, geometry, assembler, verifier, MeterReader, ONNX) | وكيل A (الشبكة) | يقرأ فقط؛ يفتح issue/PR للتعديل |
| `app/demo/**` (الواجهة، الكاميرا، الاختبار الجماعي) | **وكيل B** (بيئته مهيّأة للتطبيقات) ابتداءً من الآن | A يراجع |
| `lab/synth2.py`, `lab/det_model.py`, `lab/train_det.py`, `lab/gen_det_data.py`, `lab/export_onnx.py`, `lab/eval_e2e.py` | A | — |
| `lab/assemble.py`, `lab/segverify.py` (المرجع Python للتجميع) | A | B يقترح تعديلات |
| `lab/sevenseg*.py`, `lab/forensic_*.py`, `lab/forensic_reader.py` | B | — |
| `benchmark/data/digit_boxes.json`, `benchmark/data/erp/**` | B | A يقرأ |
| `benchmark/results/**` | كلٌّ يكتب ملفاته بوسم المحرك (`digitnet_*`, `forensic_*`, `vote_*`, `phone_*`) | |
| `docs/**` | كلٌّ ملفاته؛ `STATUS.md`/`CHANGELOG.md` يُحدَّثان بسطر لكل خطوة بدون حذف سطور الآخر | |

الفروع: A على `genspark_ai_developer`، B على `main` (أو فرع من main). الدمج النهائي عبر PR #1 بعد مزامنة rebase.

## 2. صيغة القارئ الحتمي (يسلّمه B، يستهلكه A)
ملف `lab/forensic_reader.py`، بلا اعتماد على ملفات خارج `lab/`، دالة واحدة:
```python
def read_line(crop_bgr: np.ndarray) -> dict:
    """crop_bgr: قصّ سطر القراءة (أي حجم، BGR uint8، قد يحوي كسوراً وأسطراً ثانوية).
    returns {
      "text": "003155",                     # الجزء الصحيح فقط كما يُعرض (بالأصفار)؛ "" إذا لم يُقرأ
      "digits": [                           # خانة لكل رقم بالترتيب من اليسار
         {"cls": 0, "conf": 0.91, "box": [x1,y1,x2,y2], "segments": [1,1,1,1,1,1,0]}  # box بإحداثيات القصّ، segments a..g
      ],
      "status": "OK" | "EMPTY" | "MISSING_DIGIT" | "UNSURE",
      "ms": 12.3
    }"""
```
- `conf` في [0,1] ويجب أن تكون **أمينة**: على الـ46 صورة، الخانات ذات `conf ≥ 0.8` يجب أن تكون صحيحة ≥ 97%.
- يجب أن يعمل نفس الكود لاحقاً في Kotlin (B ينقله إلى `app/meterocr/ForensicReader.kt` بعد اتفاق على الواجهة؛ عمليات OpenCV تُستبدل بعمليات مصفوفات بسيطة — Otsu، مكوّنات متصلة، إسقاطات).

## 3. صيغة صناديق الأرقام المرجعية (B يكتبها، للتقييم فقط — لا تدريب)
`benchmark/data/digit_boxes.json`:
```json
{"_doc": "per-digit boxes of the INTEGER part, normalised to the upright full photo [x1,y1,x2,y2]; eval only",
 "23066.jpg": {"text": "006719", "boxes": [[0.31,0.29,0.36,0.41], ...]}}
```

## 4. صيغة صور النظام (المالك يرسلها، B يجهّزها)
`benchmark/data/erp/labels.csv`: `filename,reading,meter_type,source_date` — الصور نفسها خارج git (مجلد `data/erp/photos/`، نفس آلية الـ49).
B يضيف `benchmark/data/erp/line_boxes.json` و`digit_boxes.json` بنفس الصيغ أعلاه (نصف آلي: محدِّد A يقترح، B يصحّح).
التقسيم: **حسب رقم العداد** لا حسب الصورة (80% تدريب / 20% تحقق). الـ49 تبقى اختباراً نهائياً فقط.

## 5. التصويت (A ينفّذه في `lab/vote.py` ثم Kotlin)
لكل خانة: إذا اتفق DigitNet والقارئ الحتمي ⇒ ثقة مرتفعة. إذا اختلفا ⇒ الخانة «غير مؤكدة» (تتلوّن) ويُختار صاحب الثقة الأعلى فقط إذا تجاوز 0.8 وإلا تبقى فاضية. القياس: «غلط وواثق» قبل/بعد التصويت على الـ46.

## 6. قياس الجوال (B)
`adb push photos/ /sdcard/Android/data/com.almaham.meterdemo/files/photos` → وضع الاختبار الجماعي → رفع `bench_<device>.csv` + `bench_summary_<device>.json` إلى `benchmark/results/phone/` مع اسم الجهاز وإصدار أندرويد.


## §7 تعريف السطر (ADR-0005، 2026-10-18)
السطر = اتحاد صناديق الأرقام بلا هامش. مقياس M3 الرسمي = IoU>0.5 مع اتحاد `digit_boxes.json` (`recall_tight_iou50`). مقياس `line_boxes` ثانوي. وكيل T: اجعل الضيّق هو المقياس الأساسي في `eval_locator_real.py` واللوغ؛ لا تغيير في `synth2.py`.
