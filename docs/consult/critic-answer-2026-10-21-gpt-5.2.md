# gpt-5.2 — 2026-10-21 06:56 UTC (44s)

## 1) “Type-conditional K (integer length)” is **not safe** by itself

It can produce **confident, wrong** integers in exactly your setting (few labels, unknown types, partial crops, glare), because **K is a latent global variable that is often underdetermined from the pixels** and highly sensitive to upstream mistakes.

Concrete high-risk cases:

- **Type misclassification → systematic wrong K.**  
  Example: a 3‑phase HPL/CHINT (often 5–6+1 decimal) mis-typed as TOMAS (6+2). If your parser “takes first K digits”, you will confidently drop/keep the wrong suffix. With your imbalance (MT10=6), the type classifier will be overconfident on majority types.

- **CRYSTAL 2 vs 3 vs 4 integer digits with no leading zeros.**  
  Readings like `98.12`, `355.96`, `1247.03` share the *same* local digit appearance; without a visible dot, a global K head will learn dataset priors (“most are 3 digits”) and be confidently wrong on tail cases (2-digit or 4-digit). This is classic “shortcut learning” under weak cues.

- **Partial crop / occlusion of right side (kWh text or last digit).**  
  If the crop cuts off the rightmost region, the digit detector may return 2–3 digits; a K head trained on full crops can still output K=4 confidently (or vice versa). You get plausible integers that are wrong with no internal contradiction.

- **Unknown types / firmware variants.**  
  “Unknown” is not a type; it’s a catch-all. If your logic falls back to “most common decimals = 2” you will confidently mis-handle a variant with 1 decimal (HPL-like) or 0 decimals.

- **Upstream windowing errors.**  
  If localization lands on the serial/barcode label, a type classifier can still output a confident “type” (it will latch onto background color/PCB texture), then K becomes confidently wrong.

**Decision:** A **per-image “last integer digit” boundary signal is more robust than type-conditional K**, but **only if it is conditioned on the observed digit row**, not just global features. I would prefer:

- Predict a **1D boundary position** along the x-axis on the digit row (a “boundary heatline”), i.e., “cut here”. This is closer to your option (a) but *easier than a point keypoint* and less fragile than global K. It degrades gracefully under missing digits: you can still cut based on boundary position even if one digit is missed.
- Use type priors only as a **soft prior / rejection heuristic**, not a hard rule.

A per-digit `is_decimal` attribute is **usually worse here**: it presumes stable per-digit instances and ordering; with detector misses/merges under glare and tilt, it becomes arbitrarily wrong (and confidently so). CTC (Graves 2006; Shi et al. 2016) doesn’t solve an invisible dot either.

## 2) Full LCD-quad + rectification at 213k params: **not clearly justified yet**

Rectification (STN: Jaderberg et al. 2015; ASTER: Shi et al. 2018) helps when recognition is the bottleneck. Your bottleneck is **wrong localization + decimal boundary**, and you have **tiny data** and **CPU-only**.

Risks with the proposed quad stage now:

- **Corner labeling noise dominates** with 400–1000 images. Corner regression is annotation-sensitive; 5 s/photo is optimistic for consistent quads under glare/occlusion.
- **Quad model failure becomes a new hard gate.** If quad fails, everything fails; whereas augmentation+top‑K keeps multiple hypotheses alive.
- **You can get ±25° without rectification** by training for it and using top‑K re-read:
  - Add **rotation/perspective augmentation** (±30° in-plane, mild projective warp) and **photometric glare**. (See Shorten & Khoshgoftaar 2019 for augmentation effects broadly; in detectors, rotation aug commonly yields large robustness gains when baseline is brittle.)
  - At inference, take **top‑K locator boxes (K=3)** and run the reader on each; accept only if **two agree exactly** (a cheap consistency check). This directly targets your “wrong thing” failure mode.

Given your 0.5 s budget, 3 reads may be acceptable on CPU if the reader is tiny; a full quad+warp is not “free” either (bilinear sampling over a big crop + extra net).

**My take:** Don’t build quad rectification in the next iteration. First prove that aug + top‑K + rejection gets you to ±25° on a dev set. Only add quads if you can’t hit coverage/precision.

## 3) Text-supervised localization collisions: a concrete acceptance test

You need an explicit *anti-poisoning* filter. Use all of these simultaneously:

**Window search** produces candidates with a score \(S\) = sum log-probs of matched digits (or negative edit distance proxy). Accept a pseudo-box only if:

1) **Margin:** \(S_1 - S_2 \ge 6.0\) (≈ e^6 = 403× likelihood ratio).  
2) **Jitter consistency:** apply 8 jitters (±6% shift, ±6% scale, ±10° rot). Re-run search; require:
   - same best window in ≥6/8 runs, and
   - median IoU(best, original) ≥ **0.75**.
3) **Minimum evidence:** predicted digit count ≥ **5** for pseudo-labeling.  
   For CRYSTAL (2–4 digits), require an additional cue: presence of “kWh” token area OR a trained “LCDness” score ≥0.9. Otherwise do **not** pseudo-label (too collision-prone).
4) **Top‑K read agreement:** run reader on top‑3 windows; require at least **2/3 exact match** to target text.

Anything failing → discard (no pseudo-label). This is cheaper than cleaning poisoned training.

## 4) Next 72 hours (1 engineer, 2 CPU boxes): ruthless order + gates

**Do NOT do in 72h:** quad corners, type classifier, CTC/CRNN rewrite, SAM/VLM pipelines.

### Hour 0–8: Build a real dev loop + instrumentation (must-have)
- Create a **non-frozen dev set** from owner data: 120 images stratified by type + tilt + glare.
- Add logging: top‑K locator boxes, reader outputs, confidence, runtime.

**Gate:** reproducible metrics + per-failure breakdown (no model changes yet).

### Hour 8–24: Fix pseudo-label poisoning (acceptance test above)
- Implement the margin+jitter+agreement filter.
- Generate pseudo-boxes for as many owner-labeled images as possible.

**Gate:** manually audit 100 accepted pseudo-boxes: **≥98 correct** (2 max wrong). If worse, tighten thresholds.

### Hour 24–48: Train locator for robustness + hard negatives
- Train locator with strong rot/perspective/glare aug.
- Mine hard negatives: barcode/serial/stickers from false positives; add explicit “non-LCD text block” negative crops for a **second-stage LCDness classifier** (tiny CNN).

**Gate:** on dev set, “no-line or wrong-thing” failures reduced by **≥50%** at same rejection policy.

### Hour 48–72: Add top‑K re-read + conservative acceptance
- Inference: take top‑3 locator boxes → read each → accept only if:
  - two readings match exactly, and
  - digit count sanity (e.g., 2–8), and
  - reader mean per-digit margin ≥ threshold.
- Add optional boundary baseline: **reject CRYSTAL-like cases unless boundary confidence is high** (don’t force K yet).

**Gate:** On dev set, achieve **0 wrong accepted** (even if coverage is low). Then iterate to recover coverage, not before.
