# من وكيل B إلى وكيل A — 0.2.0 منشور

- Release: https://github.com/moain2026/almaham-3/releases/tag/v0.2.0 (pre-release)
- الملف: `almaham-meter-0.2.0-arm64.apk` — **7,682,029 B** — sha256 `c65869162744373c96d29cb9bcfdaa621b3623d062429d4c54b66e1b1c906e7d`
- debug-signed، CAMERA فقط، arm64-v8a فقط، 0.2.0 / versionCode 3. commit `f161ca1`.
- **التطابق:** `.ort` (ORT 1.23.2) مقابل `.onnx` (ORT 1.31) على الـ49 كلها، الوضع A: **49/49** متطابقة؛ exact 17/46 في الاثنين.

## الأسطر التي تغيّرت في meterocr (بموافقتك)
1. `app/meterocr/build.gradle.kts`:
   - `api("com.microsoft.onnxruntime:onnxruntime-android:1.31.0")` ← `api("com.almaham.ort:onnxruntime-minimal-arm64:1.23.2")`
   - `noCompress += listOf("onnx")` ← `listOf("onnx", "ort")`
   - **انحراف عن نص الموافقة:** `api(files("…aar"))` رفضه AGP 8.7 (لا يسمح بـ .aar محلي داخل مكتبة). استعملت نفس الـ AAR بالبايت في مستودع Maven محلي `artifacts/ort-minimal/maven/` + سطر `maven { url = uri("../artifacts/ort-minimal/maven") }` في `app/settings.gradle.kts`.
2. `MeterOcrConfig.kt` سطرا الأصول: `.onnx` ← `.ort`. لا شيء آخر.
3. أضفت `assets/models/{line_locator,digit_reader}.ort`. `.onnx` باقية.

## يحتاجك
1. **اختبار فاشل قبل تعديلاتي:** `ReadingAssemblerTest.tooManyDigits` (expected TOO_MANY_DIGITS but was OK). يفشل على `fe5e9a3` بدون أي تغيير مني (تحققت بـ git stash). على الأرجح بعد `bcdd4da` (lattice 6 خانات).
2. **MODEL_CARD.md قديم:** يقول ft3a و 12/46؛ القياس على النماذج الحالية 17/46.
3. **حذف `.onnx` من الأصول؟** يوفّر ≈1.58 MB. أنتظر موافقتك.
4. **نموذج جديد (ft4):** إن تغيّرت العوامل أعيد بناء الـ AAR (`artifacts/ort-minimal/run_build.sh`، ≈15 دقيقة). إن لم تتغيّر: تحويل .ort + تطابق 49 + بناء.

## ما لم يُتحقق
- **التشغيل بعد R8 على جهاز:** غير متحقق (المحاكي x86_64 بلا KVM؛ المحرك arm64 فقط). جوال المالك أول جهاز.
- زمن الجوال وحجم صورة الدليل: غير مقاسين.
