# claude-opus-5-5 — 2026-10-24 08:39 UTC (189s)

# Consultation #2: answers

Two cross-cutting points change several answers below, so I state them first.

* **Cross-class ghosts.** CenterNet's 3×3 max-pool NMS (Zhou et al., *Objects as Points*, 2019) runs **per class**. Your ghost pairs on one cell usually have *different* labels: `005337.88 → 00563307018` contains 5→5,6; 3→3,3; 7→7,0; …. A "3" peak and an "8" peak 6 px apart never suppress each other. This is a decoder bug before it is a model problem.
* **Ensembles are affordable.** Speed is not a constraint, and each model is 0.21M params, so running 3–5 models is nearly free. Averaging their heatmaps, and using their agreement as a gate, is the cheapest lever you are not pulling. It appears in Q1, Q4, Q6 and Q7.

---

## Q1. Ghost detections

### Geometry, so the kernel sizes are not guesses

Recompute these from your own data (median predicted `w`, and the median gap between adjacent ground-truth (GT) digit centres).

* **Digit size in the crop.** With PAD_Y 0.45, the line occupies about 64/1.9 ≈ 34 px of the 64-px height.
  * 7-segment digit width is ≈ 0.55·h ≈ 19 px.
  * Pitch is ≈ 0.75·h ≈ 25 px.
  * At stride 4, the pitch is ≈ 6 heat-map columns.
* **What "IoU < 0.45" implies.** Two side-by-side boxes of width `w` offset by `d` have IoU = (w−d)/(w+d). IoU < 0.45 means d > 0.38·w ≈ 7 px ≈ 2 columns. So your ghosts sit 7–12 px from the true centre.
* **Kernel consequences.**
  * A 3×3 kernel (±1 column = ±4 px) can never suppress them, even class-agnostically.
  * ±2 columns (8 px ≈ 0.32 pitch) is safe against real neighbours.
  * ±3 columns (12 px ≈ 0.48 pitch) is borderline on tightly spaced displays.

### Ranking for 0.0-error (gain / risk)

**1. Class-agnostic peak extraction plus a cell-level class vector.** This is a decode-only fix and the clear first choice: high gain, low risk.

```python
def decode_cells(heat, wh, off, peak_min=0.25, nms_frac=0.5, win_frac=0.35):
    # heat: (C=11, H, W) after sigmoid
    agn = heat.max(0)                                  # class-agnostic objectness
    hmax = maxpool2d(agn, kernel=(3, 5), pad=(1, 2))   # wider in x only
    ys, xs = np.where((agn == hmax) & (agn >= peak_min))
    cand = sorted(zip(agn[ys, xs], ys, xs), reverse=True)

    # pitch from widths of strong peaks (ghosts are weak, so they barely bias this)
    strong = [c for c in cand if c[0] >= 0.40] or cand[:4]
    w_med = np.median([wh[0, y, x] for _, y, x in strong])
    pitch = 1.33 * w_med  # calibrate ratio pitch/w per dataset; 1.25-1.40 typical for 7-seg

    kept = []
    for s, y, x in cand:                               # 1-D NMS along x (option a)
        cx = x + off[0, y, x]
        if all(abs(cx - k['cx']) >= nms_frac * pitch / 4 for k in kept):  # /4 = stride
            kept.append(dict(s=s, y=y, x=x, cx=cx))

    for k in kept:                                     # evidence pooled over the cell
        r = max(1, int(round(win_frac * pitch / 4)))
        v = heat[:, max(k['y']-1, 0):k['y']+2,
                    max(k['x']-r, 0):k['x']+r+1].reshape(11, -1).max(1)
        order = np.argsort(-v)
        k['cls'], k['best'], k['alt'] = order[0], v[order[0]], v[order[1]]
        k['ambiguous'] = k['alt'] >= 0.5 * k['best']   # feeds `confident`
    return kept
```

The essential 0.0-error property is that suppression **never silently discards competing evidence**:

* The suppressed ghost's class score survives as `alt` in the cell vector.
* If the ghost was a "6" at 0.40 next to a "5" at 0.45, the cell becomes ambiguous and the reading is not confident.
* Coverage may drop slightly, but sequence correctness improves and false confidence cannot increase.

Two further details:

* **Dot class:** exclude it from the agnostic map. Decode dots separately with their own peak threshold, because dots sit between cells and the 1-D NMS would eat them.
* **Kotlin:** port the same code. Parity stays testable on your 49 golden outputs.

**2. Option (c), kernel along x only.** This is a subset of #1. A fixed 3×5 class-agnostic kernel without the pitch-adaptive pass is acceptable as the Kotlin-simple version. Do not go to ×7.

