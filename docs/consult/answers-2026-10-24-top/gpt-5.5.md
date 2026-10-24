# gpt-5.5 — 2026-10-24 04:25 UTC (218s)

## 1. Selective prediction gate

**Recommendation:** use a fixed, low-dimensional selective-classification gate with threshold calibrated on an independent calibration set; do not trust a free logistic model trained and evaluated on the same ~73 images, and do not claim “0.0 error” statistically from 17/0.

### Justification

This is a classic **reject-option / selective classification** problem: output a label only when the estimated risk is low. See Chow’s reject rule (Chow, 1970), selective classification by El-Yaniv and Wiener (2010), Geifman and El-Yaniv (2017), and confidence/calibration work by Guo et al. (2017). Conformal methods are useful, but ordinary conformal prediction gives coverage of the true label in a set; here you want **risk control among singleton outputs**. The relevant family is closer to **risk-controlling prediction sets / learn-then-test** (Bates et al., 2021; Angelopoulos et al., 2021) or a binomial upper-bound audit.

With only 73 frozen images, 68 held-out images, and 97 field-feedback images, you cannot statistically certify near-zero error. For example:

- Current strict gate: 17 accepted, 0 wrong.
- One-sided 95% Clopper-Pearson upper bound for accepted-error rate:

\[
U = 1 - 0.05^{1/n}
\]

For `n=17`, `U ≈ 16.2%`.  
Two-sided 95% upper bound is about `19.5%`.

Approximate required zero-error accepted counts:

| Desired upper bound on accepted-error rate | Zero-error accepted samples needed, 95% one-sided |
|---:|---:|
| 5% | 59 |
| 2% | 149 |
| 1% | 299 |
| 0.5% | 598 |
| 0.1% | 2995 |

So “17 accepted / 0 wrong” is a useful engineering signal, not a statistical proof of zero error. Clopper and Pearson (1934) is the standard exact interval reference.

### Concrete gate construction

Use two layers:

#### A. Hard reject predicates

Start with a deliberately conservative rule. Initial thresholds I would test:

```text
status == OK
locator_line_score >= 0.55
min_digit_score >= 0.60
max_alt_ratio = max(alt / score) <= 0.35
pitch_cv <= 0.10
max_gap_over_pitch <= 1.35
height_cv <= 0.15
no unresolved boundary ambiguity
TTA exact agreement
```

Where:

- `alt / score` should be computed per digit after cross-class NMS.
- For known confusing pairs `{5,6}`, `{9,0}`, `{9,8}`, `{2,3}`, `{7,1}`, use stricter:

```text
alt / score <= 0.25
```

because your observed one-digit swaps have `line_score 0.51–0.74` and `min_conf 0.34–0.59`, i.e. they are not separable by locator score alone.

Boundary-specific hard reject:

```text
if boundary_source in {"height", "lattice"} and no visible dot and no learned integer-boundary cue:
    reject
```

This will lower Crystal coverage, but it is appropriate until you add a learned boundary signal. Your own root-cause analysis says geometry cannot solve same-height fractions with invisible dots.

#### B. Optional learned risk score, but only for ranking

A small logistic model is acceptable **only as a ranking model**, not as a trusted calibrated probability, and only if the threshold is chosen on separate calibration data.

Features I would use, capped at ~8 to avoid overfitting:

```text
1. min_digit_score
2. p10_digit_score or mean_digit_score
3. max_alt_ratio
4. min_margin_abs = min(score - alt)
5. locator_line_score
6. pitch_cv
7. boundary_source categorical: dot / height / lattice / none
8. TTA_agree_count or exact_agreement flag
```

Optional:

```text
9. confusable_pair_flag
10. right_extra_peak_score
11. n_digits
```

Use L2-regularized logistic regression, Firth logistic regression, or isotonic regression on a single hand-designed score. Do **not** fit a larger model, random forest, XGBoost, or neural calibrator on this amount of data.

A reasonable scalar hand score is:

```text
badness =
    1.5 * max(0, 0.60 - min_digit_score)
  + 1.0 * max(0, 0.55 - locator_line_score)
  + 1.5 * max(0, max_alt_ratio - 0.35)
  + 1.0 * max(0, pitch_cv - 0.10)
  + 2.0 * boundary_ambiguous
  + 3.0 * tta_disagreement
  + 1.0 * confusable_pair_weak_margin
```

Then accept only if `badness == 0` or `badness <= τ`, where `τ` is chosen on calibration data.

### TTA agreement

Use TTA mainly as a **disagreement detector**, not to average confidence.

Suggested TTA set:

```text
T0: original
T1: line crop x-shift +2%
T2: line crop x-shift -2%
T3: scale 1.03
T4: scale 0.97
```

Accept only if:

```text
all 5 decoded strings identical
all 5 lengths identical
max Levenshtein distance = 0
min over TTAs of min_digit_score >= 0.55
max over TTAs of max_alt_ratio <= 0.40
```

If 5x reader cost is too high, use 3 TTAs: original, +x-shift, -x-shift.

### Honest validation plan

Do not tune on the 49 owner + 34 TH34 set anymore if you want to call it frozen. It has already been used for model selection and error taxonomy.

Minimum defensible procedure:

1. Freeze detector weights.
2. Freeze gate feature definitions.
3. Use one calibration set to choose thresholds.
4. Evaluate once on a new blind set.

Report:

```text
coverage = accepted / total
wrong-output rate among accepted = wrong / accepted
wrong-output rate per input = wrong / total
Clopper-Pearson upper bound for wrong / accepted
Clopper-Pearson upper bound for wrong / total
type-stratified results
```

If you must use the current data, use blocked cross-validation by meter ID or at least by photo source/type, but label it as development validation, not final evidence.

---

## 2. Integer/fraction boundary for Crystal-like displays

**Recommendation:** first add a learned integer-boundary signal, preferably a “last integer digit” heat-map class; use 2× resolution as a secondary cascade for no-dot cases; do not rely on meter type or fixed digit count.

### Ranking

#### 1. Add a 12th heat-map class: `LAST_INTEGER_DIGIT`

**Expected gain:** high for `EXTRA_RIGHT`, especially Crystal.  
**Risk of confident errors:** moderate, controllable by gating.  
**Data needed:** ~200–500 real line crops with boundary labels; start with all Crystal/Tomas/Smart failed cases.  
**CPU cost:** negligible.

This is the best first option because it fits your existing CenterNet-style detector. You already have digit centers and heat-map machinery. Add one extra class whose positive center is the last integer digit. At inference:

```text
boundary_x = x_center(last_integer_digit) + 0.5 * estimated_pitch
```

Accept the learned boundary only if:

```text
last_integer_score >= 0.60
TTA boundary std <= 0.03 * line_width
boundary agrees with dot/height cue if such cue exists
no second last-integer peak within 0.75 pitch with score >= 0.5 * best
```

For no-dot same-height Crystal, this gives the network a supervised semantic boundary cue that geometry lacks.

Expected practical effect: likely remove most `EXTRA_RIGHT` failures. You reported 6 `EXTRA_RIGHT`, 4 Crystal. This head should directly target those. It may move Crystal from `2/7` toward something like `4–6/7` on TH34 if localization is not the limiting factor. Exact gain unknown without annotation.

#### 2. Per-line 1-D boundary regressor head

**Expected gain:** medium-high.  
**Risk of confident errors:** higher than the heat-map class because scalar regressors can look precise while being wrong.  
**Data needed:** ~200–500 real line crops with boundary `x`.  
**CPU cost:** negligible.

Add a small head predicting normalized boundary position:

```text
b ∈ [0, 1]
loss = SmoothL1(b_pred, b_true)
```

Better: predict both mean and uncertainty:

```text
loss = |b - μ| / σ + log σ
```

Reject if:

```text
σ > 0.03
or TTA std(b_pred) > 0.03 * line_width
```

This is useful as an auxiliary signal, but I would not use it alone. Combine with the `LAST_INTEGER_DIGIT` heat-map:

