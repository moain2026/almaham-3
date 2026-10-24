# gpt-5.5 — 2026-10-24 08:49 UTC (226s)

## 1. Ghost detections

**Rank for the next release: (a) lattice/slot-aware 1-D NMS → (c) anisotropic heatmap NMS → (b) higher peak thresholds. For retraining: (d) tuned/elliptical Gaussian + hard-negative diagnostics before (e) CTC.** The immediate fix is not “keep the higher score” blindly; it is “cluster detections into physical digit slots, keep one candidate per slot, and abstain if the slot is ambiguous.” This directly targets the failure `005337.88 → 00563307018`, where the error is mostly insertions/duplicates, not missing detections. Raising `RD_PEAK_MIN` will remove ghosts but will also remove the true low-score MT10/EMETER_GREEN digits; it is a coverage killer and should only be used as a final candidate-pruning knob.

**Implement a slot decoder, not just pairwise NMS.** Estimate pitch from detections, assign detections to a 1-D lattice, and decide one digit per slot. If two detections fall in the same slot and the loser score is not clearly lower, return `MISSING_DIGIT`/`AMBIGUOUS`, not a reading. This is safer than “keep higher score” for the 0-wrong product rule.

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class Det:
    x: float
    y: float
    w: float
    h: float
    cls: int
    score: float
    alt_score: float = 0.0

def robust_pitch(dets, min_dets=4):
    xs = np.array(sorted([d.x for d in dets]))
    if len(xs) < min_dets:
        return None
    diffs = []
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            dx = xs[j] - xs[i]
            if dx > 1.5:  # heatmap/input pixels depending on representation
                for k in range(1, 9):
                    diffs.append(dx / k)
    diffs = np.array(diffs)
    widths = np.array([d.w for d in dets if d.w > 0])
    if len(widths):
        med_w = np.median(widths)
        diffs = diffs[(diffs > 0.7 * med_w) & (diffs < 2.5 * med_w)]
    if len(diffs) == 0:
        return None
    q1, q3 = np.percentile(diffs, [25, 75])
    keep = diffs[(diffs >= q1 - 1.5 * (q3 - q1)) & (diffs <= q3 + 1.5 * (q3 - q1))]
    return float(np.median(keep)) if len(keep) else float(np.median(diffs))

def slot_nms(
    dets,
    pitch=None,
    slot_radius=0.38,
    duplicate_ratio_abort=0.55,
    min_keep_score=0.25,
):
    """
    Returns (kept_dets, ambiguous_flag).
    Use before assemble.py integer/fraction cutting.
    """
    dets = [d for d in dets if d.score >= min_keep_score and d.cls <= 9]  # digits only here
    if len(dets) <= 1:
        return dets, False

    dets = sorted(dets, key=lambda d: d.x)
    if pitch is None:
        pitch = robust_pitch(dets)
    if pitch is None or pitch <= 0:
        return dets, False

    # Greedy slot assignment anchored at strongest detection.
    anchor = max(dets, key=lambda d: d.score)
    x0 = anchor.x

    slots = {}
    for d in dets:
        k = int(round((d.x - x0) / pitch))
        residual = abs(d.x - (x0 + k * pitch))
        if residual <= slot_radius * pitch:
            slots.setdefault(k, []).append(d)
        else:
            # off-lattice candidate: keep as separate only if very strong
            slots.setdefault(("off", len(slots)), []).append(d)

    kept = []
    ambiguous = False
    for _, group in slots.items():
        group = sorted(group, key=lambda d: d.score, reverse=True)
        best = group[0]
        if len(group) > 1:
            second = group[1]
            # Same physical cell, competing predictions.
            if second.score >= duplicate_ratio_abort * best.score:
                ambiguous = True
            # If same class duplicate and clearly weaker, suppress silently.
        kept.append(best)

    kept = sorted(kept, key=lambda d: d.x)
    return kept, ambiguous
