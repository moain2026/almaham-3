# claude-fable-5-1 — 2026-10-24 04:26 UTC (278s)

# Consultation response — almaham-3

Preliminary blunt statement that conditions everything below: **"0.0 error" is not a verifiable property of this system with your data.** With 17 accepted / 0 wrong, the exact 95% Clopper–Pearson upper bound on the accepted-error rate is 1 − 0.05^(1/17) ≈ **16%**. To certify ≤1% at 95% you need ≥299 accepted with zero wrong (≥459 for 99% confidence); to certify ≤0.5% you need ~600. Everything you decide should be framed as "minimize risk, measure honestly, grow n via field feedback", not "achieve zero".

---

## Q1. Selective prediction gate

**Recommendation:** Do not fit a free-form classifier. Use a monotone AND-rule over ≤4 engineered rejection signals (per-digit *absolute margin*, locator score, digit-count plausibility, and k-of-5 TTA/second-reader string agreement), set the threshold conformally as "strictly above the worst accepted-wrong score on a pooled calibration set", and report Clopper–Pearson bounds. Recalibrate the threshold for every deployed model.

**Justification.**
- Framework: Chow (1970) reject option; Geifman & El-Yaniv (2017) *Selective Classification for Deep Neural Networks* (risk–coverage curve, SR baseline); Geifman et al. (2019) AURC; Hendrycks & Gimpel (2017) MSP baseline. Conformal: Vovk et al. (2005); Angelopoulos & Bates (2021) tutorial; Bates et al. (2021) *Distribution-free, risk-controlling prediction sets*; Angelopoulos et al. (2021) *Learn then Test*. Conformal risk control gives risk ≤ α + B/(n+1); with α→0 you get nothing from n≈70, which is the formal statement of the preliminary point.
- Your own numbers show why the current gate fails: ONE_DIGIT_SWAP cases have min_conf 0.34–0.59 and line_score 0.51–0.74 — indistinguishable from correct readings on those two scalars. CenterNet peak scores under focal loss (Lin et al. 2017) are systematically under-confident and uncalibrated (Guo et al. 2017), and their scale **differs between seeds**, so a 0.55 threshold tuned on reader_ft6m2_s1 means something else on soup5. Any threshold must be re-derived per model.
- Logistic regression: pooled data is ~73 frozen + 97 field ≈ 170 images with maybe 35–45 wrong-or-empty outcomes. Events-per-variable rule (Peduzzi et al. 1996; ~10 EPV) ⇒ ≤4 features, L2-regularized, nested CV. That is feasible but gives you a smooth score whose tail you still cannot validate. The monotone rule is equivalent in practice and auditable. If you fit anything, fit a monotone model (isotonic or sign-constrained logistic).
- The two signals you are not yet using are the ones that address the swap failures:
  1. **Absolute per-digit margin** `score − alt`. `alt < 0.5×score` accepts a 0.40 vs 0.19 digit. For a 5→6 ghost confusion the runner-up (5) typically carries appreciable mass; require `min_d (score_d − alt_d) ≥ 0.25` *and* `alt_d ≤ 0.20` in absolute terms. Measure on the 5 swap cases first.
  2. **Agreement under perturbation** (Ayhan & Berens 2018; Bahat & Shakhnarovich 2020; deep-ensemble disagreement, Lakshminarayanan et al. 2017). Run the reader on 5 variants of the line crop (±6% scale, ±4 px horizontal shift, ±15% gain, one γ change) and require 5/5 identical integer strings; additionally run the locator twice on a jittered user rectangle (±8% of each side) and require the same reading. The "OTHER/wrong line" class (10 cases, line_score 0.30–0.58) is exactly the one that is unstable under rectangle jitter. Cost: reader at 64×448 with 0.21M params is ~3–10 ms on a mid-range ARM core; 5 passes fit the budget.
  3. **Digit-count plausibility**: from the 1,143 verified labels, build the empirical set of integer-string lengths (overall, and per type if a type classifier exists). Reject any length with empirical frequency < 1%. This alone catches many EXTRA_RIGHT / MISSING_LEFT cases with zero model risk.
- Lattice regularity and height-ratio variance are weak on your taxonomy (EXTRA_RIGHT on Crystal has regular pitch and equal height) — include only as a hard-reject for CV(pitch) > 0.12.

