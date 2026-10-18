# Models in this APK — locator_t14500 (agent T) + reader_ft4a (agent A) — 2026-10-18

| file | source weights | lineage |
|---|---|---|
| `line_locator.onnx` | `lab/weights/locator_t14500.pt` | synthetic scenes t1..t3 (36k), 14,500 steps, early-stopped (agent T, `docs/training-log-agentT.md`) |
| `digit_reader.onnx` | `lab/weights/reader_ft4a.pt` | reader_v1_s2000 (synthetic) → ERP fine-tune ft2 (361) → ft3 (923) → ft4 step 1000 (1,703 real samples, 50/50 real/synthetic, lr 2e-4) |

- Real training data: ERP photos with vision-model consensus labels (labelling agents) + weak digit boxes (`lab/erp_finetune.py`). **None of the 49 test photos** (SHA256 check).
- **Measured on the 49 test photos (46 readable), sandbox x86 CPU, `lab/eval_ckpt.sh weights/locator_t14500.pt weights/reader_ft4a.pt t14500_ft4`:**
  exact A **19/46 (41.3%)**, wrong-confident **0**, empty 2, reader on ideal line crop 18/46, locator tight IoU>0.5 26/46, p50 36 ms / p95 70 ms (sandbox, not a phone).
- History on the same 46: v1 0 → ft2 6 → +assembly fix 9 → ft3a 12 → ft3 14 → T14500+ft3a 17 → **T14500+ft4a 19**.
- Export: `lab/export_onnx.py` (NHWC 0–255 input; normalisation + 3x3 max-pool NMS inside the graph); max|torch−ort| < 5e-4. ~850 KB each.
- Licence: own weights (owner). No AGPL/GPL components anywhere in the pipeline.