```

**Use the slot decoder before all boundary logic.** Today, ghosts break the “regular lattice → cut at 6” rule. Therefore the pipeline order should be: raw heatmap decode → class-agnostic slot clustering/NMS → ambiguous-slot veto → boundary/integer cut → confidence gate. Do not estimate the boundary from the unfiltered raw sequence.

**Add explicit ghost metrics to `eval_reader.py`.** For the 38 photos with raw detections and display text, compute Levenshtein alignment against the full display string before and after slot NMS. Report substitutions, deletions, insertions separately; ghost detections are mostly insertions. Also report: `duplicate_slots_per_line`, `ambiguous_slots_per_line`, `raw_full_string_exact`, `slot_full_string_exact`, `integer_exact`, `accepted`, `accepted_wrong`.

```python
def levenshtein_ops(pred, gt):
    # Return counts: ins, del, sub.
    m, n = len(pred), len(gt)
    dp = [[(0,0,0,0) for _ in range(n+1)] for __ in range(m+1)]
    # tuple: cost, ins, del, sub
    for i in range(1, m+1):
        c, ins, dele, sub = dp[i-1][0]
        dp[i][0] = (c+1, ins, dele+1, sub)
    for j in range(1, n+1):
        c, ins, dele, sub = dp[0][j-1]
        dp[0][j] = (c+1, ins+1, dele, sub)
    for i in range(1, m+1):
        cand = []
        c, ins, dele, sub = dp[i-1][j] if False else (0,0,0,0)
        for i in range(1, m+1):
            pass
