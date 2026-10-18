# GenCode-APK — كل الهاشات والبصمات (وكيل B)

كيف تتحقق من ملف نزّلته: `sha256sum almaham-meter-0.2.1-arm64.apk` ← يجب أن يطابق الجدول.
وبصمة التوقيع: `apksigner verify --print-certs <apk>` ← `Signer #1 certificate SHA-256 digest`.

## 1. ملفات APK المنشورة (GitHub Releases، pre-release)
| الإصدار | الملف | بايت | sha256 | sha1 | md5 |
|---|---|---|---|---|---|
| **v0.2.1** (الحالي) | almaham-meter-0.2.1-arm64.apk | 7,682,409 | `8940f7372997f39dcaab120ec84c2afa2ec4865b277ad63a12bacb9cb2be3b3f` | `d9630822685452c7c890bf01a6dd439ebc403489` | `b43e999791eba4d66bb25038ee1d7135` |
| v0.2.0 | almaham-meter-0.2.0-arm64.apk | 7,682,029 | `c65869162744373c96d29cb9bcfdaa621b3623d062429d4c54b66e1b1c906e7d` | `eba2e07bf85e6981ebe3479848eb1d9002339efc` | `5cd645ba4b06bebc9a209d01d883e046` |
| v0.1.1 | almaham-meter-0.1.1-arm64.apk | 37,849,126 | `9eaf497eaa1d48bbf83f9ab2a1684f945ff6f8756042844dfc4bd12b27145e5c` | — | — |
| v0.1.0 (وكيل A) | almaham3-meterocr-0.1.0-release.apk | 89 MB | `1948ce46c43f3d783d0abba2b4f868ba6207edd5b834a3b700a0532bdeb6c11b` | — | — |

روابط:
- https://github.com/moain2026/almaham-3/releases/download/v0.2.1/almaham-meter-0.2.1-arm64.apk
- https://github.com/moain2026/almaham-3/releases/download/v0.2.0/almaham-meter-0.2.0-arm64.apk
- https://github.com/moain2026/almaham-3/releases/download/v0.1.1/almaham-meter-0.1.1-arm64.apk

## 2. بصمة شهادة التوقيع (كل إصدارات B: نفس المفتاح)
`apksigner verify -v --print-certs` — APK Signature Scheme **v2** (v1/v3/v4: false):
| | |
|---|---|
| DN | `C=US, O=Android, CN=Android Debug` (**مفتاح debug — للتجربة فقط**) |
| certificate SHA-256 | `04f129a99c0a5b0c5bec5876ebbc308bd77e47466f9260d9e0f179ff61a374a3` |
| certificate SHA-1 | `5ef72c6d7ccff60481bd15f4716c66399a00274d` |
| certificate MD5 | `f953a4976088a81ebd063c2ca3f9edf3` |
| public key SHA-256 | `fa27021ae7b3cbece8276026212572f9988b89e44bb92f9df2ae09e1c0d3ae5f` |
| public key SHA-1 | `dc177091799a99f6efa71ab4fac80cd98c5ef7a0` |
| الخوارزمية | SHA256withRSA |
| صالح | من 2026-10-17 23:55:42 UTC حتى 2056-10-09 |
| مكانه | `~/.android/debug.keystore` في سندبوكس B (كلمة السر الافتراضية `android`، alias `androiddebugkey`). **ليس في git.** |

**تنبيه:** في بيئة جديدة يُنشأ debug.keystore جديد ⇒ بصمة مختلفة ⇒ الجوال يرفض التحديث فوق النسخة القديمة (احذفها أولاً). للحفاظ على البصمة: انسخ `~/.android/debug.keystore` بطريقة آمنة خارج git، أو انتقل لمفتاح إنتاجي.

## 3. داخل APK 0.2.1 (`unzip -p <apk> <file> | sha256sum`)
| sha256 | الملف |
|---|---|
| `70dc58f0d2a11315ae166e383f7705e1905dc60dfb166e54a68a22cb589fff76` | assets/models/digit_reader.ort (reader_ft4a) |
| `e2c2242a9513cd6e9d4abfaeb8c219c7d4ff47336a97dad7bc700a7f41f91743` | assets/models/line_locator.ort (locator_t14500) |
| `60ef479c19d7d95060cd7e29720e7beb96872ceabcbec391392059e1d1d6eb66` | assets/models/digit_reader.onnx (المصدر، غير مستعمل) |
| `23b45a7c0c8122d212e65bbcecbe1c6c9ea3b79cf317db0cb7b0988f2f5145d8` | assets/models/line_locator.onnx (المصدر، غير مستعمل) |
| `ef0d8a6d552281afb6af04bd8d18b4e014e3ff9ccfe5aafddfa6b403a44ef57e` | lib/arm64-v8a/libonnxruntime.so (بعد strip من Gradle) |
| `5c77031f6716bf3b30d33ff4e6f90036eb8d3015e9a7c889b01dfb5a9d26145f` | lib/arm64-v8a/libonnxruntime4j_jni.so |
| `8f95e8274aa22b40ed2b9039ccd737986333881213594627b88b7a680a2f5088` | classes.dex |

## 4. مدخلات البناء في المستودع
| sha256 | الملف |
|---|---|
| `877286fb0b55f19571c472b52ab1a81ded295ef36cffabc5e7af2429082299b6` | artifacts/ort-minimal/maven/.../onnxruntime-minimal-arm64-1.23.2.aar (1,252,102 B) |
| `271e46bd435c26aab1068035748135dd77111a1beb57a7f5b54c3b8a40878514` | libonnxruntime.so كما خرج من بناء ORT (2,455,568 B، قبل strip) |
| `a5f7ae863a67936f85df3ad9b712bc266c3029735ec082a4d994087f1cdfcf4b` | artifacts/ort-minimal/run_build.sh |
| `59fa16dd1fc64279868d4a45c8e923e69dde8a86b85eb9fafd7b3639e44b3e8a` | benchmark/results/size/ort_required_operators_and_types.config |

## 5. النماذج في 0.2.0 (قبل ft4a) — للأرشيف
digit_reader.onnx `90dd48bf2b5b5576430d257a9ac3dc455a9fb0a07a6050812e9412f6ca1ab2ad`، line_locator.onnx `23b45a7c…` (نفسه).
