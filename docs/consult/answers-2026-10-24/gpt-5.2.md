# gpt-5.2 — 2026-10-24 04:18 UTC (122s)

## 1) Selective prediction gate (abstain unless *very* sure)

**Recommendation (1 line):** Use a **two-stage gate**: (A) hard structural/consistency rules, then (B) a **calibrated “probability of correctness”** model (tiny logistic/isotonic) and set the final accept threshold by **inductive conformal / binomial bounds**; do **not** hand-tune thresholds on the 73-image frozen set.

**Justification:**  
- Your “0 wrong among accepted” requirement is a **selective classification** / **reject option** problem (Chow, 1970; Geifman & El-Yaniv, 2017). In practice, you need (i) *high-signal heuristics* that kill known failure modes (EXTRA_RIGHT, wrong line, missing-left), and (ii) a learned calibrator that combines weak signals (min digit score, margins, line score, regularity) into a single monotone “correctness” score.  
- Raw detector peak scores are rarely calibrated (Guo et al., 2017). A logistic regression (Platt scaling style) or isotonic regression on correctness is cheap, robust, and easy to audit.  
- With only ~73 frozen + 68 val + 97 field, you cannot “prove” 0.0% risk; you can only choose thresholds and report **Clopper–Pearson** bounds honestly.

**Concrete gate design (what to implement):**

### Stage A: hard “fail-fast” rules (deterministic)
Apply before any learned calibrator; if any triggers → **ABSTAIN**.
1. **Line plausibility (from locator):**
   - Require `locator_line_score ≥ 0.45` (start here; re-tune after calibration).  
   - Additionally: run locator on **2 TTAs** (±3° rotate or ±5% scale). Require IoU(best_box_tta0, best_box_tta1) ≥ **0.7** or center distance ≤ **0.05×width**. If unstable → abstain.  
2. **Lattice / pitch sanity (you already have):**
   - Keep your `MISSING_DIGIT if gap > 1.75×pitch`. Also add **pitch CV**: `std(pitch)/mean(pitch) ≤ 0.20`.  
3. **Digit count envelope (type-agnostic):**
   - Accept only if detected integer-length candidate is in **[4, 7]** (or whatever Yemen meters truly cover; if unknown, keep wide but exclude absurd counts like 1–2 or >8).  
4. **Anti-EXTRA_RIGHT rule (fraction leakage):**
   - If a dot is detected: require dot score ≥ **0.25** *and* dot x-position between two digit centers with neighbor gap within **[0.6, 1.6]×pitch**; otherwise treat dot as unreliable and abstain if any boundary ambiguity remains.  
   - If no reliable dot and any of these hold: last digit is significantly smaller (`h_last < 0.75×median_h`) **OR** last gap is large (`gap_last > 1.4×pitch`) → abstain (these are cheap “fraction-start” indicators).
5. **Ambiguity margin rule (per-digit):**
   - For each accepted digit: require `(score_best - score_alt) ≥ 0.20` **and** `(score_alt/score_best) ≤ 0.50`.  
   - This directly targets ONE_DIGIT_SWAP cases where the wrong class is close (your failure stats show these pass current gate).

### Stage B: learned correctness calibrator + conformalized threshold
Train a tiny model to predict **P(correct | features)** on a held-out calibration set (not on frozen test).

**Features (all scalar, cheap):**
- `min_score` (your min digit peak)
- `p05_score` (5th percentile digit score; often more stable than strict min)
- `min_margin = min(score_best - score_alt)`
- `min_ratio = min(score_alt/score_best)`
- `mean_score`, `std_score`
- `locator_line_score`
- `pitch_cv`
- `max_gap_over_pitch`
- `num_digits`
- `dot_score_max` and `dot_present` (binary)
- `tta_agreement` (0/1): run reader on 2 TTAs of the line crop (e.g., ±2 px shift, mild gamma). If strings disagree → 0.