```text
accept boundary if heat-map boundary and regressor boundary differ <= 0.35 pitch
else reject
```

#### 3. Read at 2× resolution: `128×896`

**Expected gain:** medium if the dot is physically present but lost during downsampling; low if the dot is absent or invisible in the source.  
**Risk of confident errors:** low-to-medium.  
**Data needed:** retrain reader at 2×; ideally include real Crystal crops.  
**CPU cost:** roughly 4× reader convolution cost.

Your root-cause note says the dot is `≤1 px after downscale` with peak `0.07–0.29`, below threshold. A 2× reader may make the dot recoverable. But if the dot is optically absent or the LCD has same-height fractions with no clear dot, resolution will not solve the semantic boundary.

Do not run 2× for every image unless target-device timing allows it. Use a cascade:

```text
run normal reader
if boundary_source == dot and dot_score >= 0.30:
    use normal result
else:
    run high-res boundary/dot reader
```

Expected cost:

```text
64×448 reader cost = 1×
128×896 reader cost ≈ 4×
cascade mean cost = 1× + p_ambiguous * 4×
```

If ambiguous cases are 20–30%, mean cost is about `1.8–2.2× reader`, not `4×`.

#### 4. Sequence model with CTC and boundary token

**Expected gain:** uncertain.  
**Risk of confident errors:** medium-high with your current data.  
**Data needed:** probably `1000+` real or high-quality labelled line crops; ideally full visible transcription including fractional digits and an `<INT_END>` token.  
**CPU cost:** variable; small CRNN can be mobile-feasible but more complex than your detector.

A CTC model can output:

```text
0 0 7 0 2 2 <INT_END> 4 5
```

References: Graves et al. (2006) for CTC; Shi et al. (2016) for CRNN text recognition.

But if labels contain only the integer part while the image includes fractional digits, training becomes ambiguous. The model may learn to treat fraction digits as blanks, which can fail confidently. I would not switch to CTC before fixing the detector-boundary formulation.

#### 5. Meter-type classifier → digit-count prior

**Expected gain:** low for the specific Crystal problem.  
**Risk of confident systematic errors:** high.  
**Data needed:** ~50–100 images per type minimum, but that is not the main issue.  
**CPU cost:** small.

You already have a rejection of fixed digit count, and I agree. Type errors are systematic, and Crystal has no safe leading-zero rule. Use type only as a rejector:

```text
if type posterior < 0.80:
    do not apply type prior

if type posterior >= 0.95 and predicted digit count is outside historically observed range:
    reject, do not auto-correct
```

Do not use type to force truncation.

---

## 3. Using the 612 photos with known readings but no line boxes

**Recommendation:** manually annotate line boxes and integer-boundary points for the 612; use weak localization only to pre-fill annotation, not as the primary training signal.

### Justification

The weak-labeller already failed on these images. That means they are exactly the cases where automatic localization is least reliable. Training on automatically guessed boxes from these images risks confirmation bias and poisoning.

Self-training and pseudo-labelling are known to suffer from confirmation bias when the model’s own high-confidence mistakes are recycled as labels. See Yarowsky (1995), Lee (2013), and Arazo et al. (2020). MIL can work, but it is fragile here because the reader is already imperfect and the image may contain serial numbers, labels, LCD icons, or repeated digit strings. Classic MIL references include Maron and Lozano-Pérez (1998) and Andrews et al. (2002).

612 boxes is not a large annotation job. It is probably higher ROI than another week of seed training.

### Concrete annotation plan

For each of the 612 images, annotate:

```text
1. line bounding box
2. integer/fraction boundary x, or last integer digit index
3. meter type
4. readable / unreadable flag
5. optional: visible fraction digits yes/no
6. optional: dot visible yes/no
```

If you build a small annotation UI with current locator proposals preloaded:

- line box only: likely `5–15 s/image`
- line box + boundary: likely `10–25 s/image`
- full digit boxes: likely `30–90 s/image`