**3. Option (a), 1-D NMS alone, per class.** It is useless for the cross-class case. Do it class-agnostically, which is the #1 code above.

**4. Factorised head (training level), my preferred retraining fix.**

* Replace the 11-channel sigmoid heat with:
  * a 1-channel objectness heat (focal loss, as now), and
  * an 11-way softmax classification map supervised at GT centres plus a 1-pixel neighbourhood.
* Cross-class ghosts become structurally impossible, because there is one peak per cell.
* The softmax gives a proper runner-up for the ambiguity rule, replacing comparisons between independent sigmoids that are not commensurable.
* Cost: one extra 1×1 conv and a loss term. Init from the current backbone. Same ONNX size.

**5. Option (d), Gaussian radius tuned to cell width.**

* The CornerNet radius (Law & Deng, 2018) is driven by the short side of the box. For tall, narrow digits it gives a small σ_x, so the model learns narrow per-class peaks that do not inhibit a neighbour of another class.
* An elliptical Gaussian with σ_x ∝ w and σ_y ∝ h, as in TTFNet (Liu et al., 2020, α ≈ 0.54), helps somewhat.
* It does not address the cross-class problem. Do it only together with #4.

**6. Option (b), per-class RD_PEAK_MIN.** I would not do this.

* Ghost scores (0.30–0.45) overlap true-cell scores on MT10/EMETER (0.3–0.4).
* Raising the threshold converts ghosts into MISSING_DIGIT on exactly the types that are already weak.
* Per-class thresholds fitted on 38 photos overfit.

**7. Option (e), CTC/CRNN head.** Not in the next 3 days.

* CRNN+CTC (Shi et al., 2015/2017; Graves et al., 2006) removes ghosts by construction and gives a sequence-level probability.
* But you lose explicit positions, which are what the integer/fraction cut and lattice rules depend on.
* It is a new model trained from about 900 images plus synthetic data. Revisit if #1 and #4 leave more than about 30% of sequences wrong on val-m4.

### Measurement on the 38 raw-det photos, then confirmation

Per photo, align the decoded full sequence (including fraction digits and dot) to the display text with Levenshtein alignment. Report:

* **Sequence exact-match rate.** Baseline is 1/38.
* **Errors split by type:** insertions (ghosts), deletions (lost digits) and substitutions.
* **Count error:** `#dets − #cells`. Its histogram should collapse to 0.
* **Downstream:** end-to-end integer accuracy, strict-gate coverage, and strict-gate wrong count.

Treat the 38 as a dev set: at most 2 parameters (`nms_frac` ∈ {0.4, 0.5, 0.6}; kernel x ∈ {5, adaptive}).

**Confirm on val-m4** (177, with digit boxes), not on the 49/34. Success criteria:

* insertions drop by at least 80%;
* deletions rise by no more than 1 photo;
* gate wrong count stays at 0.

---

## Q2. Integer/fraction boundary without a visible dot

Make the cut a **vote among independent cues**, and declare `confident` only when the cues that are available agree. One weak cue alone should never decide a confident reading.

| Cue | Source | Cost | Notes |
|---|---|---|---|
| C1 dot | reader dot class | exists | Faint on MT10; absent on CRYSTAL |
| C2 locator right edge | LINE box | exists | Mode A > mode L proves it carries the boundary |
| C3 fraction flag per digit | new 1-channel head on reader | labels already derivable | Recommended new cue |
| C4 per-type layout (k_frac rightmost cells) | type known or classified | small | Very strong where the layout is fixed |
| C5 kWh glyph (12th class) | new labels | ~150 boxes | CRYSTAL only |

### C3 (recommended) instead of a glyph class or a separate regression head

Add one sigmoid channel at each digit centre: P(digit is fractional).

* **Labels.** You already have them. Any GT digit whose centre lies right of the integer-line box, plus half a pitch, or right of a GT dot, is fractional.
* **What the reader learns.** It sees the whole padded line, so it can use whatever cue each type offers: dot, glyph, spacing, slightly smaller digits, or the "rightmost-2-of-8" position.
* **Why it beats a 12th glyph class.**
  * There are no new annotations.
  * It works for MT10/EMETER, which have no glyph.
  * It degrades gracefully: low certainty means abstain.
* **Why it beats a boundary-x regression head.** A regression head gives one scalar, with no calibrated uncertainty and no tie to individual cells.
* **Note on your earlier negative result.** Fraction loss masking had no effect, but that told the model to ignore fraction digits. C3 asks it to *classify* them, which is a different signal.