**Model:** L2-regularized logistic regression (or isotonic if monotonicity is expected). This is standard post-hoc calibration tooling (Guo et al., 2017; Zadrozny & Elkan, 2002).

**How to set the accept threshold (honestly, with little data):**
- Split data into: **train-calibration** (to fit logistic) and **calibration** (to choose threshold), keep the **73 frozen** as final test only.  
- Choose the largest threshold τ such that **0 errors** among accepted on the calibration set.  
- Report uncertainty with **Clopper–Pearson** for the error rate among accepted:
  - If you accepted *n* examples with 0 observed errors, the 95% upper bound is  
    \[
    p_{err} \le 1 - 0.05^{1/n}
    \]
    Examples:  
    - n=17 (your current strict gate): upper bound ≈ **16.3%**  
    - n=50: upper bound ≈ **5.8%**  
    - n=100: upper bound ≈ **3.0%**
- Practically: to claim “near-zero”, you need **many more accepted calibration points** than you currently have.

**Conformal variant (optional, but principled):**
- Use **inductive conformal prediction** on the logistic model’s “nonconformity” score `s = 1 - P̂(correct)` (Vovk et al., 2005; Angelopoulos & Bates, 2021).  
- Pick significance α (e.g., 0.01 or 0.05). Conformal gives distribution-free coverage guarantees for the *set* prediction; for selective acceptance you’ll still end up with a threshold on `s`, but now tied to α on a calibration set.

---

## 2) Integer/fraction boundary for Crystal-like displays (dot invisible, same-height digits)

**Recommendation (1 line):** First try **(c) 2× resolution** + re-train with aggressive “tiny-dot preservation”; if dot is truly unobservable, the boundary is **information-theoretically ambiguous** and you must introduce a **prior** (meter-type / digit-count) or abstain.

**Justification:**  
Your own root-cause note says the dot becomes ≤1 px after downscale and scores 0.07–0.29. If the delimiter is not observable, *no model* can reliably separate integer/fraction from a single static crop without additional information (type prior, temporal sequence, user hint, etc.). Any method that “hallucinates” the boundary increases the risk of confident EXTRA_RIGHT errors.

**Ranked options (gain vs risk vs cost):**

### (c) Read at 2× resolution (128×896 input to reader)
- **Expected gain:** High for Crystal if the dot is physically present but lost to downscale; should directly reduce EXTRA_RIGHT.  
- **Risk of confident errors:** Low-to-medium; if dot still absent, model may still guess. Gate should require dot evidence; otherwise abstain.  
- **Data needed:** Moderate; you already have Crystal examples—need more *real* Crystal where dot exists at full-res. Synthetic must render subpixel dots + realistic resampling.  
- **CPU cost:** ~4× MACs in early layers (area doubles in each dimension). With 0.21M params it might still fit <100 ms, but measure; often it’s borderline on mid-tier phones.

**Concrete:** Train reader at 128×896, and enforce a gate: **accept only if dot_score ≥ 0.30 OR boundary confidence ≥ 0.9** (if you add a boundary head).

### (e) Meter-type classifier → digit-count prior (with uncertainty)
- **Expected gain:** Medium to high if type strongly determines decimal layout for Crystal-like devices.  
- **Risk:** **High** if type misclassified or if within-type layouts vary. This is exactly how you get confident systematic errors. Must be paired with abstention when type confidence is low.  
- **Data needed:** You already have type labels in m3; add more Crystal/SMART_YELLOW.  
- **CPU:** Low (tiny MobileNetV3-small head or even linear probe on shared backbone).

**Concrete:** Use type prior only when `P(type) ≥ 0.95`. Otherwise abstain or fall back to dot-based boundary only.

### (b) Per-line 1‑D boundary regressor head
- **Expected gain:** Medium if there is subtle visual cue besides dot (spacing, segment style).  
- **Risk:** Medium-to-high for Crystal where there may be *no cue*; regressor will learn dataset priors and can be confidently wrong OOD.  
- **Data needed:** Needs explicit boundary supervision. You currently do not have it unless you derive it from dot or from trusted meter-type rules.  
- **CPU:** Low (1D conv/MLP on pooled features).

