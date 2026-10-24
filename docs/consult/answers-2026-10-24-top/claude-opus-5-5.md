# claude-opus-5-5 — 2026-10-24 04:24 UTC (188s)

# Consultation response: almaham-3 meter reader

**Summary.** Your "0 wrong / 17 accepted" result is not evidence of safety. Your own seed study refutes it: mean 1.37 wrong accepted per seed, and only 4/27 seeds had 0 wrong. That puts the honest selective risk of the current gate at roughly 5–10%. With 17 accepted and 0 errors, the 95% Clopper-Pearson upper bound is 16%. The rest of this response treats "0.0 error" as "risk ≤ r\* at confidence 1−δ, measured on data the gate never saw."

The largest untapped asset is the 612 photos with known readings. They are useless for boxes until fixed, but ideal for calibrating the gate.

---

## Q1. Selective prediction gate

**Recommendation:** Use three layers, in this order:
1. Monotone hard vetoes based on agreement.
2. A small logistic score with ≤5 features.
3. A threshold chosen by a binomial risk bound (SGR / Learn-then-Test) on a calibration set split by meter ID, which must not be the 73 frozen images.

**Justification**

- **Why not split conformal prediction.**
  - Standard split conformal produces prediction *sets* with marginal coverage. You need to bound the error rate *among accepted* outputs. That is a risk-control problem.
  - Directly applicable methods:
    - Geifman & El-Yaniv 2017, "Selective Classification for Deep Neural Networks" (the SGR algorithm, a binomial bound on selective risk).
    - Bates et al. 2021, "Distribution-Free, Risk-Controlling Prediction Sets."
    - Angelopoulos et al. 2021, "Learn Then Test."
  - All of these assume exchangeability. A new meter type or a new phone camera breaks the guarantee, so you need per-type monitoring (below).
- **Why vetoes beat learned features at n≈100s.** Agreement signals (TTA, ensemble, crop jitter) are nearly binary and monotone. Treating them as vetoes needs no fitting and cannot overfit. Kamath et al. 2020 ("Selective Question Answering under Domain Shift") found a small calibrator on such features beats raw softmax confidence. Your separability numbers (median min_conf 0.53 OK vs 0.35 wrong) say the same.
- **Your current `alt` is too weak.**
  - Cross-class NMS keeps a runner-up only if a second peak survives. Ghosting usually produces *one* peak with the wrong class.
  - Instead, read the full 11-class vector at the peak location (3×3 max-pool neighbourhood).
  - Then compute the margin against the best class within segment-Hamming-distance ≤2 of the winner (see Q4). This targets the ONE_DIGIT_SWAP cases that currently pass.

**Concrete design**

1. **Vetoes.** Reject if any of the following holds:
   - Status is not OK.
   - Any digit changes under K=6 TTA variants:
     - Locator-box jitter of ±0.15 pitch horizontally (left and right).
     - Scale ×0.92 and ×1.08.
     - Gamma 0.7 and 1.4.
   - Box jitter directly probes EXTRA_RIGHT and MISSING_LEFT. Gamma directly probes ghosting.
   - The 2-model ensemble disagrees (Q5).
   - Integer digit count is implausible for the predicted display subtype (Q2e).
