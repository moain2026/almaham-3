# gpt-6-astra — 2026-10-24 08:46 UTC (139s)

## 1. Ghost detections: suppress duplicates, but do not turn ambiguity into confidence

**Start with cross-class, geometry-aware duplicate suppression—not a higher global threshold.** Your scores overlap too much between correct digits and ghosts for a threshold increase to be a clean solution. However, removing a competing detection must not erase the evidence that the cell was ambiguous.

### Ranking the proposed fixes

This ranking is an engineering prior, not a result established by your 38 examples.

| Option | Expected benefit here | Main risk | Recommendation |
|---|---|---|---|
| **(a) Pitch-aware 1-D suppression** | High if most extras are duplicates within cells | Incorrect pitch can merge adjacent genuine digits; suppressing a conflicting label can create false confidence | **First experiment**, with ambiguity retained |
| **(c) Wider horizontal heat-map max pooling** | Moderate for nearby peaks of the **same class** | Fixed pixel scale; does not remove cross-class ghosts; may suppress adjacent repeated digits | Cheap diagnostic, not the main solution |
| **(b) Higher peak threshold** | Removes low-score ghosts | Removes correct MT10/EMETER digits at the same scores; can produce plausible but truncated readings | Threshold sweep as a baseline; no per-class tuning yet |
| **(e) CTC/sequence head** | Potentially substantial, longer-term | Needs trustworthy sequence labels, still has decimal ambiguity and correlated confident errors | Consider after auditing labels and crops |
| **(d) Wider target Gaussians** | Uncertain; weak mechanism for fixing this problem | Does not impose one detection per cell or cross-class exclusivity | **Do not prioritize** |

For training changes among these choices, I would test **a sequence formulation before trying to solve duplicate peaks by enlarging Gaussians**, but neither is the highest-priority three-day task.

In standard CenterNet, Gaussian heat-map targets and the modified focal loss do **not** act as repulsion between detections. Around an object center, a wider Gaussian generally reduces the negative penalty in that neighborhood; it does not enforce “one class, one peak per physical cell.” Inspect your actual loss implementation, but do not expect Gaussian widening to solve cross-class ghosts. See **“Objects as Points” (Zhou, Wang and Krähenbühl, 2019)** and the inherited heat-map formulation in **“CornerNet” (Law and Deng, 2018)**.

### Implement (a) as cell hypotheses, not destructive NMS

Use a high-recall candidate list and construct competing explanations of each cell. Keep the top label for assembly, but preserve conflicting labels and discarded detections for the confidence gate.

```python
@dataclass
class CellHypothesis:
    x: float
    best_digit: int
    best_score: float
    alt_digit: int | None
    alt_score: float
    member_ids: list[int]
    geometry_ambiguous: bool
```

Three important implementation details:

1. **Do not estimate pitch from the median spacing of all raw detections.** Ghosts contaminate exactly that quantity. Fit a robust lattice to candidate centers, allowing missing cells and multiple candidates per cell. Alternatively, estimate pitch from a high-score subset and retain several plausible pitch hypotheses. If pitch is unstable, abstain rather than force a grouping.
2. **Do not use unconstrained single-linkage clustering.** A chain of detections can bridge two real cells. Require a bounded cluster span or assignment to distinct lattice slots.
3. **Keep dots out of digit suppression.** Handle dot position, size and confidence separately.

Your `0.6 × pitch` criterion is worth testing, but it is relatively aggressive. I would compare **0.4, 0.5 and 0.6 × pitch**, without combining that sweep with numerous other tunable rules. Require baseline compatibility as well as horizontal proximity. If the 0.4 and 0.6 settings produce different integer readings, record `DECODE_UNSTABLE` and abstain initially.

For a single physical cell with detections `3:0.43` and `8:0.39`, keeping `3` is reasonable for the candidate transcription. It is **not** reasonable to let suppression transform that cell into an unambiguous `3`. Define the runner-up over different digit labels in the cell neighborhood, not merely over boxes that survive NMS.

### What horizontal max-pool NMS can and cannot do