For 612 images:

```text
line box + boundary ≈ 2–5 hours of focused annotation
full digit boxes ≈ 5–15 hours
```

That is cheap compared with the cost of debugging poisoned pseudo-labels.

### Ranking of your options

#### Best: iv. Manual boxes

Most reliable. Also fixes the main missing supervision: Crystal/Tomas/Smart boundary and localization.

Use these 612 not just for locator training, but also to create a harder validation split by meter ID/type.

#### Second: iii. Pseudo-label with current locator and accept only when reader output == label

Useful, but only with very strict acceptance.

Suggested auto-accept rule:

```text
reader_string == human_label
5/5 TTA exact agreement
locator_line_score >= 0.60
min_digit_score >= 0.65
max_alt_ratio <= 0.30
single matching candidate among top K windows
candidate line boxes from two methods IoU >= 0.70
```

Then audit at least:

```text
20% random sample per meter type
100% of Crystal-like no-dot cases
100% of cases with multiple matching candidates
```

Use pseudo-labels with reduced loss weight:

```text
pseudo box weight = 0.25–0.50
manual box weight = 1.0
```

#### Third: i. Widen weak-labeller

Good as a proposal generator, dangerous as an automatic labeller.

Use:

```text
multi-scale windows: line heights 32, 48, 64, 80, 96 px equivalent
horizontal stride: 5–10% of window width
vertical stride: 10–20% of window height
reader threshold lowered for proposal generation only
top K = 10–20 proposals shown to annotator
```

Do not auto-accept low-threshold matches unless they pass the strict pseudo-label rule above.

Pitfall: exact string match is not enough when many windows are searched. Multiple testing makes false matches more likely, especially for short readings or repeated digits.

#### Last: ii. MIL / reading-consistency loss

I would avoid this until you have a better reader and a clean validation set.

If you try it:

```text
freeze reader first
generate K candidate line boxes per image
choose latent box only if exactly one candidate matches label
do not backprop through the reader initially
use EM-style training with manual audit
```

Do not train locator and reader end-to-end from image-level readings at this stage. The failure modes are too systematic.

---

## 4. Ghost-segment confusions

**Recommendation:** add ghost-specific synthetic augmentation, hard-negative mining, and a seven-segment auxiliary task; also tighten pair-specific rejection thresholds for `{5,6}`, `{9,0}`, `{9,8}`, `{2,3}`, `{7,1}`.

### Justification

Your difficult swaps are exactly seven-segment Hamming-neighbor confusions. These are not ordinary digit OCR errors; they are segment-state errors under low contrast or visible off-segments.

I do not know of a strong public paper that specifically reports controlled improvements for LCD seven-segment OCR under visible off-segment ghosting. Most published automatic meter-reading papers are dataset-specific and do not isolate this failure. The standard tools are from broader CV/OCR practice:

- hard example mining: Sung and Poggio (1998), Shrivastava et al. (2016, OHEM)
- focal loss for hard examples: Lin et al. (2017)
- synthetic domain randomization: Tobin et al. (2017), Tremblay et al. (2018)
- multitask auxiliary supervision: Caruana (1997), Ruder (2017)
- local contrast normalization / CLAHE: Zuiderveld (1994)

### Concrete changes

#### A. Ghost-specific synthetic renderer

Your previous Crystal synthetic did not help, likely because it did not model the discriminative nuisance: off-segment visibility and active/off contrast distribution.

Render seven-segment digits with explicit active/off intensity distributions.

Example normalized intensity model:

```text
background B ~ Uniform(0.25, 0.75)

active segment contrast A:
    A ~ Uniform(0.45, 1.00)

off segment contrast O:
    with p=0.50: O = 0
    with p=0.30: O ~ Uniform(0.05, 0.25)
    with p=0.20: O ~ Uniform(0.25, 0.60)   # hard ghosts

active dropout:
    multiply active segment by Uniform(0.60, 1.00)

blur:
    sigma ~ Uniform(0, 1.2 px)

JPEG:
    quality ~ Uniform(25, 90)

glare / LCD gradient:
    low-frequency additive field amplitude 0–0.25
```

