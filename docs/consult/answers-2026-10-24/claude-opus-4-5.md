# claude-opus-4-5 — 2026-10-24 04:21 UTC (596s)

# External review — almaham-3 meter reader

Blunt upfront: your biggest problems are statistical (tiny eval sets, split leakage, saturated val) and structural (Crystal boundary is unresolvable from current signals), not training-recipe. Spend effort there.

---

## Q1. Selective-prediction gate

**Recommendation:** Use split-conformal "selection with guaranteed FDR/FPR" (Learn-then-Test, Angelopoulos et al. 2021; Conformal Risk Control, Angelopoulos et al. 2022) on a simple monotone score; do NOT fit a logistic regression — you don't have the data.

**Justification.**
- With ~73+68+97 ≈ 238 images and a target of "0 wrong," Clopper–Pearson is unforgiving: observing 0/50 wrong gives a 95% upper bound of 7.1% error; 0/100 → 3.6%; 0/200 → 1.8%. You literally cannot *demonstrate* ≤1% error without a few hundred clean labels. State this to the owner.
- A learned gate over 6 features on ~150 calibration points will overfit; VC-style rule-of-thumb wants ≥10×dim×1/ε. Keep the gate low-dimensional.
- Conformal "selective classification" (Geifman & El-Yaniv 2017, "Selective Classification for Deep Neural Networks"; and the Risk-Controlling Prediction Sets framework, Bates et al. 2021) gives a distribution-free guarantee: pick threshold τ on a 1-D score s so empirical risk ≤ α with probability 1-δ on exchangeable data. For target α=0.01, δ=0.05, you need n ≥ ~300 calibration items with zero errors above τ. You're short.