### C2, trusted harder but properly

Retest LINE_CLIP **after** the Q1 fix. Your earlier mixed result was almost certainly contaminated, because the clip uses `k·pitch` and ghosts corrupt the pitch estimate.

Rule: drop digits with `cx > line_right + 0.5·pitch`. Report how often C2 disagrees with C1 when C1 is present. That rate is your estimate of the locator's boundary error.

### C4: ask whether the meter type is known

If the utility's customer record contains the meter model (Yemeni utilities typically register it per account), have the user pick it once per meter in the app. Then:

* **MT10:** k_frac = 2, out of 8 same-height cells.
* **CRYSTAL:** rightmost 2 cells under "kWh".
* Leading-zero blanking does not break this, because fraction cells are always lit and you count from the right.

Failing that, a type classifier on the meter crop is easy: types are visually very distinct, and you have 10k labelled photos with type tags, presumably.

### C5 (12th glyph class)

Only if CRYSTAL remains the dominant boundary failure after C2–C4. It is the narrowest cue.

### Combination rule (no learned fusion; 73 photos cannot support one)

```
cut_votes = {c: idx for c in available cues}
confident_boundary = len(set(cut_votes.values())) == 1 and len(cut_votes) >= 2
```

If only one cue is available, accept it only if it is C1 with dot score ≥ t_dot, or C4.

### Measurement protocol

1. Metric: **boundary accuracy conditional on a correct digit sequence**, i.e. predicted integer digit count = GT count. This separates cut errors from read errors.
2. Report it per cue and per type on val-m4, plus the pairwise disagreement matrix.
3. Report the gate in two forms: (i) single-cue cut, (ii) vote-cut. The vote should give lower coverage and 0 wrong. If it gives the *same* coverage, the cues are not independent and you have learned something.

---

## Q3. SMART_MT10 with zero data

**Order: (a) always, (b)+(c) as a cheap bet, plus an OOD/abstain path. Never tune on the 9.**

**(a) Report by type, permanently.** 9/39 of the frozen set is a type absent from 10,155 training photos. A pooled accuracy on this set says little about deployment in the owner's region. Report:

* trained types: 20/30, CP 95% CI [47%, 83%];
* MT10: 2/9, CI [3%, 60%].

The 0.0-error question for MT10 is not "how many right" but "how many *confidently* wrong". Today that is 0. Keep it that way, by abstention rather than hope.

**(b) Synthetic MT10 lines work, if you render the right failure modes.** Glyph shape is the easy part. What makes LCD 7-seg hard, and what synthetic data must include, is:

1. **Unlit segments faintly visible**, at 5–25% of lit-segment contrast. This is where 8-vs-0/6/9 confusions come from. If synth1 lacks this, add it to all types.
2. **Low global contrast on dark backgrounds**, with segment/background ΔL in roughly 10–40 on a 0–255 scale, plus polarity variants.
3. **Layout:** 8 equal cells, faint dot of 0–30% contrast between cells 6 and 7 (sometimes absent), and fixed pitch.
4. **Plastic-window artefacts:** specular bands, yellow tint from the case, and slight defocus.

Train fraction cells with C3 labels. The MT10 layout is exactly where a "rightmost 2 of 8" prior must be learned.

Experience from meter-reading work supports synthetic data for segment glyphs, though a domain gap remains on unseen meter models:

* Laroca et al. 2019 (UFPR-AMR) and 2021 (unconstrained AMR, Copel-AMR);
* Salomon et al. 2020, dial meters.

Expect a partial gain, not parity.

**(c) "MT10-isation" of existing real lines.** Darken, compress contrast, add a yellow tint, invert polarity where plausible, and add a synthetic faint-segment overlay.

* This is label-preserving, cheap, and in my experience does about as much as (b) for the photometric gap.
* It cannot teach the 6+2 layout.

**GAN style transfer: no.** CycleGAN-type methods need unlabelled MT10 target images, and the only ones you have are the 9 test photos. Using them is contamination.

**Evaluation discipline.** Pre-register *one* evaluation of the (b)+(c) model on the 9 MT10 photos and report it once. Every additional look turns the 49-set into a dev set; it is already partially one after 31 seeds.

**Product path.** MT10 comes from another region, so the owner may never collect it.

* If the type is known (C4) or classified, have the app route MT10 to "please type the reading" until data exists.
* Ask the owner whether *anyone* in that region can send 30–50 photos with readings. That is worth more than any synthesis.

---

## Q4. Honest validation: critique

### What is right

pHash-cluster splitting, Clopper–Pearson bounds, and a separate calibration set for the gate.

### Problems