A `(1, 5)` max pool on each class heat map only compares same-class responses. It will not suppress a `0` and an `8` at nearby locations. At stride 4, its horizontal half-width is two feature cells, or roughly **8 input pixels**; whether that is safe depends on actual resized cell pitch. Measure that distribution before choosing a kernel. Adjacent identical digits such as `00` are the critical regression test.

### Training-level fix: correct supervision and penalize the actual errors

Before changing architecture, audit a small batch of training targets **after all crop, resize and augmentation operations**:

- Every visible digit in the reader task should have consistent supervision.
- If fractional digits are present but not part of the transcription target, decide whether they are supervised as digits, explicitly ignored, or excluded by crop. Mixing these policies across sources is harmful.
- Inspect nearest-neighbor digit centers at stride 4. Identify target collisions and tiny separations.
- Check that `digit-perm` alters the image and annotation consistently, rather than creating implausible cell geometry or incorrect text.

Then add **manually verified hard examples** where the model predicts between-cell digits, reflections or competing digits on one cell. Use complete labels on these crops and oversample the crops; do not automatically relabel model predictions as negatives. This is more directly targeted than another generic augmentation sweep.

A CTC model removes the need for box-level duplicate suppression, but not insertion errors or boundary ambiguity. **“Connectionist Temporal Classification” (Graves et al., 2006)** is a sensible alternative if full visible-line transcripts are reliable. Do not train CTC on integer-only transcripts while sometimes showing clearly visible fractions unless the crop/task definition deliberately supports that behavior.

### Measurement on the 38 examples

The 38 examples are a **decoder development set**, not evidence of field-level safety. Add physical cell IDs/boxes and fraction-boundary annotations; raw strings alone cannot tell you whether NMS merged genuine neighboring cells.

Report, before and after each decoder change:

- **Extra detections per true cell**, including conflicting-label duplicates.
- **Missing true cells** and adjacent-cell merges.
- Digit substitutions after cell matching.
- Exact full digit sequence, with dot detection reported separately.
- Exact integer reading.
- Accepted correct, accepted wrong, and abstained.
- How many newly correct examples required resolving ambiguity by score alone.

Run this on the **same photos under learned and human crops**, not only human crops. A change that cleans oracle crops but breaks the deployed crop distribution is not a win.

---

## 2. Integer/fraction boundary: use independent cues and explicit abstention

**Neither the unit glyph nor the learned LINE edge should be universally trusted.** The right near-term design is a boundary hypothesis with evidence provenance: visible dot, validated layout cue, locator edge, or unsupported inference.

Where eight same-height cells have no visible decimal indicator, the boundary can be **unidentifiable from the digit pixels alone**. A boundary regressor cannot recover information that is absent; it will learn a layout prior. That can work for known layouts and fail confidently on unseen ones.

### Use the kWh glyph conditionally, not as a universal decimal marker

For CRYSTAL, the glyph is a credible cue **because you have a physical observation linking its placement to the fraction cells**. But the correct mapping need not be “cut at glyph center x.” Measure whether the relevant relation is to its left edge, center, or a fixed cell offset.

For every annotated CRYSTAL image, record:

```text
x of last integer center
x of first fraction center
digit pitch
kWh bounding box
visibility/occlusion of kWh
layout subtype
```

Fit a simple relationship such as:

\[
x_\text{boundary}=x_{\text{kWh,left}}+\alpha p,
\]

where \(p\) is digit pitch. Inspect residuals in **cell units**, separately by layout subtype. If the mapping differs across layouts, use layout-specific rules or reject ambiguity; do not average them into one misleading relationship.

Adding a 12th class is reasonable **only if the glyph is actually visible and resolvable in the reader input**. Inspect its rendered dimensions at 64×448. A tiny unit glyph above the digits may be too small at stride 4, or outside the existing crop. If so, test a slightly taller/context-preserving reader crop or a small context branch. Also distinguish the relevant energy-unit glyph from printed units elsewhere on the meter.

### Treat the locator edge as a noisy boundary measurement

Your oracle result shows crop-definition sensitivity. Before retraining, measure:

\[
r = \frac{x_{\text{LINE,right}}-x_{\text{true boundary}}}{p}.
\]

Plot this for learned boxes and human boxes, by meter type. This will show whether a fixed `LINE_CLIP + k·pitch` rule is even plausible.