```

Use an existing implementation if available; the important thing is to track insertion errors separately from digit confusions and misses.

**Do not tune the slot-NMS constants on the frozen 49/34 if you want them to remain tests.** Use m4 validation/calibration for the thresholds. The 38 display-text cases are still useful as a diagnostic dashboard, but if you grid-search `slot_radius`, `duplicate_ratio_abort`, or `min_keep_score` on them, they become development data.

**Try anisotropic heatmap NMS as a cheap secondary change, but do not rely on it.** CenterNet-style decoders use local max-pool NMS as in Zhou et al., “Objects as Points”, 2019. Changing from `3x3` to `1x5` or `3x5` on the output heatmap may suppress nearby same-cell peaks, but with stride 4 a `5`-wide heatmap kernel suppresses only ±8 input pixels. If the ghosts are side-by-side within a digit cell but farther than that, it will not remove them. Test `kernel=(1,5)` and `kernel=(3,5)` on m4, but keep the slot decoder because it operates in physical pitch units.

**Do not fix this primarily by raising `RD_PEAK_MIN`.** Correct cells on MT10/EMETER_GREEN are often `0.30–0.40`; raising the global threshold to `0.45` or `0.50` will convert wrong readings into empty readings, but it will also delete many correct low-contrast digits. For 0-wrong operation, thresholding is acceptable only inside a calibrated selective gate, not as the main duplicate-removal mechanism.

**For retraining, tune the CenterNet Gaussian to suppress multiple local maxima inside one glyph, but cap it below neighbor pitch.** If your current heatmap target is too sharp, the model can learn separate peaks on seven-segment strokes. Use an elliptical Gaussian with something like:

```python
sigma_x = min(0.20 * pitch_out, 0.35 * box_w_out)
sigma_y = 0.25 * box_h_out
radius_x = int(np.ceil(3 * sigma_x))
radius_y = int(np.ceil(3 * sigma_y))
```

Then validate local-maxima-per-GT-cell, not just exact string accuracy. Do not make `radius_x` approach `0.5 * pitch`; overlapping neighboring digit targets will merge true adjacent digits.

**Add a hard-negative diagnostic loop if retraining.** After each candidate model, run it on m4 train without augmentation, collect false local maxima within each GT digit cell, and report `FP_peaks_per_digit_cell`. If this does not fall, the Gaussian change is not solving the ghost mechanism. Online hard example mining ideas from Shrivastava et al., 2016 are relevant, but for this codebase a simpler “collect bad crops → oversample them” loop is probably enough.

**CTC/sequence recognition is a longer-term architecture change, not a 3-day fix.** CTC, Graves et al., 2006, and CRNN, Shi/Bai/Yao, 2016, are natural for line strings and would remove object-detection-style duplicate boxes. But CTC can still confidently hallucinate or collapse repeated characters incorrectly, and calibration for 0-wrong selective prediction remains necessary. I would not replace the detector with CTC until you have a clean pHash split, more full-string labels, and a frozen calibration protocol.

---

## 2. Integer/fraction boundary

**Train an explicit boundary cue; use the locator only as a veto or auxiliary candidate.** The learned locator box carrying boundary information is real, but the audit already shows it is not reliable enough to “trust harder”: 9/17 wrong cases had locator IoU `<0.5`, and mode L being worse than end-to-end proves that box convention is entangled with reader behavior. A boundary signal should be predicted in the reader coordinate frame after slot decoding.

**Add a `SEP`/`BOUNDARY` head or class before adding only `kWh`.** The actual quantity needed by `assemble.py` is the separator x-coordinate between integer and fractional cells. A `kWh` glyph is an indirect cue and may have type-dependent offset. The better target is a separator point/vertical keypoint:

- Heatmap class: `BOUNDARY`.
- Target position: `(x_sep, y_digit_center)`.
- `x_sep`: midpoint between last integer cell and first fraction cell, or dot center if the dot is reliable and centered at the boundary.
- Loss: same focal heatmap loss as CenterNet; no `wh` needed, only offset.
- Decode: choose highest `BOUNDARY` peak near the digit row; cut digit slots with `x_center < x_sep`.

This is a small code change and keeps the CenterNet-style decoder.

**Also annotate `kWh/unit` as an auxiliary class where visible, especially for CRYSTAL.** For CRYSTAL, the physical cue is the printed `kWh` glyph above the two fraction digits. Add a `UNIT_KWH` box class if the glyph is inside the padded reader crop. Do not hard-code “cut at glyph x” until measured; instead measure the offset:

```text
delta = (x_kwh_reference - x_sep) / pitch
```

per meter type. If the standard deviation of `delta` is below about `0.20 pitch` on calibration, then the glyph can be used as a deterministic boundary candidate. Otherwise use it as an auxiliary detection feature or as training signal for the boundary head.

**Use locator right edge as a conservative agreement check.** For every readable validation image, compute:

```text
e_locator = (x_locator_right_in_reader_coords - x_sep_gt) / pitch
```

Then grid-search only on calibration:

```text
x_sep_from_locator = x_locator_right + k * pitch,  k ∈ {-0.5, -0.25, 0, 0.25, 0.5}
```

Promote locator clipping only if there are zero wrong integer cuts on calibration and it improves coverage. Otherwise use:

```text
if abs(x_sep_reader - x_sep_locator) > 0.50 * pitch:
    abstain
