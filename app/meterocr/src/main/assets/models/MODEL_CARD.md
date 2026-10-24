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

---
## Release candidate 2026-10-24 (agent S) — `locator_m4_s0.pt` + `reader_m4_s0.pt` (NOT yet in this APK)
Lineage: both fine-tuned from the reference pair's parents (`locator_m1_augv2`, `reader_ft6m1_augv2`) on **m4** = 903 ERP photos (m3 + 381 line boxes verified by agent R; 9 poisoned labels excluded; pHash-cluster split 726 train / 177 val), synthetic `scene_s1` / `line_s1`, 3000 steps AdamW 2e-4 cosine, AUG v2, no EMA, seed 0 (locator checkpoint at step 2500 — run cut by sandbox cleanup; a full 3000-step rerun is in progress). Shards archived privately (`almaham-3-private-data/training_shards/2026-10-24_m4`). None of the 49/34 photos is in m4 (hash + filename exclusion, re-checked).

### Numbers (all backed by `benchmark/results/engines/*loc_m4_s0_rd_m4_s0*`)
| metric | reference pair | **candidate** |
|---|---|---|
| 49 mode A (39 readable) | 22 | **23** |
| 49 mode B (shipped path) | 19 | **22** |
| testset_human 34 | 21 | **23** |
| strict gate on 73 (accepted / wrong) | 17 / 0 | **20 / 0** |
| `OK & min_conf≥0.55` on 73 | 18 / 2 | **22 / 0** |
| **val-m4 end-to-end, clean65** (never in any training) | 47/65 | **49/65** |
| val-m4 e2e, all 177 | 140 | **145** |
| val-m4 e2e strict gate 177 (accepted / wrong) | 72 / 4 | 75 / 4 |

Honest reading: every axis moves the same way, but no single difference is statistically significant (McNemar clean65 p=0.63, 177 p=0.33; the 49/34 differences are within seed spread ±2). Claim: **no regression, consistent small gain** — nothing more.

### Per meter type on the 49 (mode A) — Clopper–Pearson 95%
| type | readable | exact | 95% CI |
|---|---:|---:|---|
| TOMAS_SMART | 13 | 9 | [39%, 91%] |
| TOMAS_STATIC | 4 | 4 | [40%, 100%] |
| TAGADOD | 2 | 2 | [16%, 100%] |
| CRYSTAL | 5 | 4 | [28%, 99%] |
| EMETER_GREEN | 6 | 1 | [0%, 64%] |
| **SMART_MT10** (still 0 training examples) | 9 | 3 | [7%, 70%] |
| all | 39 | 23 | [42%, 74%] |
| trained types only | 30 | 20 | [47%, 83%] |

### Selective prediction — the gate that will ship with this pair
- Today's `confident` flag is **vacuous**: `SegmentVerifier` rejects 83–86% of the digits of fully *correct* readings, so `confident_total = 0` on all 177 val photos for both pairs. It must be removed from `uncertain` in Kotlin (kept as diagnostics only) before any "confident" number is quoted.
- Gate v2 measured end-to-end on val-m4 (`docs/research/gate-v2-2026-10-24.md`): `OK & every digit score≥0.45 & alt<0.5·score` → 130 accepted / 11 wrong; **+ TTA agreement** (gamma 0.7/1.4, scale 0.92/1.08, identical string) → 106 / 2; **+ previous-reading window** (`prev ≤ v ≤ prev + 2×500`, previous reading simulated) → 104 / 0 (clean65 34 / 0). Rule-of-three upper bound on the accepted-error rate ≈ 3/104 ≈ 2.9% — far from the ~300 accepted-without-error needed to claim ≤1%.
- Previous-reading window figures use a *simulated* previous reading; they must be re-measured on real (photo, previous, truth) triples from the owner's system before being quoted as product numbers.

### Ship conditions (status)
1. clean65 e2e ≥ reference — **met** (49 ≥ 47).
2. Python↔Kotlin parity 49/49 on this pair — pending (Astra r4 permanent test).
3. This card updated — done (this section).
4. Owner phone run — pending.
Not published to the web demo until 2 and 4 are done.

### Update 2026-10-24 21:00 — candidate reader replaced: `reader_m4_dr1_s0.pt` (locator unchanged: `locator_m4_s0.pt`)
Recipe = m4 reader recipe + 4000 synthetic lines from `synth2.py SYNTH_DR=1 SYNTH_LINE=int` (dark / low-contrast panels, faint or absent dot, integer-only LINE box). Trained on Contabo, seed 0; seeds 1 and 2 reproduce the gain.
| metric | reference | m4_s0 (previous candidate) | **dr1_s0** | dr1_s1 | dr1_s2 |
|---|---|---|---|---|---|
| val-m4 e2e clean65 (never trained on) | 47/65 | 49/65 | **53/65** | 52 | 52 |
| val-m4 e2e all 177 | 140 | 145 | **146** | 145 | 145 |
| strict gate on 177 (accepted / wrong) | 72/4 | 79/5 | 73/4 | 65/3 | 67/3 |
| 49 A / B / testset_human 34 | 22/19/21 | 23/22/23 | 23/22/22 | — | — |
| strict gate on 73 | 17/0 | 20/0 | **21/0** | — | — |
| gate v2 (G0+TTA) on 177 | — | 106/2 | **110/2** | — | — |
Honest reading: +4 clean65 photos fixed, 0 broken vs the previous candidate (McNemar p=0.125, n too small for significance), consistent across three seeds; 49/34 within seed spread. What it fixed: TAGADOD ×2, SMART_YELLOW ×2 (dark/low-contrast panels — exactly the hypothesis). What did not help (measured): +172 pseudo-labels, +349 label-verified photos, ×2 width, longer training, 3-seed ensembles.
Live on the web demo as engine `dr1` (default). APK ships only after Kotlin parity 49/49 on this pair.
