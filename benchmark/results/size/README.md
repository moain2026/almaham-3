# APK size work (agent B, release 0.1.1) — see docs/apk-size-report.md
- `ort_required_operators_and_types.config`: operator+type list of our two models (ORT 1.23.2 `convert_onnx_models_to_ort --enable_type_reduction`), input to the minimal ORT build.
- `parity_litert_fp32.json`: onnx2tf float32 .tflite vs ORT 1.31 .onnx, 10 photos (mode A), `lab/litert_parity.py`.
- `parity_ort_format.json`: .ort (converted by ORT 1.31) vs .onnx, same 10 photos.
- `parity_ort1232_format.json`: .ort converted+run by ORT 1.23.2 (the minimal-build version) vs ORT 1.31 .onnx.