```

not “clip harder.”

**Measure boundary separately from digit recognition.** Create a boundary-eval CSV with one row per readable photo:

```text
photo_id
meter_type
gt_integer
gt_full_display
pitch
x_sep_gt
x_sep_dot
x_sep_height_drop
x_sep_lattice6
x_sep_locator_k
x_sep_boundary_head
x_sep_kwh
boundary_abs_err_pitch
oracle_cut_correct
detected_cut_correct
final_integer_correct
```

The key metric is `oracle_cut_correct`: use the GT/full-display string or manually verified digit slots, then apply only the boundary method. This isolates boundary errors from digit classification and ghost detections.

**Define success in pitch units.** A boundary predictor is safe if the separator falls between the last integer slot and the first fraction slot. In practice require margin:

```text
-0.35 <= (x_pred_sep - x_gt_sep) / pitch <= +0.35
```

for “safe,” and treat anything outside that as a boundary failure. For a 0-wrong product, the calibrated gate should abstain when boundary candidates disagree by more than `0.4–0.5 pitch`.

**Concrete plan.**

1. Add `BOUNDARY` labels to m4 by derivation wherever possible. If full digit/fraction boxes exist, derive automatically. If only integer boxes exist, use the right edge of the verified integer-line box as a weak boundary label and mark it `weak=1`.
2. Manually label `BOUNDARY` and `UNIT_KWH` on the 38 display-text diagnostic images and the unused CRYSTAL/MT10-like images.
3. Train reader with digits + dot + boundary, and optionally `UNIT_KWH`.
4. Evaluate four boundary methods on m4 calibration and validation: current heuristic, locator clip, `UNIT_KWH` offset, boundary head.
5. In production decode, accept only when slot-NMS is non-ambiguous and boundary evidence is consistent.

---

## 3. SMART_MT10 with zero training data

**Do not tune on the 9 SMART_MT10 test photos.** Report them separately as an out-of-distribution meter type: `2/9` currently, with zero examples in the labeled pool. If you use those 9 to design thresholds or synth parameters and then report improvement on them, the number is no longer an honest test result.

**For product behavior, prefer abstention on MT10-like low-confidence same-height-fraction displays until real data exists.** A simple safe rule is:

```text
if same-height 8-slot lattice
and no reliable dot/boundary
and median digit score < calibrated threshold:
    EMPTY / not confident