1. **177 cannot resolve seed differences.**
   * 148/177 = 83.6%, CP 95% CI ≈ [77%, 89%].
   * Seed SD on m3 was about ±2/39; on 177 expect about 1.5–2.5 points.
   * "Pick the best of 3 seeds" inflates the winner by about +0.85σ ≈ 1.5–2 points. That is pure selection bias, and the 49/34 will then "regress".
   * **Better: don't select seeds. Ensemble them** (average sigmoid heatmaps of seeds 0, 1, 2, then decode). Deep Ensembles (Lakshminarayanan et al., 2017) improve both accuracy and ranking quality for selective prediction, and there is no selection bias.

2. **"49/34 not worse" as a promotion gate turns them into dev sets.** You already looked at them through 31 seeds and several recipe arms.
   * Log every access.
   * Use them only for a final report per *milestone*, not per candidate.
   * If a candidate passes val-m4, it ships; the 49/34 number is what you publish, not what you decide on.

3. **Compare paired, not marginal.** Use McNemar's exact test on the 177 per-photo outcomes, candidate vs reference. For example, 10 vs 2 discordant photos gives p ≈ 0.04; 6 vs 3 is noise.

4. **"Strict-gate wrong = 0" on a small accepted set certifies little.** With n accepted and 0 wrong, the one-sided 95% upper bound on error is ≈ 3/n (the rule of three).
   * 17 accepted ⇒ error ≤ 16–18%.
   * Claiming ≤ 1% risk needs about 300 accepted with 0 wrong.
   * Choose the threshold with Learn-then-Test (Angelopoulos et al., 2021): a fixed sequence of thresholds, from strict to loose, each tested with a binomial bound at δ = 0.05. Or use conformal risk control (Angelopoulos et al., 2022). Report the guaranteed risk level, not "0 wrong".

5. **The calibration set is too small. Fix it with out-of-fold (OOF) predictions.**
   * Train 3 cluster-disjoint folds on m4 (903).
   * That yields predictions on all ~900 photos from models that did not see them, about 5× more calibration data than half of val-m4.
   * The approximation: the deployed model is not one of the fold models. Two options:
     * deploy the 3 fold models *as* the ensemble, and calibrate on OOF ensembles of the other folds; or
     * accept the cross-conformal approximation (Vovk, 2015).

### Revised promotion rule

* McNemar non-inferiority on val-m4 versus reference (no significant loss; for a gain, p < 0.05).
* Gate threshold chosen by LTT on OOF predictions, with 0 wrong on val-m4 at that threshold.
* Report the 49/34, per type, with CP bounds, once per milestone.

---

## Q5. Capacity

Low peak scores do not show low capacity.

* **Heatmap peaks are soft by design.** CenterNet peaks are trained against Gaussians with focal loss, so even large models routinely sit at 0.4–0.7. Stride-4 quantisation further lowers the peak sampled at the integer pixel.
* **Low scores on MT10/EMETER (0.3–0.4) are domain shift.** Capacity will not fix a type it has never seen.

### Zero-cost diagnostic first

Run the current reader in mode L on its **own training photos**, real only, no augmentation.

| Train real acc / scores | val-m4 | Diagnosis |
|---|---|---|
| ≈ val (~84%), scores 0.4–0.5 | 84% | **Underfitting**: capacity, or augmentation too strong for 0.21M |
| ≫ val (≥97%), scores ≥0.7 | 84% | **Data-limited**: width won't help much |

### Then one controlled experiment, only if underfitting

* Width ×1.5 and ×2. Note that ×2 channels is about **×4 params and ×3–4 FLOPs**, not ×2.
* Identical recipe and steps, init from scratch (or inflate weights if feasible), 2 seeds each.
* Compare four quantities:
  * train-real fit;
  * val-m4 mode-L accuracy (McNemar, paired);
  * median correct-cell score;
  * risk–coverage curve (area under it, AURC).
* Also run one arm with AUG v2 photometric strength halved at ×1 width. If that closes the gap, the issue is augmentation/capacity balance, not width per se.
* On CPU this is about 4–6 runs; schedule it overnight (see Q7). My prior is that ×2 gives +2–4 points on trained types and ~0 on MT10.

---

## Q6. Confidence: coverage at 0 wrong