**Concrete gate.** Combine signals into a single monotone score, then conformalize:
- s = min_digit_peak − 0.5·runner_up_ratio + 0.2·locator_score + 0.3·lattice_regularity − 0.4·(1 if n_digits∉[4,7] else 0).
- Weights not fit — chosen from your failure stats (min_conf OK 0.53 vs wrong 0.35 is your strongest signal; runner-up next).
- Add TTA agreement as a *hard* gate (not inside s): run 3 augmentations (±5° rotation, ±5% scale, mild gamma), accept only if top-1 string identical on all 3. This alone will kill most ghost-segment swaps (they're unstable under affine).

**Validation.** Report Clopper–Pearson 95% CI for (wrong|accepted) and coverage on each of the three eval shards separately (TH34, 49A, 49B, field-97). Don't pool. Pre-register the threshold before touching the frozen 73.

---

## Q2. Integer/fraction boundary for Crystal

Rank (best first):

1. **(c) 2× resolution for Crystal only, triggered by type classifier.** Expected gain: largest and lowest-risk. Dot peak 0.07–0.29 at 1 px → at 2 px you're in the 0.3–0.6 range the net was trained on. CPU: 64×448 → 128×896 is 4× FLOPs on the reader ≈ +15–25 ms, acceptable. Risk: low — same model, same labels. Data: none new.
2. **(a) 12th "last-integer-digit" heatmap class.** Expected gain: moderate–high if you have N per sample (you do: len(label)). You convert an invisible-dot problem into a visible-digit problem. CPU: negligible (+1 channel). Risk: medium — the net may latch onto position bias; mitigate by training with heavy horizontal shift aug and variable-N. Data: relabel existing crops programmatically (last integer char index). This is essentially the "key-point as semantic class" trick (CenterNet, Zhou et al. 2019).
3. **(b) 1-D boundary regressor head.** Similar to (a) but regresses a scalar x-coordinate. Slightly worse than (a) because regression under label noise is harder than a sharp heatmap peak; CenterNet-style heatmaps outperform regressors on sub-pixel localisation (Law & Deng 2018, CornerNet).
4. **(d) CTC with explicit boundary token.** Expected gain: potentially high but *high confident-error risk* — CTC collapses alignment and your "min peak" confidence stops meaning what it means. Also 0.21M params won't give you a useful LSTM/attention stack. Rejected unless you redesign the whole reader.
5. **(e) Type classifier → digit-count prior.** You already rejected fixed-K; a *soft* prior (e.g., Crystal: P(N=5)=0.6, 6=0.3, 4=0.1) used only to break ties is safe, but it won't fix the boundary when N is actually variable. Low gain alone; useful as a feature in Q1 gate.

Concrete plan: ship (c) now (one week), add (a) as a parallel head next iteration.

---

## Q3. 612 photos with reading but no box

**Recommendation:** (iii) self-training with hard reading-consistency verification, bootstrapped by (i) multi-scale weak-labelling; avoid (ii); use (iv) only as a last 50-image audit.

**Justification.**
- (i) **Multi-scale sliding window with reading-consistency**: run reader at scales {0.75, 1.0, 1.33, 1.5} and aspect ratios {6:1, 7:1, 8:1}, accept box iff reader output == label AND min_conf ≥ 0.5 AND N==len(label). This is textbook weak-to-strong (Xie et al. 2020, "Self-training with Noisy Student"). Low poisoning risk because the equality check is exact.
- (iii) is the same idea with the current locator proposing; add it as a second round.
- (ii) **MIL with reading-consistency loss** sounds principled but is unstable with 0.21M params and no pretrained backbone; the loss has many local minima where the locator picks a wrong line whose reader hallucinates the right digits. Known failure mode in weakly-supervised detection (Bilen & Vedaldi 2016, WSDDN; Tang et al. 2017, OICR — they all need an ImageNet-pretrained backbone to work).
- (iv) Manual boxes on 50 hardest (TOMAS 176, SMART_YELLOW 96) will give more per-hour than any algorithmic trick. Do it.

**Pitfall:** readings like 000123 are satisfied by many spurious crops (any crop containing "123" plus noise can OCR to 000123 if the model hallucinates zeros). Require the box to cover *all* detected digits with ≥0.9 of their mass, and require pitch regularity (your existing check).

---

## Q4. Ghost-segment confusions

**Recommendation:** (1) hard-negative synthetic rendering with explicit ghost segments, (2) local contrast normalisation at input, (3) auxiliary 7-segment mask head. In that order of ROI.

**Justification.**
- **Synthetic ghosting**: your line_s1/line_crystal_opt2 presumably render clean segments. Add per-segment residual intensity ∈ U(0.05, 0.25) of the on-segment intensity, independently per segment, per digit. This directly targets 5↔6 (segment 'c'), 9↔0 (segment 'd'), 9↔8 (segment 'e'), 2↔3 (segment 'f'), 7↔1 (segments 'a','f'). Cheap, high leverage. Published analogue: Jaderberg et al. 2014 showed synthetic text with controlled nuisance variables matches real OCR distributions.
- **Local contrast normalisation / CLAHE** on input: ghost segments are low-contrast; CLAHE compresses this signal. Risk: can also kill real-weak-segment digits; evaluate carefully. Pinto et al. 2008 ("What is the best multi-stage architecture...") established LCN as a strong normaliser for recognition.
- **Auxiliary 7-segment mask head**: predict a 7-channel mask per detected digit, supervised from synthetic (free) and a few hundred real labels. Multi-task helps regularise (Caruana 1997); here it forces the trunk to represent segments explicitly rather than digit-shape gestalt, which is where ghost errors come from. +5–10% params only if you share the trunk.
- **Published seven-segment OCR with ghosting**: Finnegan et al. 2019 ("Automated Reading of Seven-Segment Displays") and the SSOCR tradition handle it with per-segment thresholding; recent CNN work (Popayorm et al., Kanagarathinam & Sekar 2019) does not specifically address ghosting — this is an underserved niche. "Unknown" for a strong published baseline on ghost-segment confusion rates.

TTA (Q1) + synthetic ghosts is the pragmatic combo.

---

## Q5. Model selection with 27 seeds

**Recommendation:** EMA within a run + uniform weight-soup of top-k by *held-out loss* (not TH34 accuracy); deploy a 2-seed ensemble only if TTA budget allows.

**Justification.**
- Your TH34 σ=1.3 on 34 items means ±1 image shift is well inside noise. Selecting on TH34 is overfitting; your soup5/10/27 non-monotonicity is the symptom. "Model Soups" (Wortsman et al. 2022) explicitly shows greedy soup > uniform soup when the selection signal is informative, and both ≈ best single when it is not — which is your regime.
- **EMA** (Polyak averaging; Tarvainen & Valpola 2017, Mean Teacher) is near-free and reliably reduces seed variance for CenterNet-style heatmap nets. Enable with decay 0.999, start after step 500.
- **SWA** (Izmailov et al. 2018) over the last 25% of training is also near-free; stack with EMA.
- **2-seed inference ensemble**: averages heatmaps, ~halves selection variance. 2× CPU cost is probably the biggest single-shot accuracy gain you can get; use the budget you'd spend on resolution for Crystal here only if (c) in Q2 isn't adopted.
- **Do not pick on frozen 73.** The frozen set exists so you can report. Use the m3 val for ranking even though it saturates on IoU50 — switch its metric to *reader-end-to-end exact-match* or line-score, which won't saturate.

---

## Q6. Training efficiency on 8 CPU cores

**Recommendation:** You're near the floor for this model size on CPU. Spend cycles on more seeds and longer schedules, not optimisation tricks. Two small wins: channels_last + larger batch.

**Justification.**
- 0.4 s/step at batch 32 on 0.21M params ≈ ~1.5 GFLOPs/step on 1 core at ~4 GF/s effective — this is close to Xeon FP32 practical throughput for small conv kernels (memory-bound).
- **torch.compile on CPU**: usually 10–30% for small convs via Inductor, sometimes regresses on tiny models. Try, measure, keep if positive. ONNX Runtime with graph-opt is often faster than PyTorch eager for your shapes.
- **channels_last** (`memory_format=torch.channels_last`): 10–20% on CPU conv (PyTorch docs). Free; adopt.
- **Mixed precision**: correct — bf16 is slow on anything pre-Ice Lake / without AMX. Skip.
- **Larger batch, fewer steps**: with AdamW and cosine, going from batch 32 → 64 at 1500 steps is near-equivalent on your scale (McCandlish et al. 2018, "Empirical Model of Large-Batch Training"); test.
- **Compile the data pipeline into a shard-cached tensor file** so step time is pure compute. 0.03 s/step overhead is already fine, mentioning for the record.
- Headline: at ~50 min/run, 8 cores = ~230 runs/day for the reader. Use that for EMA/SWA sweeps and seed ensembles, not micro-optimisation.

---

## Q7. Practice violations making your numbers untrustworthy

Blunt list:

1. **Split by photo key, not by meter id.** Serious leakage: same meter photographed twice ends up in train and val. Expect 5–15% optimistic bias on IoU50 and end-to-end accuracy. This likely *fully explains* "IoU50 66/68 for every seed." **Fix now**: re-split by meter id, re-run one seed, publish the delta internally.
2. **Selecting models on the 49/34 frozen sets.** You've been doing this (seed study optimises TH34). These are now training sets. The *actual* frozen set is the 97 field photos with feedback, and even those are at risk if you tune towards them. Create a *new* ~100-image frozen set and don't look at it until deployment review.
3. **50/50 real/synth ratio** without curriculum: with 1000 real and 24k synth, oversampling real 24× means the model sees each real crop ~24× per epoch. If augmentation is weak, this memorises. Your AUG v2 is reasonable, but check training loss on real-only subset vs eval loss — gap tells you.
4. **Val set that saturates (IoU50 66/68) is being used as a selection signal.** Useless, as you noted; it's actively harmful because it gives false confidence. Replace with end-to-end string exact-match and digit-level edit distance.
5. **Owner_visual ×2 weighting** without documenting what distribution it represents may skew the model to one phone/user; verify it doesn't correlate with meter type.
6. **No per-type stratified reporting** in training logs. TH34 CRYSTAL 2/7 on 31/31 seeds is a clear signal the model can't do Crystal at all; aggregate numbers hide this. Report per-type always.
7. **Reading `min_conf` as a calibration score** — CenterNet heatmap peaks are not calibrated probabilities (Guo et al. 2017, "On Calibration of Modern Neural Networks"); add temperature scaling fit on held-out before using in a conformal gate.
8. The "0.0 error" claim is not statistically supported by any eval you currently have; be explicit with the owner about the Clopper–Pearson bounds (Q1). Promising zero with n=73 is unprofessional.

---

### Priority stack if I had your week
1. Re-split by meter id, re-baseline. (half day)
2. Crystal 2× resolution path + type classifier gate. (2 days)
3. Hard-negative ghost-segment synthetic + retrain. (1 day + overnight)
4. TTA 3× agreement as hard gate; conformal threshold on combined score. (1 day)
5. Weak-label 612 photos with multi-scale consistency; manual-box the 50 hardest. (1 day)
6. EMA + 2-seed heatmap ensemble at inference. (half day)

Expect: coverage at 0 wrong on TH34+49 to roughly double (today 17/73); Crystal to move off 2/7. Do not promise this to the owner before measuring.