**Concrete:** Output boundary x-coordinate + uncertainty (e.g., Laplace NLL). Gate: accept only if predicted boundary std ≤ **0.1×pitch**.

### (a) Add 12th heatmap class “last integer digit”
- **Expected gain:** Medium *only if* the model can learn a cue; otherwise it encodes priors.  
- **Risk:** Similar to (b); also label construction is tricky because you don’t have per-digit ground truth alignment from string labels alone.  
- **Data needed:** You’d need to match detected digits to the known label string during training (Hungarian + order constraints), and you still don’t know the boundary in Crystal without extra info.  
- **CPU:** Minimal.

**Concrete:** Only do this if you can generate reliable training targets (e.g., from visible dot subset) and then **do not apply** it when dot is not detectable—otherwise it’s just a learned prior.

### (d) Sequence model (CTC) with boundary token
- **Expected gain:** Low-to-medium for boundary specifically; CTC helps with detection-free reading but doesn’t magically create boundary evidence.  
- **Risk:** Medium; CTC models can be overconfident and harder to calibrate without careful uncertainty estimation.  
- **Data:** Needs more real sequence diversity.  
- **CPU:** Potentially higher (encoder + recurrent/transformer) unless extremely tiny.

**Bottom line:** If dot truly disappears, (c) is the only “physics-based” fix. Everything else is a prior → must be gated aggressively or abstain.

---

## 3) Using the 612 photos with known reading but unknown line box

**Recommendation (1 line):** Do **(iv) manual boxes for a targeted subset** (especially Crystal/SMART_YELLOW) + **(iii) strict self-training with verification**; avoid broad MIL over sliding windows unless you can constrain the proposal set tightly.

**Justification:**  
- Weakly-supervised localization with only string labels is prone to **confirmation bias**: the model learns to pick regions that make the reader output match the label even if they’re wrong for the right reasons (classic weakly-supervised detection failure mode; see Bilen & Vedaldi, 2016; Tang et al., 2017).  
- Your earlier weak-labeller failed; widening it indiscriminately tends to add **poisoned boxes** (wrong region that coincidentally matches a substring / spurious digits), which is catastrophic under “0 wrong” constraints.

**Concrete plan (reliable, low-poison):**

### Step 1: Minimal manual boxing (highest ROI)
- Manually box **~150–250** line regions from the 612, stratified:
  - Crystal + SMART_YELLOW + Mechanical first (these are underperforming / missing).
- This gives you a trustworthy calibration + training anchor.

### Step 2: Strict pseudo-labeling (iii) with hard verification + stability checks
For each unlabeled-line image:
1. Get **top-K locator proposals** (modify locator to output top-K peaks, K=5–10).
2. For each proposal, run reader and assembly; accept a proposal as pseudo-GT only if:
   - predicted integer string == human label **exactly**
   - passes Stage A structural checks (Q1)
   - **stable under 2 TTAs** of the line crop: same string both times
3. If multiple proposals satisfy, pick the one with highest `(locator_score × min_digit_score)`.

This is “self-training with verification”; it’s safer because the label check is exact.

### Step 3: Avoid full sliding-window widening (i) unless constrained
If you do (i), constrain heavily:
- Only evaluate windows centered near the locator peak ±10% height, ±10% width; multi-scale only {0.9, 1.0, 1.1}.  
- Otherwise compute blows up and false matches rise.

### Step 4: MIL / latent box (ii) only with tight proposals
If you try MIL, do it over the **top-K locator boxes**, not dense windows. This is closer to weakly-supervised detection (Bilen & Vedaldi, 2016), but your supervision is stronger (exact string match), which helps.

**Pitfalls to watch:**
- “Lucky match” on a wrong region (especially if label has repeated digits). Mitigate with TTA stability + lattice sanity + requiring all digits present (no missing-left).  
- Distribution shift: pseudo-labels concentrate on easy cases; keep manual labels for hard cases to avoid collapsing coverage.

