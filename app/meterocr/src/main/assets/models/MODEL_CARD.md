# Models in this APK — ft3a (2026-10-18)
- `line_locator.onnx` ← `lab/weights/locator_ft3a.pt` (locator_t@8000 synthetic → ERP fine-tune ft2 → ft3 step 500)
- `digit_reader.onnx` ← `lab/weights/reader_ft3a.pt` (reader_v1_s2000 synthetic → ERP fine-tune ft2 → ft3 step 750)
- Training data: synthetic (lab/synth2.py) + 923 ERP photos with vision-model labels (weak boxes, lab/erp_finetune.py). **None of the 49 test photos.**
- Measured on the 49 test photos (46 readable), sandbox CPU: exact A **12/46**, B 12/46, wrong-confident **0**, reader on ideal crop 18/46, locator tight IoU>0.5 30/46. Details: docs/benchmark_report.md §8.
- Export: `lab/export_onnx.py` (NHWC 0–255 input, normalisation + 3x3 max-pool NMS inside the graph). max|torch−ort| < 5e-4.
- Licence: own weights (owner). No AGPL/GPL components.