**Concrete protocol.**
1. Pool frozen-49B, TH34, and the 97 field photos into a calibration set **C** (after confirming the field photos' meters are not in training; see Q7).
2. For each candidate model, compute the rule features for every image; define the acceptance region as: `all margins ≥ τ_m` ∧ `line_score ≥ τ_L` ∧ `length ∈ L_ok` ∧ `TTA 5/5` ∧ `rect-jitter agree`.
3. Set (τ_m, τ_L) by conformal exclusion: τ_m = max margin over *wrong* examples in C that pass the other hard rules, plus 0.02; same for τ_L. This is the split-conformal quantile at the extreme; it is the most honest thing you can do with n≈40 wrong examples.
4. Report: coverage (accepted/total), wrong-accepted count, Clopper–Pearson 95% upper bound, and the full risk–coverage curve, not a single point. Expect something like coverage 30–40% at 0 wrong on C; the honest upper bound will still be ~5–8%.
5. Leave-one-out the threshold-setting step to estimate how much coverage you lose when the worst wrong example is unseen — this quantifies fragility.
6. Field loop: every accepted reading the user confirms/corrects goes into C. You need ~300+ accepted confirmations before the error-rate claim means anything. Build that pipe now.

---

## Q2. Integer/fraction boundary (Crystal-like)

**Recommendation, ranked:** (1) native-resolution dot verifier on inter-digit gaps (a local variant of your option c), (2) option (a) 12th class as a *vote* with the locator's right edge, (3) option (e) as a *reject-only* prior, (4) option (d) as an independent second reader for agreement, (5) option (b) last. If, after (1), the dot is confirmed to be ≤1 px *in the native photo*, abstain on all Crystal readings with ≥7 digits — no architecture can recover information that is not in the pixels.

**Detail.**

| Option | Expected gain | Confident-error risk | Data | CPU |
|---|---|---|---|---|
| (c') Gap dot-verifier at native res: for each consecutive digit pair, crop the gap at native resolution (e.g., 32×32 centred on the gap, height = digit height), tiny 4-layer CNN → P(dot). Use as boundary when P≥0.9, reject reading when 0.3<P<0.9 for any gap | Highest for Crystal **if** native dot ≥2 px; also helps Tomas/Other dot cases (peaks 0.07–0.29 today) | Low–medium: a false dot is a confident wrong boundary, so require margin ≥0.6 between best and second-best gap | 98+74 Crystal + all other real lines (dot position derivable from label length + lattice); synthetic dots rendered at native scale | ≈5 gaps × ~0.3 MFLOPs — negligible |
| (c) full 2× reader (128×896) | Same information as (c'), plus slightly better digits | Same | Same | 4× reader FLOPs (likely 40–80 ms on low-end phones) → budget risk. Only as a conditional second pass when no dot found |
| (a) 12th class "last integer digit" | Moderate on types with any visible cue (dot, colour field, larger gap); **near zero on Crystal unless a cue exists** — a CNN cannot see what a geometry rule cannot | Medium–high: with ~1k real lines it will learn "6th digit from left" positional priors — exactly the systematic error the previous consultation rejected | Needs per-digit boxes: ft6 (498) directly; m3 and the 612 via lattice-from-label | ~0 |
| (e) type classifier → P(K\|type) | Useful only where the label-length distribution per type is near-deterministic (check: if 100% of TOMAS labels are 6 digits, prior is strong; Crystal has no leading zeros ⇒ weak prior ⇒ no help where you need it) | High if used to *choose*; low if used only to *reject* (K ∉ observed lengths for predicted type, type confidence ≥0.9) | 1,143 labels, type labels exist | small classifier on 256×256 crop, ~2 ms |
| (d) CRNN+CTC (Shi et al. 2016) with dot token | As a primary reader: low — CTC must still see the dot; BiLSTM context learns positional priors from 1k samples; CTC readers hallucinate plausible strings and give poor per-character confidence | High as primary; low as a *second opinion* (heterogeneous ensemble ⇒ decorrelated errors; Gómez et al. 2018 *Cutting Sayre's Knot* read utility meters this way) | Same real lines + synth | 32×W CRNN ~0.5M params, 5–10 ms |
| (b) 1-D boundary regressor | Lowest: regression to the mean, no uncertainty, same information problem | High | — | ~0 |

Two cheap measurements before building anything: (i) on the 98+74 Crystal images, measure the dot's native pixel size and the gap between 6th and 7th digits vs median pitch — if the integer/fraction gap is ≥1.2× pitch it's a usable rule; (ii) check whether the *locator* box right edge (it is trained on the integer union) already separates: a digit whose centre lies > 0.4 pitch beyond the locator right edge is likely fraction. At 256×256/stride-4 the locator's wh error is ~±half a digit, so this is a feature for the gate, not a decision.

Also note the current Crystal synthetic set is likely **harmful**: if the rendered dot is ~1 px and invisible to the network, the labels teach it to place the boundary from position alone — that is a positional prior by construction, and it is consistent with EXTRA_RIGHT appearing with min_conf up to 0.53.

---

## Q3. The 612 photos with readings but no line box

**Recommendation:** Manually box them (option iv) — all 612, line box plus the integer/fraction split — and derive per-digit boxes from label length + equal-pitch lattice, refined by a high-recall reader pass. Budget ~2 hours of a labeller. Do not use (i)–(iii) as the primary route.

**Justification.**
- The weak labeller is `reader over sliding windows, accept if string == label`. It failed on these 612 ⇒ **the reader cannot read them anywhere in the image.** Any method that verifies via reader output (options i and iii) can only recover images the current reader already handles — classic confirmation bias of self-training (Xie et al. 2020 Noisy Student; Sohn et al. 2020 STAC; Liu et al. 2021 Unbiased Teacher all rely on a teacher that is already right). The recovered subset is biased toward easy; the hard tail stays unlabelled. Lowering the acceptance threshold or widening windows (i) adds box-extent noise (windows that match the string but cut digits) and partial-string false matches.
- Composition of the 612 — TOMAS 176, SMART_YELLOW 96, CRYSTAL 74 — is precisely your TH34 failure types (SMART_YELLOW 2/6, CRYSTAL 2/7). This is the highest-value data you own; it is cheaper to label than one day of the 27-seed sweep.
- (ii) MIL / transcription-only supervision exists (WSDDN, Bilen & Vedaldi 2016; Kittenplon et al. 2022 *TTS*; Peng et al. 2022 *SPTS*) but is engineered for large data and strong recognizers; with 612 images and a weak reader it degenerates (peaks on background text, price labels, meter serial numbers — which also match digit strings).

**Procedure.** One rectangle around the integer digits + one click on the first fraction digit (or "none"). Then: digit centres = lattice from N = len(label) across the box; run the reader with threshold 0.1 and snap each centre to the nearest detection within 0.4 pitch; flag images where snapping fails for visual check (expect 10–20%). Record meter id (or photo cluster) for every image to enable a proper split (Q7). Also label the fraction digits (class or flag) — they are needed for Q2 regardless of which option you pick.

---

## Q4. Ghost-segment confusions

**Recommendation:** Add a 7-segment-state auxiliary head (7 sigmoid channels at each digit centre), feed a local-contrast-normalized input, and render synthetic off-segments with ghost alpha ∈ [0, 0.45] and on-segments with weakened alpha ∈ [0.55, 1]; use class↔segment-code disagreement as a hard reject.

**Justification.**
- Your confusions decompose into two physical causes: *ghost on* (5→6 needs e; 9→8 needs e; 9→0 needs e on and g weak) and *weak on* (7→1 is a missed segment a; 2↔3 needs c/e trade). A holistic class head trained with focal loss has no explicit notion of "segment e is 20% as dark as segment g"; it learns shape templates. A segment head makes the decision explicitly relative. Multi-task structural supervision of this kind is standard (Caruana 1997); for text, character-structure auxiliary targets (e.g., stroke/segmentation maps in Liao et al. 2019 *Mask TextSpotter v3*) consistently help low-data recognition.
- Decoding: segment code → class is deterministic except glyph variants (6 with/without a, 7 with/without f, 9 with/without d). Treat those segments as don't-care in the segment loss and in decoding. Reject when the decoded code is not a valid digit or disagrees with the class head.
- Contrast normalization: on LCDs, ghosting is a *relative* intensity (off segments typically 10–30% of on contrast under polarizer/angle). Per-crop percentile normalization (map 2nd/98th percentiles to 0/1) or CLAHE (clip 2.0, 8×8) stabilizes that ratio across exposure. Cheap: do it in the preprocess and in training.
- Synthetic hard negatives: render each digit with every off segment drawn at alpha ~ U(0, 0.45) (independently per segment, same hue as on segments) and on segments at alpha ~ U(0.55, 1.0); oversample the six confusable pairs 3×. This is domain randomization (Tobin et al. 2017; Jaderberg et al. 2014 for text) targeted at the failure mode. Your current synth apparently renders clean on/off, which is why real ghosting is out-of-distribution.
- Type-conditioned augmentation: low priority; ghost alpha randomization covers it.
- Real data: the 176 TOMAS images in the 612 set are the real ghosting distribution. Nothing substitutes for them.

**Literature:** Meter-reading papers with public datasets — Laroca et al. 2019 (UFPR-AMR), Laroca et al. 2021 (Copel-AMR, unconstrained), Salomon et al. 2020 (dial meters), Gómez et al. 2018 (segmentation-free reading), Kanagarathinam & Sekar 2019 (seven-segment energy meters, Energy Reports) — report counter/digit accuracy but **none isolates LCD ghosting as a failure class with controlled results; a published quantitative treatment of ghost-segment confusion in seven-segment OCR is unknown to me.** Treat the segment-head approach as engineering practice, not a cited result.

---

## Q5. Model selection with noisy tiny eval

**Recommendation:** Stop selecting among seeds on TH34/49 — the spread is below sampling noise. Use weight-EMA during training (free), select on a new sealed validation set built from the 612 labelled images (split by meter id), deploy a 2-model agreement pair if the budget permits, and recalibrate the gate per deployed model.

**Justification.**
- TH34 at ~68% correct has binomial SD ≈ √(34·0.68·0.32) ≈ **2.7 images**. Your seed SD is 1.3. Picking the best of 27 seeds on this set is picking noise; the expected winner's-curse inflation is ~+2 SD ≈ 2–3 images. The same applies to 49A/B (SD ≈ 3.0). Per-type counts (n = 4–7) carry essentially no information: 2/7 vs 3/7 is not a result.
- The frozen set has been evaluated hundreds of times (27 seeds × readers × soups × gate variants). It is no longer a test set; it is a validation set with adaptive reuse (Dwork et al. 2015 *reusable holdout*; Recht et al. 2019). Any number reported from it is optimistic.
- Weight averaging: uniform soups (Wortsman et al. 2022) require models fine-tuned from a shared initialization in one loss basin. Independently initialized scratch-trained seeds are not linearly mode-connected (Frankle et al. 2020) without permutation alignment (Ainsworth et al. 2022, Git Re-Basin). Your non-monotone soup results are consistent with this. Use SWA along a single trajectory (Izmailov et al. 2018) or EMA (decay 0.999–0.9998 at 3000 steps) — EMA is standard in detector training (used in YOLO/EfficientDet codebases) and reliably reduces variance at zero inference cost.
- Inference ensembling (Lakshminarayanan et al. 2017): 2× cost is affordable for a 0.21M-param reader. Its value for you is less accuracy than **disagreement = reject**, which plugs into Q1 directly. Prefer a heterogeneous pair (CenterNet reader + segment-code decoder or small CRNN) over two seeds of the same architecture: errors are more decorrelated. If you want single-model inference, distill the 27-seed heat-map ensemble into one student (Hinton et al. 2015) — the soft heat-maps are natural targets.

**Protocol.** (1) Seal a new test set: ≥150 images from the 612, stratified by type, meters disjoint from training; touch it once per release. (2) Select on the remaining ~460 as validation. (3) Report frozen-73 numbers only as legacy, with the caveat that they are contaminated.

---

## Q6. Training efficiency on 8 CPU cores

**Recommendation:** You are near the per-core floor; try channels_last + torch.compile (expect 1.2–1.5×), replace any depthwise convolutions with plain convs, use progressive resizing for the first 60% of steps (~1.6× overall), and stop spending cores on seeds — the seed variance is noise and more seeds cannot buy information.

**Justification with numbers.**
- Rough FLOP estimate: a 0.21M-param stride-4 net at 64×448 is ~0.1–0.2 GFLOPs forward/image; ×3 for backward, ×32 batch ≈ 10–20 GFLOPs/step. A single Xeon core at realistic 20–40% of fp32 AVX2/AVX-512 peak delivers 20–40 GFLOP/s ⇒ 0.3–0.7 s/step. Your 0.4 s is already in that range; there is no 5× lying around.
- channels_last with oneDNN: 10–30% on conv nets; torch.compile (inductor, CPU backend): 1.2–1.5× on small nets, with ~1–2 min compile. bf16 autocast is only fast with AVX512-BF16/AMX (Sapphire Rapids); your observation that it is slower means this Xeon lacks it — drop it.
- Depthwise/grouped convs are notoriously slow in CPU training (poor oneDNN kernels for backward); if the backbone uses them, plain 3×3 convs with fewer channels will likely be faster per step at equal params.
- Progressive resizing (fast.ai; Touvron et al. 2019 *FixRes*): train at 48×336 for steps 0–1800, then 64×448 — ~1.7× speedup on the first phase, negligible accuracy cost for a fully convolutional net with a scale-augmented pipeline.
- Larger batch / fewer steps: with ~1k real lines, 3000×32 = 96k samples ≈ 90 real epochs. Reducing steps is where accuracy would actually drop; increasing batch gives no throughput gain on one core. Leave it.
- Multi-thread one run across 4 cores: scaling for small convs is ~2.5–3× ⇒ *lower* aggregate throughput than 4 single-core runs. Keep 1 core/run.
- The real inefficiency is strategic: 3 days × 8 cores produced 58 seeds whose spread is below eval noise. One day of that compute spent on the segment head, the dot verifier, and EMA — on a dataset enlarged by the 612 — would be worth more than another 100 seeds.

---

## Q7. Practices that make your numbers untrustworthy

1. **Split by photo key, not meter id.** The same meter photographed repeatedly straddles train/val. Your m3 val saturating at 66/68 for *every* seed is the symptom. Also the owner's photos: "owner_visual ×2 weight" in training plus 49 owner photos as frozen eval implies the owner's own meters are in both — probable leakage into the "frozen" set. Verify and purge.
2. **The frozen 73 are burned.** Hundreds of adaptive evaluations, plus the gate thresholds were tuned on the same images whose 17/0 you report. Those are validation numbers, not test numbers, and the Clopper–Pearson bound on top of them (16%) is itself optimistic.
3. **Per-type conclusions from n = 4–7** (CRYSTAL 2/7 "in 31/31 seeds") are statistically meaningless as evidence that synth "moved nothing" — though in this case the root-cause analysis independently supports the conclusion.
4. **Synthetic Crystal with an invisible dot** teaches a positional prior for the boundary. That is not neutral; it is a plausible generator of confident EXTRA_RIGHT errors. Either render the dot at a visible size matched to the native-resolution distribution you measure, or drop boundary supervision from those samples.
5. **50/50 real/synth** is arbitrary and the synth distribution (clean segments, no ghosting) differs from the failure modes. Standard practice is synth pretrain → real-heavy fine-tune, or a real-weighted mix (Jaderberg et al. 2014 used synthetic-only for a different regime; for small real sets, fine-tuning on real dominates). Ablate 50/50 vs 80/20 vs pretrain+finetune on the new validation set.
6. **Weak-labeller selection bias.** Training data contains only lines the previous reader could already read. The 612 excluded images are the hard tail; the model has literally never seen its own failure distribution.
7. **Gate thresholds are model-specific.** Heat-map peak scales shift across seeds/soups; a 0.55 threshold tuned on one model is undefined on another. Any deployment swap requires recalibration on C.
8. **Human label noise on the boundary** (which digits are "integer") is unquantified. Even a 2% inter-annotator disagreement on 1,143 readings is comparable to the error budget you are chasing. Double-annotate a 100-image sample.
9. **Letterbox 64×448 (7:1)** wastes resolution for 5–6 digit lines (typical 3:1–5:1), halving effective digit height for short lines. A width-proportional canvas or 64×320 default with 64×448 only when needed would give the dot and ghost segments more pixels for free.
10. **Reporting.** Report risk–coverage curves with intervals, not point accuracies; state n on every number; keep one test set sealed per release.