```

This avoids confidently returning the wrong integer on the exact OOD type that has no training support.

**Procedural MT10-style synthesis is worth doing; neural style transfer is not where I would spend time.** Seven-segment LCDs are low-dimensional: segment geometry, contrast, blur, glare, cell background, and viewing angle matter more than high-level texture. Procedural rendering with domain randomization, in the spirit of SynthText, Gupta et al., 2016, and domain randomization, Tobin et al., 2017, often works for this kind of constrained OCR. CycleGAN-like style transfer is risky because it can change or hallucinate segment strokes and decimal dots while preserving the label incorrectly.

**Build `synth2_mt10` procedurally.** Generate lines with:

- 6 integer cells + 2 fractional cells.
- All 8 cells same height.
- Faint or absent dot.
- Dark LCD background, low contrast digits.
- Yellow/dark case context only for locator synth, not necessarily reader synth.
- Segment dropout, partial activation, motion blur, JPEG artifacts, gamma shifts.
- Random leading zeros.
- Fraction digits present and labeled, even if the product returns only integer.

Use synthetic full-display labels such as:

```text
003214.57
120045.03
999999.99
```

and make sure the annotation includes all 8 digit boxes plus dot when visible.

**Use real unlabeled MT10-like photos as style/background sources, not as labels.** The owner’s 97 unlabeled tilted photos can still provide LCD background crops, glare, blur, and geometry. If possible, inpaint or heavily blur the existing digits and render random synthetic digits on top. Do not pseudo-label their readings unless the owner can verify them.

**Style augmentation of existing TOMAS lines is weaker than procedural MT10 synthesis.** Photometric transforms that make TOMAS look darker/lower-contrast are label-preserving and useful, but they do not create the critical MT10 structure: 8 same-height cells, faint dot, different boundary cue. So option ranking is:

1. Collect 30–50 real SMART_MT10 photos with owner readings.
2. Procedural MT10 synthesis.
3. Label-preserving photometric/style augmentation of existing lines.
4. Neural style transfer: avoid unless you manually inspect label preservation.

**When the owner collects data, ask for readings, not just photos.** Minimum useful collection: 30–50 SMART_MT10 photos, at least 10 distinct meters if possible, with owner-verified integer reading and one close crop/one normal user photo per meter. If fractional display is visible, record the full display string for a subset; it is valuable for boundary evaluation.

---

## 4. Honest validation

**Do not use the 49/34 sets for seed selection or threshold selection.** The proposal says “without touching 49/34,” but then says “promote only if 49/34 not worse.” That is test-set selection. Use 49/34 once after the model and gate are locked. If it fails, do not tweak and rerun; collect a new holdout or explicitly mark 49/34 as development data.

**Split m4 by pHash clusters into at least train / model-select / calibration.** Since m4 has 903 photos, make a frozen group split such as:

```text
train:       ~70%
select-val:  ~15%   model/seed choice, exact accuracy
calib-val:   ~15%   confidence gate thresholds only
```

Stratify by meter type and readability. Keep clusters intact. If owner/meter ID is known, group by that before pHash; pHash can miss tilted near-duplicates.

**Select the model on exact validation before calibrating the gate.** For each seed/model:

```text
metric_1: reader exact from standard crop / human line, if available
metric_2: end-to-end exact
metric_3: locator IoU / line exact proxy
metric_4: ghost insertions per line
metric_5: boundary-cut correctness
```

Pick one model using `select-val`. Then freeze weights. Then tune confidence thresholds on `calib-val`.

**Use paired comparisons against the reference, not only raw percentages.** On the same validation photos, compute:

```text
new_wins = count(new correct, ref wrong)
new_losses = count(new wrong, ref correct)
net_delta = (new_wins - new_losses) / n
```

With `n=177`, differences of 1–3 photos are noise. Require either a meaningful positive delta, e.g. `>= +3–5 pp`, or choose the simpler/safer model when tied.

**For the selective gate, report coverage and selective risk with Clopper–Pearson bounds.** If accepted readings have zero errors, the upper 95% error bound is still large at small `n`:

```text
two-sided CP upper for 0 errors = 1 - 0.025 ** (1/n)
one-sided 95% upper             = 1 - 0.05  ** (1/n)
```

Examples:

```text
n=17 accepted, 0 wrong  -> two-sided upper ≈ 19.5%, one-sided ≈ 16.2%
n=73 accepted, 0 wrong  -> two-sided upper ≈ 4.9%,  one-sided ≈ 4.0%
n=300 accepted, 0 wrong -> two-sided upper ≈ 1.2%,  one-sided ≈ 1.0%
```

So “0 wrong” on 17 or 73 accepted samples is necessary but not strong statistical evidence of near-zero field risk.

**Promotion rule should be rewritten.** Use:

1. Candidate selected only on m4 `select-val`.
2. Gate calibrated only on m4 `calib-val`.
3. Freeze code, weights, thresholds, and Kotlin parity tests.
4. Run 49/34 once.
5. Report overall and per-type results, including SMART_MT10 as OOD.
6. If 49/34 is worse, do not iterate on it; collect more data and create a new frozen test.

**Keep the old 49/34 as “legacy frozen audit,” not the only final truth.** You have already inspected them extensively. That is unavoidable, but it means future improvements can overfit them indirectly. Start building a new post-m4 field holdout now, especially for SMART_MT10 and EMETER_GREEN.

---

## 5. Model capacity

**A 2× reader is plausible but will not fix OOD type absence or boundary ambiguity by itself.** Going from `0.21M` to roughly `0.8M` parameters may raise heatmap quality and reduce low scores on known types. It will not teach SMART_MT10 with zero real examples, and it will not solve same-height fraction cutting unless the training target includes that cue.

**Low digit scores are not automatically a capacity diagnosis.** CenterNet heatmap scores trained with focal loss, Lin et al., 2017, are not calibrated probabilities. A correct digit score of `0.35–0.50` can result from low contrast, label noise, center ambiguity, too-sharp Gaussians, or focal-loss calibration. Use recall/precision and exact string accuracy, not raw score alone.

**Run one controlled width experiment.** Train exactly two reader models on the same m4 split:

```text
A: current width, same recipe, one seed
B: 2× channels, same recipe, same seed where possible
```

Keep augmentation, synthetic/real ratio, steps, and validation scripts identical. If larger training is slower on CPU, allow both models to train until the no-augmentation train metric plateaus, but do not give the 2× model more data or a different recipe.

**Evaluate these diagnostics.**

```text
1. reader exact on select-val
2. reader exact from human/verified line boxes
3. raw full-display string exact, before assemble
4. insertions per line after slot-NMS
5. mean/max local maxima per GT cell
6. min digit score on correct accepted lines
7. selective coverage at 0 wrong on calib-val
8. train-set exact on a held-out no-aug train subset
```

Interpretation:

```text
2× improves train and val materially       -> capacity was limiting.
2× improves train only                     -> data/domain/label ceiling.
2× improves scores but not exact           -> decode/boundary problem.
2× improves known types, not MT10          -> OOD data problem.
2× increases confident wrongs              -> reject for product.
```

**Adopt 2× only if the gain is bigger than seed noise.** Your seed spread is already several photos/points. Require something like `>= +5 pp` on reader exact or a clear increase in calibrated 0-wrong coverage, with no increase in accepted-wrong cases. If the gain is `+1–2 pp`, spend the effort on data and decoding.

---

## 6. Confidence

**Temperature scaling is useful for reporting/calibration, not for creating new safe predictions.** Temperature scaling, Guo et al., 2017, is monotonic for logits; it changes probability calibration but not the ranking or the decoded string. It may help set a cleaner threshold, but alone it will not recover many extra zero-wrong readings.

**TTA agreement is the best candidate for increasing 0-wrong coverage.** Run 3–5 deterministic reader transforms and require identical integer output plus stable boundary:

```text
TTA0: original
TTA1: gamma 0.85
TTA2: gamma 1.15
TTA3: scale x/y 0.98 with recrop
TTA4: scale x/y 1.02 with recrop
```

Accept a low-score reading only if all TTAs return the same integer, the same digit count, non-ambiguous slots, and boundary positions within `0.35–0.50 pitch`. Compute median digit score across TTAs for reporting, but use agreement as the safety signal.

**Use DSEG only as a veto or second confirmation, not as an override.** AUC `0.76` is weak. It can catch some detector mistakes, but it is not strong enough to say “detector says 6, DSEG says 8, choose 8.” Safe use:

```text
if DSEG predicted class != detector class:
    abstain