Oversample confusing pairs by `3–5×`:

```text
5 vs 6
9 vs 0
9 vs 8
2 vs 3
7 vs 1
```

For each pair, generate borderline examples where the distinguishing segment has active/off contrast ratio near 1.

#### B. Segment-level auxiliary head

Add a seven-segment state prediction auxiliary loss.

For each detected digit center, predict:

```text
7 binary logits: segment_on[0:7]
```

Targets are derived from the digit label, so no extra annotation is needed.

Loss:

```text
L_total = L_centernet + λ_seg * BCE(segment_logits, segment_targets)
λ_seg = 0.2–0.5 initially
```

Use this only as auxiliary supervision, not as the sole classifier. At inference, use it as another ambiguity signal:

```text
digit_class = 9
segment_head says pattern closer to 8 or 0
=> reject if class/segment disagreement
```

For style variants:

- Some `7` digits may have or lack a middle/top style depending on display.
- Some `1` digits are narrow.
- Allow variant templates or ignore uncertain segments for those types.

#### C. Pair-specific margin gate

Your current gate:

```text
alt < 0.5 * score
```

is too weak for Hamming-neighbor pairs.

Use:

```text
if top1/top2 in confusable_pairs:
    require alt / score <= 0.25
    and score - alt >= 0.20
else:
    require alt / score <= 0.35
```

Because CenterNet heat-map scores are not calibrated class probabilities, use these as empirical thresholds, calibrated on held-out data.

#### D. Contrast-normalized input

Try a 2-channel reader input:

```text
channel 1: original grayscale
channel 2: locally normalized grayscale
```

Local normalization:

```text
I_norm = clip((I - P10_local) / (P90_local - P10_local + eps), 0, 1)
```

or CLAHE with conservative clipping:

```text
clipLimit = 2.0
tileGridSize = 8×8 or 4×4 depending on crop size
```

But be careful: CLAHE can amplify ghost segments. Evaluate specifically on the five ghost-pair categories.

#### E. Real hard-negative mining

Create a hard set from your observed mistakes:

```text
all false 5/6, 9/0/8, 2/3, 7/1
near misses where alt/score > 0.25
all images rejected due to TTA disagreement
```

Oversample those real cases by `4×` during fine-tuning for `500–1000` steps with lower LR:

```text
lr = 5e-5 to 1e-4
real:synth = 75:25
```

Do not let synthetic dominate this fine-tune.

---

## 5. Model selection with noisy tiny eval sets

**Recommendation:** stop choosing seeds by the 73 frozen images; use EMA/SWA within a run, prefer two-seed agreement if runtime allows, and select by a new hard validation set stratified by meter ID/type.

### Justification

Differences like TH34 `21/34` vs `25/34` are not reliable with `n=34`, especially after trying 27 seeds. This is winner’s curse / multiple comparisons. Selecting the best seed on the frozen set will overstate future performance.

Weight averaging can help, but your results show cross-seed uniform soups are non-monotone:

```text
soup5  -> gate 14/0
soup10 -> gate 16/3
soup27 -> gate 17/1
```

That is expected. Model soups work best when models are in the same basin, often fine-tuned from the same pretrained initialization (Wortsman et al., 2022). From-scratch tiny detectors with different seeds may not average cleanly.

Standard practice for small detectors is:

- EMA of weights during training.
- Sometimes SWA over late checkpoints from the **same run**.
- Ensembles if latency allows.
- Do not cherry-pick by a tiny final set.

References: Polyak and Juditsky (1992) for averaging; Izmailov et al. (2018) for SWA; Wortsman et al. (2022) for model soups. EMA is standard in modern detectors including YOLO-style training, though often reported as engineering practice rather than a separate paper.

### Concrete deployment options

#### A. EMA per seed

During training maintain:

```text
ema_decay = 0.999
start EMA after 10–20% of steps
evaluate EMA weights, not raw final weights
```

For 3000 steps:

```text
start EMA at step 500
decay 0.999 or 0.9995
```

#### B. Same-run SWA

Save checkpoints from the last training phase:

```text
steps: 2000, 2250, 2500, 2750, 3000
average weights within the same seed
```

Do not average all 27 seeds unless a separate validation set proves it helps.

#### C. Two-seed agreement

If 2× inference cost is acceptable, this is attractive for selective prediction.

Run two independently trained readers, maybe same locator or two locators. Accept only if:

```text
decoded strings identical
digit count identical
line boxes IoU >= 0.70
per-digit centers differ <= 0.25 pitch
both pass individual confidence gates
```

This will reduce coverage but should reduce seed-specific ghost and localization errors. It is often better for “no wrong outputs” than averaging heat-maps, because disagreement is directly useful for rejection.

If you ensemble by averaging:

```text
average pre-sigmoid heat-map logits
average wh/off heads
then decode once
```

But for selective prediction, I would still keep a disagreement feature.

#### D. Model selection protocol

Create a hard validation set from the 612 newly annotated images:

```text
split by meter ID, not photo key
type-balanced
include Crystal no-dot cases
include Tomas/Smart/Yellow
include known ghost examples
```

Then select by:

```text
primary: wrong accepted = 0 under fixed gate
secondary: maximum coverage
tertiary: exact read accuracy before gate
```

Use the 49/34 only for final reporting if you can honestly stop tuning on them. Otherwise declare them development sets and collect a new blind test.

---

## 6. Training efficiency on 8 CPU cores

**Recommendation:** do not spend much effort micro-optimizing; your throughput is already plausible for CPU training of small convnets, and the better use of 8 cores is parallel seeds, longer schedules, and annotation-driven experiments.

### Justification

You report:

```text
batch 32
64×448
0.21M params
~0.4 s/step on one core
data pipeline ~0.03 s
```

So the data loader is not the bottleneck. The bottleneck is compute/backprop/loss. For small models, PyTorch CPU overhead and oneDNN convolution efficiency dominate. Large gains are unlikely unless something obvious is misconfigured.

### Concrete checks

#### A. Run one-core jobs in parallel

Use:

```bash
OMP_NUM_THREADS=1
MKL_NUM_THREADS=1
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
```

Then run 8 independent trainings in parallel. This is usually better than one training job using 8 threads for such a small model.

#### B. Try `channels_last`

Worth a quick benchmark:

```python
model = model.to(memory_format=torch.channels_last)
images = images.to(memory_format=torch.channels_last)
```

This can help oneDNN convolution on CPU, but not always. Benchmark full training step, not just forward pass.

#### C. Try `torch.compile`, but do not expect miracles

For fixed shapes, PyTorch 2.x CPU Inductor may fuse pointwise parts of focal loss.

Test:

```python
compiled_step = torch.compile(train_step, mode="reduce-overhead")
```

or:

```python
torch.compile(model, mode="max-autotune")
```

But small models often see little gain, and compile overhead may not amortize unless runs are long.

#### D. Larger batch

Try:

```text
batch 64
lr 3e-4
steps 2000–2500
```

Compare to:

```text
batch 32
lr 2e-4
steps 3000
```

Do not reduce optimizer updates too aggressively. For focal loss and small real data, too-large batch can reduce useful gradient noise.

#### E. Mixed precision

You already observed mixed precision is slower on this Xeon. That is common unless the CPU has strong BF16/AMX support. Do not use FP16 CPU training.

#### F. Cache expensive target generation

If heat-map target generation is in Python and nontrivial, precompute for real images. But since data is `0.03 s/step`, this is not the main win.

### Practical allocation

Given your problem, I would spend CPU budget like this:

```text
60%: seed sweeps with EMA/SWA
20%: ablations of boundary head / ghost augmentation
20%: longer fine-tunes on hard examples
```

The real bottleneck is not CPU speed; it is insufficient hard labelled data and unstable model selection.

---

## 7. Setup issues that make numbers untrustworthy