Do **not** pick the best `k` on the frozen sets. Estimate an edge-error interval from development data. A digit is safely an integer digit only if its assignment is unchanged across that interval. If a possible digit lies near the uncertain cutoff, abstain rather than simply delete it.

Also, **IoU < 0.5 is not sufficient causal evidence of locator failure**. A low-IoU box might still preserve all useful content, and a high-IoU box can lose the boundary cue. Recompute paired outcomes on the common 38 photos, with identical padding and mapping code. Record separate left/right/top/bottom errors and whether integer cells, fraction cells and glyphs are visible.

### Concrete boundary plan

1. **Annotate boundary and cue visibility on development data.** Record the first fraction cell or the gap immediately before it, plus “cue not visible / ambiguous.”
2. **Evaluate boundary decisions with oracle digit boxes.** This isolates boundary logic from ghosts and digit substitutions.
3. Compare three prespecified rules:
   - Dot-based boundary, otherwise abstain.
   - Dot plus validated layout/glyph cue.
   - Those cues plus locator edge, accepted only when the hypotheses agree.
4. Measure **boundary-cell error rate and coverage**, not just pixel regression error.
5. Run the same rules with predicted cells and report end-to-end accepted wrong readings.

If this shows boundary errors remain a major independent failure mode, train a tiny boundary head. I would prefer **classification over gaps between cells, with an explicit unknown/unsupported outcome**, to unconstrained x-regression. A spatial boundary heat map is another viable formulation. In either case, test separately on known layouts, held-out layouts and occluded cues.

**Do not introduce “six integers” as an unconditional fallback.** It is a layout rule, not visual evidence. Use it only for a reliably identified, validated layout.

---

## 3. SMART_MT10: report the gap, synthesize deliberately, collect real evidence

**Use (a) plus a controlled version of (b).** Report the current 2/9 transcription result by type, and report how many of those nine were confidently accepted and wrong. Raw accuracy and selective risk are different quantities. For deployment, an unsupported layout should lead to abstention where you can detect it—not a forced six-digit result.

Those nine photos have already informed several design decisions. Keep them as a named **MT10 challenge/development set**, but do not present improvement on them as independent validation of MT10 generalization.

### Prefer procedural LCD synthesis to generic style transfer

For this particular task, I would rank:

1. **Procedural seven-segment rendering with MT10-like layout and optics.**
2. **Label-preserving style augmentation of existing lines.**
3. **Learned image-to-image style transfer.**

The advantage of procedural synthesis is control of the failure mechanism: eight equal-height cells, segment geometry, faint decimal point, dark LCD, weak contrast, ghosted inactive segments and realistic spacing. Generic gamma or color augmentation cannot turn the wrong decimal layout into the correct one.

Learned style transfer is not my recommendation for an eight-core CPU setup or a zero-confident-error objective. It can alter thin segments and dots while preserving neither label semantics nor known uncertainty. General synthetic-text results—e.g. **“Synthetic Data and Artificial Neural Networks for Natural Scene Text Recognition” (Jaderberg et al., 2014)**—support synthetic supervision broadly, but do not establish success on this specific LCD domain.

### Minimal synth2 experiment

Keep the real/synthetic ratio at 50/50. For one controlled reader run, replace **25% of synthetic samples**, thus **12.5% of all samples**, with MT10-style examples. Keep initialization, seed, steps and all other augmentations fixed.

Render variation in:

- Eight equal-height cells and realistic gap-to-width ratios.
- Multiple seven-segment shapes, not one font.
- Low contrast and spatially varying illumination.
- Inactive-segment leakage and reflections.
- Blur, perspective and downsampling in a physically sensible order.
- Decimal visibility, including nearly invisible dots.

**Do not label an invisible dot as a visible detectable object.** If it is erased during rendering, mark its detection supervision appropriately; the reading may still have a decimal boundary defined by layout, but that is a different target.

Measure gains on MT10 separately from regressions on known types, and distinguish digit recognition from boundary inference. A reader-only synthesis experiment cannot solve the regional domain gap in the locator; scene synthesis is a separate experiment.

### Collect 30–50 photos with diversity, not 50 nearly identical views