if DSEG margin < calibrated threshold:
    abstain on borderline detector cases
```

Do not let DSEG rescue a digit that the detector thinks is ambiguous unless TTA is unanimous and the gate was calibrated that way.

**Use two pre-registered gates, not many fitted combinations.** Example:

```text
Gate A: current strict detector gate
    status OK
    no ambiguous slot
    min_digit_score >= 0.55
    max_runner_up_ratio < 0.50
    boundary reliable

Gate B: stable-low-score gate
    status OK
    no ambiguous slot
    min_digit_score >= 0.35
    max_runner_up_ratio < 0.60
    all TTAs return same integer
    boundary candidates agree within 0.50 pitch
    DSEG agrees with every digit, or at least with every digit whose detector score < 0.55
```

Calibrate only the few numeric thresholds on m4 calibration. Do not search dozens of combinations on 73 photos.

**If you want one scalar risk score, keep it monotone and simple.**

```python
def risk_features(reading):
    return {
        "bad_status": reading.status != "OK",
        "ambiguous_slot": reading.ambiguous_slot,
        "tta_disagree": not reading.tta_unanimous,
        "boundary_disagree": reading.boundary_disagree,
        "low_score": 0.55 - reading.min_digit_score,
        "bad_margin": reading.max_alt_ratio - 0.50,
        "bad_dseg": reading.max_dseg_disagreement,
    }

def accept_gate(r):
    if r.status != "OK": return False
    if r.ambiguous_slot: return False
    if r.boundary_disagree: return False
    if r.min_digit_score >= 0.55 and r.max_alt_ratio < 0.50:
        return True
    if (
        r.min_digit_score >= 0.35
        and r.max_alt_ratio < 0.60
        and r.tta_unanimous
        and r.dseg_all_agree
    ):
        return True
    return False
