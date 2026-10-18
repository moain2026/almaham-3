---
status: accepted
date: 2026-10-18
---
# 0003 — لا نماذج AGPL (Ultralytics YOLO) في المنتج
## السياق والمشكلة
نماذج الـ ERP الحالية `lcd-detector-v1.onnx` و `digit-reader-v3.onnx` مدرّبة بـ Ultralytics YOLO11 (AGPL-3.0).
شحنها في تطبيق مغلق خطر قانوني. البرومت اقترح YOLO11n كخيار ج.
## الخيارات
1. استخدامها كما هي · 2. رخصة Ultralytics تجارية · 3. معماريات متساهلة (CNN خاص، PicoDet/RT-DETR Apache-2.0، SSD-MobileNet).
## القرار
3. نماذج الـ ERP تُستخدم في المعمل كـ baseline للقياس فقط (`lab/baseline2.py`)، ولا تُرفع لهذا المستودع ولا تُشحن.
## العواقب
✔ لا خطر رخصة. ✘ لازم ندرّب كاشف/محدّد خاص.
