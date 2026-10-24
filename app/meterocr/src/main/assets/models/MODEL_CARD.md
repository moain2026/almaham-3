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

---
## Addendum 2026-10-24 (agent S) — current reference pair and what the numbers do and do not prove
**Reference pair since 2026-10-21:** `lab/weights/locator_m1_augv2.pt` + `lab/weights/reader_ft6m2_s1.pt` (results `benchmark/results/engines/digitnet_check_{A,B}.json`, `testset_human_check.json`, risk–coverage in `lab/logs/eval_check.log`). Python↔Kotlin parity 49/49 (A and B) with optical2's `PixelResampler.kt` (not yet merged into this app; see `docs/handoff/review-of-optical2-r3-2026-10-24.md`).

### Per meter type on the 49 (mode A, 39 readable) — Clopper–Pearson 95%
| type | readable | exact | 95% CI |
|---|---:|---:|---|
| TOMAS_SMART | 13 | 11 | [55%, 98%] |
| TOMAS_STATIC | 4 | 3 | [19%, 99%] |
| TAGADOD | 2 | 2 | [16%, 100%] |
| CRYSTAL | 5 | 3 | [15%, 95%] |
| EMETER_GREEN | 6 | 1 | [0%, 64%] |
| **SMART_MT10** (0 training examples anywhere) | 9 | 2 | [3%, 60%] |
| all | 39 | 22 | [40%, 72%] |
| trained types only | 30 | 20 | [47%, 83%] |

testset_human (34, by type): 21/34. Mode B (shipped pipeline, meter rectangle from the owner): 19/39.

### Selective prediction — read this before claiming "0.0 error"
Strict gate (`status OK & min_conf ≥ 0.55 & alt < 0.5·best`) on the 73 photos (49+34 readable, minus unreadable): **17 accepted, 0 wrong**. With 0 wrong out of n = 17 the one-sided 95% upper bound on the error rate is ≈ 3/n = **18%** (rule of three; exact CP 19.5%). "0 observed wrong" is therefore **not** evidence of ≤1% risk; demonstrating ≤1% at 95% confidence requires ≈300 accepted readings with 0 wrong. Coverage is 23%.

### Known limits
- SMART_MT10 is absent from the labelled pool (10,155 type labels): the model has never seen it. Product rule until data exists: abstain / manual entry.
- Dark low-contrast LCDs (EMETER_GREEN, MT10) carry 11 of the 17 errors; the locator is on the correct line in 34/38 photos, the reader is the failing stage in 16/17 (`docs/research/training-audit-2026-10-24.md`).
- Test-set look log: the 49 have been consulted after every autotrain cycle (≥60 looks) and the 34 after every candidate since 2026-10-21; treat both as dev-tests, not clean holdouts. New promotion rule: decide on val-m4 (pHash-cluster split, 177) with paired McNemar; report 49/34 once per milestone.