```

This kind of monotone rule is less likely to overfit than logistic regression or isotonic regression on 73 samples.

**Use selective prediction discipline.** The relevant literature is selective classification, Geifman and El-Yaniv, 2017, and conformal/risk-control ideas from Vovk et al., 2005, and Angelopoulos and Bates, 2021. In your case, the practical version is: fix a gate family, choose the most permissive gate with zero calibration errors, then report coverage and CP risk bounds on untouched data.

---

## 7. Next 3 days: stop/start priority

**Stop seed fishing and recipe micro-tuning.** You already ran 31 reader seeds, EMA, soups, stronger tilt, locator aug variants, and fraction masking. The dominant failures are data/type mismatch, ghost decoding, and boundary ambiguity. More seeds are low expected value.

**Stop using 49/34 for development decisions.** Keep them as a legacy audit. If a new candidate fails there after being locked, do not tune against that failure; add data and create a new holdout.

**Stop treating human integer boxes as a clean reader oracle.** Mode L being worse than end-to-end shows that crop convention and boundary cues are part of the learned behavior. Use human boxes for diagnostics, but evaluate boundary and crop effects explicitly.

**Day 1: implement slot-NMS and ghost metrics.** Add a raw-detection dump and an eval script that reports insertion/substitution/deletion against full display text where available. Run current model with:

```text
baseline decode
+ heatmap NMS 1x5
+ slot-NMS
+ slot-NMS ambiguity veto
```

on m4 validation/calibration and the diagnostic 38. Choose constants only from m4 calibration.

**Day 1: freeze validation protocol.** Create cluster-grouped `train/select-val/calib-val` files. Add a single command that produces:

```text
end-to-end exact
reader exact
locator exact/IoU
raw full-string exact
ghost insertions
boundary failures
selective coverage
accepted wrong
CP bounds
per-meter-type table
```

Do not manually inspect outputs before model/gate selection unless the inspected split is declared development.

**Day 1–2: label the unused real data before more synthetic experiments.** Process the 134 labeled photos, the 79 owner-verified readings, the 41 suspicious 2-digit CRYSTAL labels, and the 19 unboxed photos. For the 41 CRYSTAL cases, either fix the V/A/PF poison or exclude them; poisoned short labels are worse than no labels. Add meter type tags and, where possible, boundary and `kWh` glyph labels.

**Day 2: add boundary instrumentation, even before training a boundary head.** For every validation image, compute dot/height/lattice/locator boundary candidates and normalized error in pitch units. This tells you whether locator clipping deserves another try or should be only a veto.

**Day 2: run the m4 seeds already training and select only from m4 select-val.** Evaluate seeds with the new ghost and boundary metrics, not only exact accuracy. Pick one reference candidate before confidence calibration.

**Day 2: build `synth2_mt10` procedurally.** Generate same-height 8-cell dark-LCD lines with faint dots and low contrast. Train one reader variant with synth2 if CPU time allows. Do not use the 9 SMART_MT10 test cases to tune synth parameters beyond generic physical observations.

**Day 2–3: implement TTA agreement gate and optional DSEG veto.** Use a fixed small set of TTAs. Calibrate Gate A/Gate B on m4 calibration only. Report coverage and accepted-wrong count with CP bounds.

**Day 3: run one controlled 2× reader experiment only if CPU budget allows.** If it cannot finish in time, defer it; do not let it block the decoding/boundary fixes. If it finishes, compare against same-seed 1× using the frozen eval script.

**Day 3: lock one candidate and run the legacy frozen sets once.** Produce a table like:

```text
overall 49
overall 34
trained types only
SMART_MT10 only
EMETER_GREEN
CRYSTAL
coverage under strict gate
accepted wrong under strict gate
CP upper bound
```

If SMART_MT10 remains poor, say so and ship with abstention for that pattern until 30–50 real MT10 photos are collected.

**Parallel owner request: collect SMART_MT10 and EMETER_GREEN now.** Ask for 30–50 SMART_MT10 photos with owner-verified integer readings, plus 20–30 EMETER_GREEN if possible. Require varied tilt/lighting, but one clear close photo per meter. This is higher value than another augmentation sweep.
