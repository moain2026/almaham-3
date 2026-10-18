# GenCode-APK — سجل وكيل B (2026-10-18)

| commit | ماذا |
|---|---|
| `9d9ecb8` | 0.1.1 خطوة 1: flavors field/bench (ML Kit في bench فقط عبر `MlKitBaseline`)، R8 + shrinkResources، ABI splits |
| `0ff0227` | أداة التطابق `lab/litert_parity.py` (LiteRT/.ort مقابل .onnx على 10 صور: 10/10)، config العوامل، splits arm64+v7a |
| `e659e43` | نشر v0.1.1: ملف واحد arm64، 37,849,126 B (طلب المالك) |
| `3991382` | `docs/apk-size-report.md` + handoff لوكيل A + AAR المحرك المصغّر (بُني في ≈15 دقيقة، `.so` 2,455,568 B) |
| `0d24f74` | `lab/multi_algo.py`: 792 فحصاً حتمياً + تصويت. قص السطر 20/46، مستطيل كامل 0/46. **غير مدمج** |
| `f161ca1` | `build(meterocr):` المحرك المصغّر (Maven محلي) + `.ort` + 0.2.0 arm64 فقط، 7,682,029 B، تطابق 49/49 |
| `5b8268d` | توثيق 0.2.0: `docs/release-0.2.0.md`، handoff، نتائج التطابق |
| `838c0ce` | 0.2.1: نموذج ft4a (`8347475`، وصل بعد بناء 0.2.0 بـ 5 ثوانٍ)، تطابق 49/49، exact 19/46، 7,682,409 B؛ مجلد GenCode-APK |

## النشر
- v0.1.1، v0.2.0، v0.2.1: كلها pre-release، موقّعة بمفتاح debug.
- النشر بـ GitHub REST API (لا يوجد `gh`).

## ما سلّمته لوكيل A
- `docs/handoff/agentB-to-agentA-apk-size-0.1.1.md`
- `docs/handoff/agentB-to-agentA-0.2.0.md`

مطالب مفتوحة:
1. اختبار `tooManyDigits` الفاشل.
2. حذف `.onnx` من الأصول (≈1.58 MB).
3. ~~MODEL_CARD قديم~~: حدّثه وكيل A في `8347475`.
| `11:36` | نقل تقرير وكيل A (`3beb26f`) إلى `AGENT-A-REPORT-2026-10-18.md` + تصحيح: الإصدار الصحيح v0.2.1 |