| Method | Expected effect | Why |
|---|---|---|
| Temperature scaling (Guo et al., 2017) | **≈ none** | Monotone per score. `min_conf ≥ t` has the same ranking, so you just retune t. It only interacts with the ratio rule `alt < 0.5·best`. It does not change what is separable. |
| Seed ensemble (3–5 models): averaged heat + **agreement of integer strings** | **largest** | Errors from independent seeds are partly uncorrelated. Disagreement is a strong error detector, and averaging lifts correct-cell scores. |
| TTA agreement (gamma 0.8/1.25, scale 0.9/1.1, ±2 px shift; plus locator box jitter ±5%) | large, partly overlapping the ensemble | Catches fragility to crop/boundary; directly targets the locator-box failure mode (9/17 faults) |
| DSEG template veto (AUC 0.76) | small, possibly negative | Weak ranker. As a veto it costs coverage on low-contrast types, exactly where it is least reliable. Keep only if it removes errors at ≤2% coverage cost on OOF. |
| Plausibility vs previous reading (if the app stores history) | very large where available | Reading ∈ [last, last + max monthly kWh]. Catches boundary errors (×10/÷10) almost perfectly. Ask the owner whether this exists. |

### Combination without overfitting 73 photos

Use a **pre-specified conjunction** with a single tuned threshold, not a learned combiner (logistic regression on 73 points will overfit).

```
confident = (all K ensemble×TTA runs give identical integer string)
        and (boundary vote unanimous, Q2)
        and (no ambiguous cell, Q1)
        and (min over cells of ensemble-mean best score >= t)
        [and plausibility check, if history exists]
```

* Tune only `t`, by LTT on OOF predictions (Q4).
* Agreement ("self-consistency") is threshold-free, so it costs no degrees of freedom.
* Expectation: coverage should rise from 23% to roughly 40–55% on trained types at 0 observed wrong, mostly because ensemble averaging raises the min-score of correct readings and agreement replaces the overly strict 0.55 cut. This is my prior, not a measurement.

---

## Q7. Stop / start, 3 days, 8 CPU cores

**Stop:** seed sweeps on m3, weight soups, AUG v3 reader tilt, fraction loss masking, and any decision that consults the 49/34.

### Day 1 (decode and analysis; CPU runs m4 seeds already in flight)

1. **Q1 decoder.** Class-agnostic NMS, cell vectors, ambiguity flag, dots decoded separately. Measure on the 38, confirm on val-m4. Port to Kotlin; re-check 49/49 parity.
2. **Cross-tab fault mode × type for the 17 failures.** My strong guess is that most of the 9 locator failures are MT10/EMETER_GREEN. If so, the locator is not the generic bottleneck its 96% val suggests.
3. **Q5 zero-cost diagnostic** on the training set.
4. **Retest LINE_CLIP** on top of the new decoder. Add the boundary-vote logic (C1 + C2 + lattice).
5. **Ask the owner three questions:**
   * Is the meter type known per account?
   * Does the app or utility have the previous reading?
   * Can anyone get MT10 photos?

### Day 2 (training; overnight queue)

6. **Ensemble m4 seeds 0, 1, 2** via heat averaging, plus the agreement gate. Measure the val-m4 risk–coverage curve against the best single seed.
7. **Fix the reader-input mismatch** exposed by mode L < mode A. Train the reader on boxes jittered to match the *measured* locator residual distribution (fit dx/dy/dw/dh from locator-vs-human on m4 val), not on clean human boxes.
8. **Add data.**
   * Add the 134 unused photos, but **drop the 41 two-digit CRYSTAL labels** unless a human verifies the box is on the kWh line (8/33 poisoned is too high a rate).
   * Have the reviewer box the remaining 19.
9. **Start the 3-fold OOF run** (reader + locator) for calibration, with the C3 fraction head added (cheap) and the factorised head if Day 1 shows many residual cross-class ghosts.
10. **Width ×2 controlled run** (2 seeds), only if the Day-1 diagnostic says underfitting.

### Day 3 (calibrate, report)

11. **Gate threshold** by LTT on OOF. Freeze.
12. **Synthetic data.** Add the unlit-segment rendering plus the MT10 layout to synth (benefits all types); train one candidate.
13. **One milestone evaluation** on 49/34:
    * per type, with CP bounds;
    * accepted count and wrong count, with the 3/n bound stated explicitly;
    * one pre-registered MT10 number.
14. **Collection brief for the owner:**
    * readings for the 97 tilted photos (typing a number is cheap; boxes can come from ensemble pseudo-labels that a human only verifies);
    * 30–50 photos each of MT10 and EMETER_GREEN.

### Where the evidence is thin

* The ghost-offset and pitch numbers above are derived from your thresholds, not measured. Compute them before fixing kernel sizes.
* The coverage projection in Q6 is a prior.
* The claim that most locator faults concentrate on unseen types is a hypothesis that the Day-1 cross-tab will confirm or kill.