**Recommendation:** treat current numbers as development diagnostics, not final product evidence; the main violations are non-independent splitting, repeated use of the frozen set, saturated validation, and unverifiable “zero error” claims from tiny accepted counts.

### Specific issues

#### 1. Split by photo key, not meter ID

This is a serious problem. If the same meter appears in train and validation under different photo keys, validation overestimates generalization.

Fix:

```text
split by meter ID / serial / site / customer if possible
otherwise cluster by perceptual hash + visual meter type
```

At minimum, ensure the same physical meter is never in both train and validation.

#### 2. The frozen 49/34 set is no longer frozen

You have used it for:

```text
model comparison
seed study
soup selection
failure taxonomy
gate analysis
```

That makes it a development set. It is still useful, but not as final evidence.

Fix: collect a new blind test, freeze all code/model/gate first, evaluate once.

#### 3. Held-out m3 val is saturated

Locator IoU50 `66/68 for every seed` means it cannot select models. It is too easy or the metric is insensitive.

Fix: build a hard validation set containing:

```text
Crystal same-height fraction
invisible dot
Tomas/Smart/Yellow
low contrast
ghost segments
wrong-line distractors
leading-zero cases
```

Use exact reading under gate, not only locator IoU50.

#### 4. Multiple seed selection creates winner’s curse

With 27 locator seeds and 31 reader seeds, the best-looking seed on a tiny set is likely overfit to that set by chance.

Fix:

```text
predefine selection metric on dev set
select once
report final on blind set
```

#### 5. 50/50 real/synthetic may be too synthetic-heavy

Synthetic is useful, but your Crystal synthetic moved nothing:

```text
CRYSTAL 2/7 in 31/31 seeds
```

That means the synthetic distribution is missing the key nuisance. A fixed 50/50 ratio may hurt calibration and confidence.

Ablate:

```text
real:synth = 100:0
75:25
50:50
25:75
```

Evaluate by type and by error category, not just overall accuracy.

#### 6. Focal-loss detector scores are not calibrated probabilities

CenterNet heat-map peaks trained with focal loss are not calibrated confidences. Guo et al. (2017) showed modern neural confidence is often miscalibrated; focal loss can further distort probability interpretation.

Therefore:

```text
min_conf = engineering score, not probability
alt ratio = ambiguity feature, not posterior odds
```

Use calibration/audit thresholds, not semantic “confidence” claims.

#### 7. Boundary rules are known-invalid for Crystal

Your own root cause says:

```text
fraction height ratio median = 0.99
dot peak = 0.07–0.29
```

So height and dot-threshold rules cannot carry the required information. Continuing to tune thresholds around this is not standard practice. Add supervised boundary information.

#### 8. Exact target definition must be clarified

You cite:

```text
007022 -> 22
```

as `MISSING_LEFT`, implying leading zeros matter. But “integer part” sometimes means numeric value, where leading zeros do not matter. The product must define whether the output is:

```text
numeric integer value: 007022 == 7022
or display string: 007022 != 7022
```

Train/evaluate consistently.

#### 9. Type distribution and tiny per-type counts

TH34 has:

```text
CRYSTAL 7
SMART_YELLOW/EMETER 6
OTHER 4
```

Per-type conclusions from n=4–7 are extremely noisy. Report confidence intervals or avoid strong claims.

#### 10. Weak-labelling failed cases are not missing at random

The 612 unused photos are concentrated in hard types:

```text
TOMAS 176
SMART_YELLOW 96
CRYSTAL 74
MECHANICAL 34
```

Excluding them biases training toward easy localization. Manually annotate them.

### Blunt summary

Current system has a reasonable tiny-detector architecture, but the evaluation protocol is not strong enough to support the owner’s “never wrong with confidence” rule. The most important next steps are not more seed searches; they are:

```text
1. manually annotate the 612 failed-localization images
2. add a learned integer-boundary signal
3. build a hard meter-ID-disjoint validation set
4. freeze a conservative gate
5. collect a new blind test large enough to bound wrong-output risk
```