---

## 4) Ghost-segment confusions (5↔6, 9↔0/8, 2↔3, 7↔1)

**Recommendation (1 line):** Add **real hard negatives** + synthesize **ghosting/off-segment artifacts** explicitly; optionally add an **auxiliary 7-seg attribute head** (multi-task) and tighten the abstention gate using **per-digit margin**.

**Justification:**  
These are classic “ambiguous evidence” errors: the image contains faint segments that make multiple digits plausible. The best fixes are (i) train on examples that contain these artifacts and (ii) force the model to represent segment-level evidence rather than only class identity. I do **not** know a widely-cited, definitive paper specifically quantifying ghost-segment augmentation gains for LCD meters; most published OCR work is on natural text, not seven-seg with ghosting (unknown).

**Concrete training/data changes:**
1. **Artifact-driven synthetic augmentation (high impact, cheap):**
   - When rendering digits, randomly turn on “off segments” at low intensity:
     - per segment probability 0.05–0.15
     - intensity 3–15% of on-segment brightness
     - add bloom/halo blur σ=0.3–1.0 px
   - Add LCD-specific effects: local contrast rolloff, pixel inversion, subpixel grid, mild motion blur.
   - This is domain randomization (Tobin et al., 2017) applied to seven-seg.
2. **Hard example mining from real data (high impact):**
   - Mine crops where the model predicts high confidence but wrong (your ONE_DIGIT_SWAP set). Oversample them ×5–×10 for reader training.
   - Keep a “confusion queue” per digit pair (5/6, 9/0/8, 2/3, 7/1) and ensure each batch contains some.
3. **Auxiliary head (moderate impact, low risk):**
   - Add a per-digit auxiliary prediction of 7-seg state (7 binary labels) or a small 7-seg heatmap inside each detected digit ROI.
   - Multi-task learning can improve representation robustness (Caruana, 1997; Kendall et al., 2018), and often reduces brittle confusions.
4. **Input normalization (moderate):**
   - Per-crop CLAHE on luminance or learned contrast normalization can reduce sensitivity to faint segments. Validate it doesn’t destroy the dot.
5. **Gate tightening that directly targets swaps (immediate):**
   - Enforce `min_margin ≥ 0.20` and/or `min_ratio ≤ 0.5` (Q1). This will cut coverage but reduces confident swaps.

---

## 5) Model selection with tiny/noisy eval sets (27 seeds vary TH34 21–25)

**Recommendation (1 line):** Use **EMA during training** + select via **cross-validated utility** on a dedicated dev set; optionally deploy a **single SWA/model-soup** only if it *improves calibration* on a held-out calibration set—do not pick by best score on the 73 frozen images.

**Justification:**  
- Seed variance is expected for small detectors and small data. Standard stabilizers are:
  - **EMA** weights (Polyak & Juditsky, 1992; widely used in modern detectors)
  - **SWA** (Izmailov et al., 2018)
  - **Model soups** (Wortsman et al., 2022)  
- Your soup results are non-monotone in N, which is normal when some seeds are miscalibrated/OOD; soups help when models are in the same basin and when you have a reliable selection criterion (you currently don’t—val saturates).

**Concrete deployment policy:**
1. **Training-time EMA:** decay 0.999–0.9999; export EMA weights only.
2. **Selection metric:** expected *accepted corrects* at a fixed “0 errors on calibration” threshold. That aligns with the product requirement.
3. **If you soup:** only soup the top-M models by *calibration-set* utility (M=5–10), not all 27.
4. **Avoid inference ensembling** unless you have latency headroom; 2× reader cost plus 2× locator cost likely breaks <100 ms on mid phones. If you need ensemble-like benefits, prefer SWA/EMA (no inference cost).

---

## 6) Training efficiency on 8 CPU cores total

