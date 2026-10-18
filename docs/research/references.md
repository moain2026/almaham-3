# المراجع
المصدر الأساسي: `docs/brief/03_البحوثات.txt` (جمعه المالك، 2026-10-18). أدناه ما اعتمدنا عليه فعلاً وماذا أخذنا منه.

## الكاميرا (Android)
| المرجع | ماذا نأخذ |
|---|---|
| https://developer.android.com/media/camera/camerax/take-photo/zsl | `CAPTURE_MODE_ZERO_SHUTTER_LAG`، CameraX ≥ 1.2، `isZslSupported`، لا يعمل مع الفلاش ON/AUTO |
| https://developer.android.com/media/camera/camerax/take-photo/options | `MINIMIZE_LATENCY` كبديل |
| https://developer.android.com/media/camera/camerax/mlkitanalyzer | ربط ML Kit مع ImageAnalysis — نقيس ولا نفترض |
| https://stackoverflow.com/questions/74109891 | MlKitAnalyzer أبطأ من Analyzer يدوي |
| https://medium.com/kbtg-life/real-time-machine-learning-with-flutter-camera-bbcf1b5c3193 | بث الإطارات لـ Dart ثقيل ⇒ native Kotlin |

## محركات القراءة
| المرجع | ماذا نأخذ | الرخصة |
|---|---|---|
| https://developers.google.com/ml-kit/vision/text-recognition/v2/android | baseline على الجوال؛ bundled ≈ +4MB؛ حرف ≥ 16×16px | مجاني (شروط Google) |
| https://github.com/PaddlePaddle/PaddleOCR · https://arxiv.org/html/2507.05595v1 | PP-OCRv5 mobile | Apache-2.0 |
| https://github.com/RapidAI/RapidOCR (rapidocr==3.10.0) | تشغيل PP-OCR ONNX في المعمل؛ مصدر ملفات النماذج (`scripts/download_models.sh`) | Apache-2.0 |
| https://docs.ultralytics.com/integrations/litert | YOLO11 → LiteRT INT8 | **AGPL-3.0** ⇒ مرفوض للمنتج (ADR-0003) |
| https://github.com/baudm/parseq | PARSeq-tiny بديل للقارئ (أثقل) | Apache-2.0 |
| https://github.com/jomjol/AI-on-the-edge-device | مصنف لكل خانة على ESP32 | MIT |
| https://github.com/renjithsasidharan/seven-segment-ocr | seven-segment بـ TFLite | — |
| https://github.com/Shreeshrii/tessdata_ssd | Tesseract seven-segment (موجود في الـ ERP كـ fallback) | Apache-2.0 |
| https://onnxruntime.ai (ORT 1.31) | تشغيل SegReader على أندرويد | MIT |
| https://developers.google.com/edge/litert/android/gpu | LiteRT GPU delegate — بديل أصغر لـ ORT | Apache-2.0 |

## أبحاث قراءة العدادات
| المرجع | ماذا نأخذ |
|---|---|
| Laroca 2019 https://raysonlaroca.github.io/papers/laroca2019convolutional.pdf | خط من مرحلتين (كشف ثم تعرّف) |
| Laroca 2021 https://arxiv.org/html/2009.10181v5 | Fast-OCR، تصحيح الميل بالزوايا الأربع |
| Copel-AMR https://github.com/raysonlaroca/copel-amr-dataset · UFPR-AMR https://github.com/raysonlaroca/ufpr-amr-dataset | **أكاديمي فقط — لا تدريب للمنتج** |
| https://www.sciencedirect.com/org/science/article/pii/S1546221822002594 | YOLOv3، 10k صورة، 5 أنواع |
| https://ieeexplore.ieee.org/iel8/6287639/10820123/10908809.pdf | YOLOv8 + 6 طرق قراءة |
| https://github.com/ZZZHANG-jx/Awesome-Image-based-Meter-Recognition-Reading | قائمة شاملة |

## جودة الصورة
| https://pyimagesearch.com/2015/09/07/blur-detection-with-opencv/ | Laplacian variance بعد الالتقاط (تنبيه فقط) |
|---|---|