Aim for **10–15 distinct meters**, with a few views per meter: frontal, oblique, dark/reflective. Obtain full visible text, integer reading, type, line/boundary annotations and session identity. Reserve approximately **one-third of meters**, not images, for a genuinely untouched test.

For the existing 97 tilted photos, obtain a paired frontal readable photo of the same stable display where practical. If the reading cannot be verified, label the image unreadable/uncertain; do not derive truth from the model.

---

## 4. Validation: your proposed promotion rule uses the test sets for model selection

**Remove “49/34 not worse” from the recurring promotion rule.** Once those results determine which model, decoder or threshold survives, those sets are no longer frozen tests. Given the number of experiments and the diagnoses already made, treat them as historical challenge sets and obtain a new prospective acceptance set.

A pHash split is an improvement, but it does not establish independence by physical meter or capture session. Hashes can miss the same meter under perspective or illumination changes, and similar LCDs from different meters can collide. Group by **meter/session/source where available**, use pHash as a supplement, and inspect nearest cross-split neighbors.

Before interpreting m4, reconcile the manifests: **531 + 381 = 912**, while m4 is described as 903, and the clustering summary covers 850 images. These may be legitimate exclusions, but log every exclusion, duplicate, missing-label case and split assignment so the actual populations are explicit.

### Use three roles, even if the sets are small

1. **Training:** weight fitting.
2. **Selection/development:** seed choice, decoder choice and architecture choice.
3. **Calibration/safety audit:** fixed system, confidence policy only—or preferably a final locked audit after threshold selection.

If the 177 validation examples are all you have, a group-aware split of roughly **90 selection / 87 calibration** is workable for development but provides weak safety evidence. Do not expect it to support a strong deployment claim, especially at 23% coverage.

Choose a seed using a prespecified metric on the selection split: for example, end-to-end integer exactness, with full-sequence reader and locator metrics as diagnostics. Use a fixed tie-break rule and treat differences of one or two examples as weak evidence. Do not optimize seed, threshold, NMS radius, TTA set and verifier cutoff jointly on the calibration half.

If thresholds are searched using correctness labels on calibration data, a standard binomial interval at the selected best threshold is **not automatically selection-valid**. Either:

- Choose the policy on development data and audit once on an untouched set; or
- Use a prespecified small family of gates with simultaneous risk bounds or a formal risk-control procedure.

See **“Selective Classification for Deep Neural Networks” (Geifman and El-Yaniv, 2017)** and **“Distribution-Free, Risk-Controlling Prediction Sets” (Bates et al., 2021)**. Such methods still require appropriate sampling assumptions; they do not make an unseen regional distribution safe.

### What 0 wrong out of 17 actually establishes

For a **fixed** gate with zero errors among \(n\) independent accepted cases, the one-sided 95% binomial upper bound is:

\[
p_{\rm wrong}\le 1-0.05^{1/n}.
\]

For \(n=17\), this is approximately **16.2%**, not close to zero. The two-sided 95% Clopper–Pearson upper endpoint is approximately **19.5%**.

The denominator is **accepted readings**, not all 73 inputs. With zero observed errors, approximately:

- **299 accepted independent cases** support a one-sided 95% upper bound below 1%.
- **2,995 accepted independent cases** support a bound below 0.1%.

At 23% coverage, that corresponds to roughly **1,300** and **13,000** independent inputs. Correlated images of the same meter provide less evidence. Moreover, these numerical bounds are only illustrative for your current result if the gate was tuned on those same photos.

**No finite validation set proves “never wrong.”** You can specify a conservative operating policy and report zero observed accepted errors with uncertainty; you cannot honestly certify literal zero risk.

---

## 5. Capacity: plausible benefit, but measure transcription—not score inflation

A 0.21M-parameter detector may be capacity-limited, but the audit does not establish that. Domain shift, inconsistent task boundaries and duplicate decoding already explain substantial error. Low scores alone are not evidence of insufficient capacity: focal-loss heat-map outputs are not calibrated correctness probabilities.

Doubling channels gives approximately **4× convolutional arithmetic** in layers where both input and output widths double, not reliably 2× latency. Parameters near 0.8M and FP32 weights near 3.2 MB are plausible; actual CPU/Android latency and peak memory must be measured. Activation memory often grows closer to 2×.