2. **Logistic score.** Fit on surviving candidates, L2-regularised, standardised features, at most 5:
   - Σ log p(digit) at peaks. Use the sum, not the min; the sum penalises many mediocre digits.
   - Min Hamming-aware margin.
   - Locator top-1 score.
   - Locator top-2/top-1 ratio (line ambiguity).
   - Lattice residual: max gap / pitch, and pitch coefficient of variation.
   
   Keep features ≤ (#wrong examples)/10 (Peduzzi et al. 1996 events-per-variable rule). With ~50 wrong readings, 5 features is the ceiling.
3. **Threshold via SGR.**
   - Sort calibration items by score.
   - For candidate thresholds in a fixed coarse grid (e.g., 10 values), compute the Clopper-Pearson upper bound on error among accepted.
   - Use Bonferroni δ/10, or fixed-sequence testing from the most conservative threshold downward as in LTT, which needs no Bonferroni.
   - Choose the largest coverage with bound ≤ r\*.

**Calibration data**
- Primary: the 612 photos with known readings, run end-to-end. Reading correctness needs no box. They are harder than average because the weak labeller failed on them, so they are conservative for the gate.
- Keep MECHANICAL meters as negatives: the gate must reject them.
- Split by meter ID: ~50% for fitting the logistic, ~50% for the threshold bound. This conflicts with using them for locator training (Q3). Resolve with a meter-ID split: about 350 for training, about 260 for calibration.
- The 97 field photos with feedback are feedback-biased (users report failures more often). Use them for monitoring only.
- The 73 frozen images: final report only, touched once per release.

**Honest bounds (95%, 0 errors observed among n accepted):**

| n accepted | Upper bound on error |
|---|---|
| 17 | 16.2% |
| 50 | 5.8% |
| 100 | 2.95% |
| 300 | 0.99% |

With 1 error in 100 accepted, the bound is 4.7%. With ~260 calibration images at ~40% coverage (≈100 accepted), the best you can *certify* is about 3%. Tell the owner this. Certifying ≤1% requires about 300 accepted, i.e., about 750+ labelled calibration images at 40% coverage. Plan for that through field accumulation.

**Reporting.** Report the risk–coverage curve and AURC (Geifman, Uziel & El-Yaniv 2019, "Bias-Reduced Uncertainty Estimation for Deep Neural Classifiers"), per meter type. Do not report a single operating point.

---

## Q2. Integer/fraction boundary on Crystal-like displays

**Recommendation:** First run a 1-hour data audit. Then:
- Change the line definition so the locator finds *all* digits.
- Add a right-anchored fraction-count prior as a veto.
- Add a high-resolution gap/dot verifier.
- Do not do the 12th class.

**Audit first.** On 20 Crystal photos, at *source* resolution:
- Is the dot visible? Measure its size in source pixels.
- Is the gap before the fraction larger than other gaps, in pitch units?
- Are there other cues: colour, a box or frame, a "kWh" or underline position?

If the dot is invisible even in the source photo, and the gap ratio is under ~1.08, then no visual method can work. The correct behaviour is then "reject unless the prior is unambiguous," with Crystal coverage near 0. That is acceptable under your rule.

**Structural issue.** The locator target is the "union of integer digit boxes." On Crystal this asks the locator to solve the boundary problem using a ~12 px digit at stride 4. That makes its labels inconsistent and its line score noisy (EXTRA_RIGHT line_score is 0.27–0.47). Change the target to the full digit row (integer + fraction) and give the boundary decision to one module that sees the reader output.

**Clarification of the previously rejected idea.** The rejected idea was a fixed *total* K digits, which fails because Crystal has no leading zeros. A fixed number of *fraction* digits counted from the right is a different prior. It does not depend on magnitude. Check in your labels whether, for each display subtype, (total detected digits − len(label)) is constant. If it is, for example always 1, that is a strong, cheap cue.

**Ranking (most to least recommended)**

| Rank | Option | Expected gain | Confident-error risk | Data | CPU |
|---|---|---|---|---|---|
| 1 | **(e′) Right-anchored fraction-count prior, used as a veto/consistency check, not an override.** Needs a subtype classifier on the meter crop, which can be a tiny head on the locator backbone. Accept only if the classifier's p ≥ 0.95 *and* the reader's digit count is consistent. | Fixes most EXTRA_RIGHT as rejections; some become correct accepts | Low as a veto. High if used to *construct* readings: type errors are systematic, as your previous consultant correctly said. | Labels already exist (type + reading) | ~0 |
| 2 | **(c′) High-res gap verifier**, not a full 2× reader. Crop each inter-digit gap from the *original* image, lower 40% of digit height, resize to 24×24, and run a ~10k-param CNN that outputs P(dot). Labels are free: for each training line, the gap after digit N=len(label) is positive and the others negative, giving ≈6k labels from 1029 lines. | Large *if* the audit shows the dot in source pixels; zero otherwise | Low. Combine with (e′) and require agreement. | Free from existing labels | <1 ms/gap, ~8 gaps |
| 3 | **(b) Per-line boundary head:** global-pooled features → softmax over gap index (0..L). This gives a distribution, so its entropy and max probability can feed the gate. | Moderate. Learns layout priors plus any gap or dot cue. | Medium. Without visual cues it learns priors and is confidently wrong on atypical meters. Gate on p_max ≥ 0.9. | Existing labels | Negligible |
| 4 | **(c) Full reader at 128×896** | Same as (c′) for the dot, plus somewhat better ghost resolution | Same as now | Retrain | ~4× reader FLOPs; probably still within 100 ms total but tight; measure on a low-end phone |
| 5 | **(d) CTC recogniser with a boundary token** (CRNN, Shi et al. 2015/2017) | Sequence-level likelihood is good for gating, and the model sees the whole line | Medium. CTC sequence probability is overconfident on small data and you lose per-digit geometry. | 1029 real lines is thin; relies on synthetic data, which already failed to move Crystal | Small |
| 6 | **(a) 12th heat-map class "last integer digit"** | Low | **High.** It is a local decision, and a 0.21M stride-4 net's receptive field likely does not span the line, so it cannot "count." It will learn shape priors and fire confidently in the wrong place. | — | — |

**Evidence on synthetic Crystal data.** The 31/31 seeds stuck at Crystal 2/7 with Crystal synthetic data confirms that the information is missing at 64 px height, not that the model lacks examples. No synthetic data will fix an information deficit.

---

## Q3. Using the 612 photos with readings but no boxes

**Recommendation:** Use verification-based pseudo-labelling (ii + iii merged) only as a pre-filler for a human click-to-confirm tool. Draw manual boxes (iv) for everything verification can't confirm.

612 boxes is about 1–2 person-hours. Nothing algorithmic beats that on reliability.

**Justification**

- **Confirmation bias.** Self-training with hard verification (Xie et al. 2020 Noisy Student; Sohn et al. 2020 STAC; Liu et al. 2021 Unbiased Teacher) adds mostly images the current model already handles. Your failures are concentrated in the images verification *rejects*: Crystal, ghosting, missing leading digits. Expect the pseudo-labelled subset to improve robustness slightly and leave Crystal untouched.
- **False verification (poisoning).** Exact-string match at ≥4 digits is rarely wrong by chance. Systematic false matches do exist:
  - Smart meters cycling registers: the cumulative kWh vs. another register can coincide in prefix.
  - The reader dropping a fraction digit inside a too-wide box, so the box includes the fraction.
  - A ghost-swapped digit happening to equal the label is rare.
- **Geometric checks to add on top of string match:**
  - Box width within ±25% of N × median pitch.
  - Box height consistent with digit height.
  - Match must be stable under ≥2 of 3 crop jitters.
  - Match must hold for ≥2 independent reader seeds.
- **MIL / reading-consistency loss** (option ii, trained end-to-end) is the principled version. It converges to the same thing as iterative pseudo-labelling over top-K proposals, at higher implementation cost and with the risk of collapsing onto a consistently wrong but readable region. Not worth it at this scale.

**Concrete procedure**

1. **Generate candidates:**
   - Locator top-20 peaks × 3 scale paddings.
   - A multi-scale sliding window: heights 8–25% of crop height, stride 1/4 window width.
2. **Accept automatically** when all hold:
   - Exact match.
   - Agreement across 2 reader seeds.
   - Jitter-stable.
   - Width/pitch consistent.
3. **Human review:**
   - Show auto-accepted boxes for a 1-click yes/no (fast, about 2 s each).
   - Draw manually for the rest.
4. **Scope:**
   - Drop or segregate MECHANICAL meters (out of scope; keep them only as gate negatives).
   - Split by meter ID between locator training and gate calibration (Q1).
5. **Draw full-row boxes** (integer + fraction) plus a boundary x-coordinate (Q2). The boundary comes from the label at almost no extra cost.

---

## Q4. Ghost-segment confusions

**Recommendation:** Use this mix:
- An auxiliary 7-segment head with labels derived for free.
- Synthetic off-segment contrast sampled from measured real distributions.
- Gamma-TTA as a gate veto.
- A Hamming-aware margin.

Of these, the gamma veto and the Hamming-aware margin will cut accepted errors fastest. The training changes reduce raw confusion more slowly.

**Literature.** I know of no published paper that quantifies ghost-segment confusion specifically. Relevant work exists on seven-segment and meter OCR:
- Kanagarathinam & Sekar 2019 (Energy Reports), on seven-segment energy-meter displays.
- Gómez et al. 2018, "Cutting Sayre's Knot," DAS (segmentation-free meter reading).
- Laroca et al. 2019 (J. Electronic Imaging) and Laroca et al. 2021 (IEEE Access), on UFPR-AMR and Copel-AMR. These are mostly mechanical/dial meters, but they include cross-dataset AMR results showing large domain drops.

None reports targeted results on off-segment ghosting.

**Interventions**

1. **Segment-level auxiliary head.**
   - At each digit centre, predict 7 sigmoid bits a–g. The labels follow deterministically from the digit class; treat the dot as a separate bit.
   - Loss weight 0.5 relative to the heat-map loss.
   - At inference, compute the Hamming distance between the class head's digit and the thresholded segment bits. Reject if it is ≥1.
   - This gives a second, partially independent opinion that focuses on exactly the contested segment.
   - Expected effect: a moderate reduction in raw swaps (my estimate, not published). A useful disagreement veto either way.
2. **Hamming-aware margin.**
   - Single-segment-difference pairs: 8↔0, 8↔6, 8↔9, 6↔5, 9↔5, 9↔3, 7↔1.
   - Two-segment-difference pairs: 3↔2 (c→e), 0↔7, etc.
   - Require p(top) − max p(c) over classes c with Hamming(top, c) ≤ 2 to be ≥ 0.25, measured on the per-class heat-map at the peak. Calibrate that number on the Q1 calibration set.
3. **Synthetic off-segments.**
   - Measure on ~50 real crops the ratio (off-segment darkness − background) / (on-segment darkness − background). It is likely 0.05–0.4 normally and higher with glare or viewing angle.
   - Sample the synthetic ghost ratio from that empirical distribution, oversampling the upper tail (0.3–0.7) with 30% probability.
   - Add a specular-glare blob covering 1–2 segments with 20% probability.
   - Hard-negative mining: emphasise synthetic digits whose ghost pattern equals a confusable neighbour (e.g., a 5 with a ghost e-segment, which looks like 6).
4. **Gamma / contrast TTA veto.**
   - Ghost confusion is threshold-like: the network decides whether a segment is on based on relative contrast.
   - Read at gamma {0.7, 1.0, 1.4}. If any digit changes, reject.
   - Cost: 3 reader passes, cheap.
   - This most directly hits the 5 ONE_DIGIT_SWAP cases that passed or nearly passed the gate.
5. **Contrast normalisation of input** (per-line percentile stretch: map 2nd/98th percentiles to 0/1). Cheap and worth one ablation run. CLAHE is riskier: it amplifies off-segments locally. Not a priority.
6. **Type-conditioned augmentation:** only if the audit shows ghosting concentrated in specific types. Otherwise skip.

---

## Q5. Model selection with noisy tiny eval sets

**Recommendation:**
- Stop picking seeds.
- Fix the recipe, train with EMA, and deploy a 2-model ensemble (locator and reader) with heat-map averaging plus a disagreement veto.
- Select only by pre-registered criteria on data that is not the frozen set.

**Justification**

- **The seed differences are noise.** At TH34 n=34 and p≈0.68, the binomial SE is 2.7 images. Your seed spread (23.0±1.3) is *smaller* than the eval noise. Ranking seeds on TH34 is ranking noise. Compare candidate models only with paired tests (McNemar) on the same images.
- **Uniform soups over independent seeds are not standard practice.** Model soups (Wortsman et al. 2022) average fine-tunes from a *shared pretrained init* within one loss basin. Independently initialised networks are generally not linearly mode-connected (Frankle et al. 2020; Entezari et al. 2022; Ainsworth et al. 2023, Git Re-Basin).
  - If your seeds share the init and differ only in data order or augmentation, the soup is valid. That would explain why it works at all.
  - If the inits differ, the soup's behaviour is accidental. The non-monotonicity in N (gate 14/0 → 16/3 → 17/1) is consistent with that.
  - Check by plotting the loss along the linear interpolation between two seeds. Recompute BatchNorm statistics after any averaging.
- **EMA is standard for small detectors.** Examples: YOLOv5/YOLOX ModelEMA; Polyak averaging; SWA (Izmailov et al. 2018). It gives most of the soup benefit within one run at zero inference cost.
- **Ensembles (Lakshminarayanan et al. 2017) are the robust choice for a "never wrong" product.** The disagreement veto converts seed variance, which is exactly your 0–4 wrong-accept spread, into rejections.
  - Cost: 2× of a 0.21M model. That is very likely within 100 ms; measure it on your lowest-end target phone.

**Parameters**

- **EMA:**
  - Decay = 0.999 × (1 − exp(−t/300)) for 3000 steps.
  - If you lengthen to 10k steps, use 0.9995.
  - Evaluate the EMA weights only.
- **SWA alternative:** average checkpoints every 100 steps over the final 30% of the schedule, then re-estimate BN statistics on 500 training batches.
- **Ensemble:**
  - Average the sigmoid heat-maps of 2 seeds *before* peak extraction.
  - Veto if the individually decoded readings differ.
  - Keep the locator ensemble at 2 members and the reader ensemble at 2 members.
- **Selection protocol, written down before running:**
  - Choose members by end-to-end reading accuracy on the meter-ID-split validation set (built as described in Q7).
  - Evaluate on the frozen 73 once.
  - Report a 95% CI.

---

## Q6. Training efficiency on 8 CPU cores

**Recommendation:** Spend ~2 hours on profiling and two cheap knobs. Then stop optimising and stop seed sweeps. The bottleneck is data and labels, not compute.

**Justification**

- **You are probably within ~2× of the floor.** Rough budget: a stride-4 tiny CenterNet at 64×448 is about 50–150 MFLOPs forward per image, so ≈5–15 GFLOP per step for forward + backward at batch 32. One Xeon core sustains maybe 10–40 GFLOPS on small, memory-bound convolutions. That gives 0.2–1 s per step; you measure 0.4 s.
- Tiny depthwise or narrow convolutions are memory-bandwidth-bound, so the 4.2× from parallel processes is the main lever, and you already use it.

**Concrete things to try, ranked**

1. **Thread and core hygiene:**
   - Set `OMP_NUM_THREADS=1` and `torch.set_num_threads(1)` per process.
   - Pin with `taskset`.
   - Check whether the 4 "cores" are 2 physical cores with hyperthreading (`lscpu`). If so, run 2 processes, not 4. Each will likely be faster, and total throughput may barely change.
2. **Fuse elementwise operations:** try `torch.compile(model)` (Inductor CPU backend) together with `channels_last`. The typical gain for small conv nets with many BN/ReLU elementwise ops is 1.2–2× (rough estimate, not measured). Profile first with `torch.profiler` to see whether convolution or elementwise time dominates.
3. **Batch scaling:**
   - Measure images/s at batch 32, 64, and 128.
   - If throughput rises over 15%, use batch 64 with LR 3e-4 (sqrt scaling), half the steps, and EMA.
4. **Mixed precision:** skip bf16 unless the CPU has AMX (Sapphire Rapids or newer). You already found it slower.

**Where to spend cores instead:**
- **One longer schedule:** run 10k steps with EMA once. 3000 × 32 at 50% real data is about 47 epochs over 1029 real lines. Longer is plausible but unverified.
- **Ablations:**
  - Synthetic ratio 25% vs. 50%.
  - The segment head.
  - The full-row locator target.
- **No more seed sweeps.** 27/31 seeds already gave you the variance estimate. More seeds buy nothing.

---

## Q7. What makes your numbers untrustworthy

**Recommendation:** Fix the split, freeze the gate before looking at frozen data, and report confidence intervals. Several of your current numbers are biased upward.

**Issues**

1. **Split by photo key, not meter ID.** Multiple photos of the same meter in train and validation is leakage. This is almost certainly why validation IoU50 is 66/68 for every seed.
   - Also check meter or account ID overlap between the *frozen* sets (owner 49, ERP 34) and m3 / ft6 / owner_visual. Owner_visual is weighted ×2 in training. If the owner photographed the same meters for both, the frozen numbers are inflated.
2. **The gate was tuned on the 73 frozen images.** The threshold 0.55 and the "0 wrong" figure were found on the test set. The seed study is the out-of-sample check, and it gives ~1.4 wrong per ~17–20 accepted. Present ~7% selective risk as the current estimate, not 0%.
3. **Adaptive reuse of the frozen set.** Many recipe decisions over 3 days were evaluated on the 49/34. The frozen set is now partly a validation set (Dwork et al. 2015, "The Reusable Holdout"; Recht et al. 2019, "Do ImageNet Classifiers Generalize to ImageNet?").
   - Collect a new frozen set of ≥100 images, from meters never seen, and touch it once per release.
4. **Tiny eval sets reported without intervals.**
   - A 22/39 result has a 95% CI of roughly [40%, 72%].
   - A TH34 per-type cell like 2/7 has a CI of about [4%, 71%].
   - Per-type conclusions from n=4–7 are anecdotes, except where the result is unanimous across 31 seeds, which is informative about the model but not the population.
5. **Wrong validation metric.** Locator IoU50 is the wrong metric when your errors are one-digit edge errors (EXTRA_RIGHT, MISSING_LEFT). Use one of:
   - End-to-end reading accuracy with a fixed reader.
   - Left/right edge error in pitch units, with a threshold of 0.5 pitch.
6. **The locator target embeds an unsolvable decision** (integer-only union on Crystal). This is label noise, not a model weakness (Q2).
7. **Synthetic ratio 50/50 is untuned and the synthetic data is unvalidated.** The fact that Crystal synthetic data changed nothing in 31/31 seeds suggests a domain gap or missing information. Ablate at 25/75 synthetic/real.
8. **"Coverage 23%" has a mixed denominator.** It pools 39 readable and unreadable images across A and B modes.
   - Report coverage separately on readable images and on all images.
   - Report the false-accept rate on unreadable images separately: they are the most dangerous class.
   - Mode A (user rectangle) is the product-relevant mode. Mode B should not drive decisions.
9. **Heat-map peak ≠ probability.** Penalty-reduced Gaussian focal targets make peak values systematically below 1 and dependent on object size. Thresholds like 0.55 or 0.30 do not transfer across retrainings. Recalibrate the gate per deployed model, which is another reason to automate the SGR procedure.
10. **No exchangeability across time or types.** Any guarantee holds only for the calibration distribution. Log every accepted field reading against later ERP truth. Track per-type accepted-error counts and auto-disable acceptance for a type when its Clopper-Pearson lower bound exceeds r\*.