**Recommendation (1 line):** Don’t over-optimize CPU training microseconds; first ensure you’re using **MKL/oneDNN + multithreading correctly**, then spend the remaining budget on **more seeds + longer schedules + targeted data** (hard negatives / manual boxes).

**Justification:**  
Your per-step 0.4 s “on one core” suggests you may be effectively single-threading compute. Small convnets typically benefit from proper intra-op threading on CPU; beyond that, gains are limited, and better results come from more training signal rather than squeezing 10–20%.

**Concrete checks / wins:**
1. **Ensure intra-op parallelism is enabled:**
   - `torch.set_num_threads(8)`  
   - Set env: `OMP_NUM_THREADS=8`, `MKL_NUM_THREADS=8`
2. **Enable oneDNN / channels_last (often helps CPU conv):**
   - Convert model and inputs to `channels_last` memory format.
   - Ensure PyTorch is built with MKL/oneDNN.
3. **Bigger batch if memory allows:**
   - If you can go batch 64 or 96, do it; reduce steps proportionally while keeping total seen examples similar. This improves CPU utilization.
4. **DataLoader:** you’re already low (0.03 s). Still: `num_workers=2–4`, `persistent_workers=True`.
5. **torch.compile on CPU:** sometimes helps, sometimes hurts; treat as “measure-only”. If compile overhead dominates short runs, skip.

If after threading you still can’t get good throughput, it’s likely close to your floor; spend cores on **more seeds** or **active-learning labeling**.

---

## 7) Setup issues that make numbers untrustworthy (be blunt)

**Recommendation (1 line):** Rebuild evaluation hygiene: split by **meter ID**, create a real **calibration/dev/test** separation, stop selecting gates on frozen tests, and stop trusting the saturated 68-image val.

**What violates/weakens standard practice:**
1. **Split by photo key, not by meter ID → leakage risk (high).**  
   Same physical meter photographed multiple times can land in both train and val/test, inflating metrics and miscalibrating the gate. For OCR-like tasks, identity leakage is a common pitfall. Fix: group split by meter identifier (or approximate via clustering if ID unknown).
2. **Using the 49/34 “frozen” sets for iterative decisions → test overfitting (high).**  
   If you tune thresholds, pick seeds, or choose soups based on these, they are no longer tests. You need:
   - Dev set (for gate/model choices)
   - Calibration set (for thresholding / conformal)
   - Final test (touched once)
3. **Val set saturates (68 images all seeds get 66/68 IoU50) → useless for selection (high).**  
   This indicates the metric is too easy or labels don’t represent deployment variation. You need harder val (more types, more bad lighting, rotations, partial occlusions).
4. **50/50 real/synth per batch may be suboptimal (medium).**  
   If synthetic is not extremely faithful for failure modes (Crystal dot, ghosting), it can dominate gradients and hurt calibration. Common practice is to tune the ratio by type and by epoch (start more synth, anneal to more real), but you must measure. Domain randomization helps only if it covers the real nuisance factors (Tobin et al., 2017).
5. **Gate based mainly on min_conf is demonstrably insufficient (you saw ONE_DIGIT_SWAP pass).**  
   This is not “wrong practice”, but it explains your confident wrong accepts. You need margin/instability features and calibration.
6. **Owner feedback/web-demo data is not cleanly incorporated.**  
   If it’s used informally for decisions, it becomes another hidden dev set. Either formalize it (with labels and splits) or treat it as anecdotal.

**Concrete remediation checklist:**
- Re-split m3 by **meter ID**; if unknown, annotate or approximate.
- Designate:
  - **Dev** (~200–400 imgs): iterate freely
  - **Calibration** (~200 imgs): fit gate/calibration only
  - **Test** (your current 73 frozen + add more): never touch until release candidate
- Report acceptance and errors with **Clopper–Pearson** bounds, not just point estimates.

---

If you want, I can propose an explicit **accept/reject threshold search procedure** (with pseudocode) that maximizes coverage subject to “0 observed errors on calibration”, and a minimal annotation plan (how many Crystal boxes you need to make the dot/boundary problem identifiable).