### One controlled experiment

Use the chosen m4 split and a fixed decoder. Train:

- Baseline-width reader.
- 2×-width reader.

Use the same sample order, augmentations, training steps and loss settings. **Both need comparable initialization.** Comparing a heavily warm-started small model with a randomly initialized large model after 3,000 steps would confound capacity with training history. If matched pretraining is infeasible, document that limitation and do not interpret a larger model’s loss as a capacity verdict.

Evaluate:

| Metric | What it distinguishes |
|---|---|
| Train and selection-set digit/sequence errors | Underfitting versus generalization failure |
| Ghosts and missing cells | Actual structural improvement |
| End-to-end integer exactness | Product utility |
| Fixed-gate accepted correct/wrong | Immediate operational effect |
| Risk–coverage curve on development data | Better ranking versus merely larger scores |
| Runtime and memory | Deployment cost |

Interpret results as follows:

- **Train and selection accuracy improve:** capacity is plausibly useful.
- **Train improves, selection worsens:** more capacity is not the current solution without better data/regularization.
- **Scores rise but exactness and ranking do not improve:** no demonstrated benefit.
- **Known types improve but MT10 does not:** capacity did not resolve missing-domain coverage.

With no GPU and m4 already running, I would **not start this before the decoder and data audits**. One matched run is enough to decide whether a second seed is worth the CPU time; it is not enough to establish a robust architecture win.

---

## 6. Confidence: test stability first; scaling cannot manufacture evidence

There is no defensible way to name the winner from aggregate scores and AUC. My implementation priority would be:

1. **Geometry/boundary consistency and benign TTA agreement.**
2. **Segment verifier as a narrowly defined veto.**
3. **Temperature scaling for calibration/reporting, not as the primary coverage fix.**

### Temperature scaling

For an independent heat-map logit \(z\),

\[
p_T=\sigma(z/T)
\]

is monotonic for \(T>0\). It preserves local ordering and does not make a wrong peak become the right one. It can make a fixed numerical threshold accept more examples, but that is not inherently safer than lowering the original threshold.

Your score-ratio rule is not invariant to temperature scaling, and the heat-map logits were trained with a dense focal objective rather than a per-reading correctness objective. Do not interpret calibrated-looking digit scores as calibrated exact-reading probabilities. See **“On Calibration of Modern Neural Networks” (Guo et al., 2017)** for temperature scaling and its scope.

### TTA: test invariance of the whole decision

Start with a small, fixed set of **five deterministic views**:

- Identity.
- Gamma 0.85.
- Gamma 1.15.
- Slightly tighter crop, still containing the full detected line.
- Slightly looser crop.

Specify gamma’s input convention and use unchanged clipping rules. For crop variants, adjust padding modestly—for example ±0.03 horizontally and ±0.05 vertically around the current defaults—rather than cutting into the LINE box.

Require agreement on:

- Cell assignments after inverse coordinate mapping.
- Integer string.
- Integer/fraction boundary.
- Assembly validity.

Use **unanimity**, not majority vote, for an initial conservative policy. Majority vote can simply consolidate the same systematic mistake. Five views would be roughly **0.47 s at 93 ms per full pass on your server**, before reuse or batching; measure on Android.

TTA is useful precisely because your result is sensitive to crop convention. But all views can share the same wrong digit or wrong six-cell prior. Treat agreement as an uncertainty feature, not five independent confirmations.

### Segment verifier: evaluate its conditional value

An AUC of 0.76 on 73 cases says little about the low-error tail. Evaluate the verifier **among cases the detector would otherwise accept**:

- Accepted wrong readings vetoed.
- Accepted correct readings vetoed.
- Errors it fails to detect.
- Behavior on dark, blurred and partly occluded cells.

Prefer a three-way output:

```text
SUPPORTS / CONTRADICTS / UNINFORMATIVE
```

A missing segment under glare or poor contrast should generally produce `UNINFORMATIVE`, not strong evidence for a different digit. Use a hard veto only when the signal is valid and contradicts the proposed digit. This distinction is essential for dark MT10 crops.

### Avoid overfitting by keeping the initial policy simple

Freeze one policy on development data:

```python
accept = (
    assembly.status == OK
    and not assembly.geometry_ambiguous
    and boundary.is_supported
    and all_tta_readings_agree
    and min_cell_score >= tau
    and max_cell_alt_ratio < 0.5
    and not segment_verifier.valid_contradiction
)
```

Then investigate **one free threshold, `tau`**, rather than fitting a multi-feature meta-classifier on 73 photos. Keep the ambiguity and boundary flags interpretable.

Compare prespecified policies on development data, then audit the chosen policy on new data. Additional vetoes alone can only reduce coverage at a fixed threshold. The intended benefit is that they may allow a lower score threshold **while maintaining measured risk**; that requires fresh evidence.

---

## 7. Three-day plan: prioritize error isolation and trustworthy data

### Stop immediately

1. **Stop the seed lottery, soups and broad augmentation sweeps.** Your existing results do not justify more CPU on those.
2. **Stop using 49/34 to approve promotions.** Retain them as named challenge/regression sets and disclose their development use.
3. **Stop treating higher heat-map scores as progress.** Require fewer errors or better risk–coverage ranking.
4. **Stop treating low locator IoU as sufficient fault attribution.** Use paired crop interventions and boundary/cell visibility.
5. **Stop admitting suspicious short labels without visual review.** The poisoned 2-digit CRYSTAL examples are a targeted audit priority, not a reason to discard every legitimate short reading.

### Day 1: build a reliable diagnostic harness

**First: reconcile m4 and freeze its manifest.** Resolve the 903/912/850 counts; record source, meter/session if known, cluster, label provenance and split. Confirm that the newly verified line boxes are consistent with the reader labels they will be paired with.

**Second: finish the high-risk label review.** Prioritize the 41 short-label examples, then the 19 unfinished boxes, then the remaining unused photos. Owner-verified readings are valuable, but still verify which display line and which pixels they refer to.

**Third: annotate the 38 diagnostic crops.** Add cell boxes/IDs, full visible sequence, fraction boundary, cue visibility and type. Cache heat maps, decoded candidates and image transforms. Build a table that identifies every removed, merged or newly accepted detection.

**Fourth: implement pitch-aware duplicate handling with preserved alternatives.** Compare the original decoder and the three predefined distance settings. Export review montages, not only summary accuracy. Add Kotlin parity cases covering repeated digits, conflicting labels on one cell, faint dots and uncertain boundaries.

Let already-running m4 jobs finish if they are progressing normally; do not launch more seed jobs.

### Day 2: isolate boundary failures and acquire the missing domain

**First: evaluate boundary logic with oracle cells.** This determines whether another detector head would address a real residual problem. Measure CRYSTAL glyph geometry and locator-edge residuals in pitch units.

**Second: test the fixed five-view TTA policy.** Record exactly which errors become abstentions and which correct readings are lost. Add the segment verifier only as a separately logged veto; do not tune a collection of thresholds against the same 73 examples.

**Third: instruct the owner’s collection now, not after training finishes.** Request distinct MT10 meters, paired readable/tilted views and verified readings. Keep a meter-group holdout before inspecting model outputs.

**Fourth: if labels and manifests are clean, run one synth2 reader experiment.** Keep the 50/50 mixture and use the controlled 12.5%-of-total MT10-style contribution. Do not simultaneously change NMS, loss, width and synthesis.

### Day 3: lock a candidate and report what is actually supported

1. Pick the m4 seed using the selection split only.
2. Freeze decoder and boundary policy.
3. Freeze or calibrate the one-parameter gate using the designated calibration protocol.
4. Run the historical 49/34 once as a disclosed challenge report, **not another optimization loop**.
5. Test any new untouched field images, grouped by meter/session.
6. Run the expanded Python/Kotlin parity suite and Android inference test.
7. Publish a per-type table:

```text
type | readable | exact integers | accepted correct | accepted wrong
     | abstained | boundary failures | ghost/missing-cell failures
```

**The best three-day outcome is not a higher aggregate score. It is a decoder that preserves ambiguity, an explicit supported-boundary policy, cleaner task definitions, and new MT10 evidence.** Those changes target demonstrated failure mechanisms. More seeds, confidence rescaling and a larger model do not yet have comparable evidence behind them.
