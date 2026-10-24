# gpt-6-astra — 2026-10-24 04:24 UTC (171s)

## 1. Selective prediction gate

**Recommendation: use a small, regularized error-ranking model behind explicit rejection rules, then certify a locked threshold on new, meter-disjoint data; your current results do not establish near-zero accepted error.**

### What the existing evidence establishes

The relevant quantity is **selective risk**:

\[
R(t)=P(\hat y\ne y\mid \text{accepted at threshold }t).
\]

This is not ordinary accuracy, and detector heat-map scores are not calibrated probabilities of an exact reading.

For a **prespecified gate**, tested on independent, representative examples, with \(e\) errors among \(n\) accepted readings, the one-sided 95% Clopper–Pearson upper bound is

\[
U=\operatorname{Beta}^{-1}(0.95;e+1,n-e),
\]

with \(U=1\) when all accepted readings are wrong. When \(e=0\):

\[
U=1-0.05^{1/n}.
\]

| Accepted readings, zero errors | Upper bound on accepted error |
|---:|---:|
| 17 | 16.2% |
| 59 | 4.95% |
| 73 | 4.02% |
| 149 | 1.99% |
| 299 | 1.00% |
| 2,995 | 0.10% |

Thus **17 accepted / 0 wrong is weak evidence**, even before accounting for model and threshold selection. The denominator is accepted readings, not all evaluated images.

At 23% coverage, obtaining 299 accepted cases requires approximately **1,300 independent attempts**; 2,995 requires approximately **13,000**. Repeated photos of the same meter are not independent substitutes.

No finite calibration set can establish “never wrong” under arbitrary future conditions. Always abstaining satisfies that rule literally; any useful acceptance policy requires an operational risk tolerance and distribution assumptions. This distinction must be explicit.

### Gate design

Selective classification is the appropriate framework: **Chow (1970), “On Optimum Recognition Error and Reject Tradeoff”; Geifman and El-Yaniv (2017), “Selective Classification for Deep Neural Networks.”**

I would implement two layers:

**Layer 1 — mandatory rejection conditions**

Reject if any of the following holds:

- assembly status is not OK;
- multiple plausible reading lines remain;
- the integer/fraction boundary is unresolved;
- a leading or trailing digit may have been cropped;
- a digit gap or overlap fails the geometry checks;
- a required perturbation check changes the integer string or boundary.

Importantly, **absence of a detected dot is not evidence of absence of a fraction**.

**Layer 2 — learned ranking, not a purported correctness probability**

With this amount of data, start with **four scalar features**, not a flexible classifier:

1. minimum digit peak score;
2. worst competing-class ratio:
   \[
   \max_i \frac{\text{alt}_i}{s_i+\epsilon};
   \]
3. locator line score;
4. maximum normalized deviation from fitted digit pitch.

Use L2-regularized logistic regression predicting *incorrect exact reading*. Standardize features using development data only. Constrain coefficient signs if convenient: higher confidence should not increase predicted error, and worse ambiguity/geometry should not decrease it.

For the initial experiment:

- use a small regularization grid, e.g. \(C\in\{0.01,0.1,1\}\);
- use **three meter-grouped folds**, provided each fold contains enough errors;
- compare against a simple nested threshold rule;
- do not include meter identity or a fixed digit-count lookup;
- evaluate digit count as a fifth feature only if grouped validation demonstrates a benefit. It can learn dataset-specific shortcuts.

The existing `alt` is potentially inadequate: **an alternative that survives cross-class NMS is not the complete competing-class evidence**. Extract the competing digit heat-map scores near each retained center, before destructive NMS, and distinguish:

- classification ambiguity at one digit;
- duplicate detections;
- a missing neighboring digit.

Those are different failure modes.

An optional three-view check could use the original crop and translations of approximately **±1 reader-input pixel**, sampled from the original-resolution image. Require exact integer-string and boundary agreement. Do not count scores from three views as three independent observations. TTA stability does not prove correctness; systematic ghost-segment mistakes can remain stable.

### Logistic regression versus conformal prediction

**Use logistic regression for ranking; do not expect conventional conformal prediction to solve conditional accepted risk.**

Standard conformal prediction controls marginal prediction-set miscoverage under exchangeability. If you accept only singleton sets, its guarantee does not automatically become

\[
P(\text{wrong}\mid\text{accepted})\le\alpha.
\]

The elementary conversion can be as weak as \(\alpha/\text{coverage}\). Moreover, conformalizing a beam containing only reader-generated strings is unsafe if the correct string was excluded by detection or boundary errors.

See **Angelopoulos and Bates (2023), “Conformal Prediction: A Gentle Introduction.”**

If threshold selection and statistical control must use the same calibration set, use an explicitly risk-controlling procedure, such as the hypothesis-testing approach of **Angelopoulos et al. (2021), “Learn then Test: Calibrating Predictive Algorithms to Achieve Risk Control.”** A practical conservative version is:

- predefine a small family of thresholds;
- compute accepted-error bounds for each;
- adjust confidence levels for testing multiple thresholds;
- select the highest-coverage threshold whose bound satisfies the target.

With your sample size this will probably certify little or no coverage at a stringent target. That is a data limitation, not a reason to weaken the statistics.

### Honest validation plan

1. Treat the repeatedly inspected 73-image set as **development data**.
2. Audit whether the 68 validation and 97 field images are meter-disjoint, independently labeled, and already involved in selection.
3. Fit and select the gate using development data only.
4. Freeze the complete pipeline: weights, crop padding, decoder, TTA, and gate.
5. Collect new, consecutively sampled deployment-like attempts on previously unseen meters.
6. Report:
   - coverage over **all attempts**;
   - errors among accepted;
   - one-sided accepted-error bound;
   - separate boundary, digit-swap, and wrong-line errors;
   - descriptive breakdowns by meter family.

Feedback-submitted field photos are not necessarily representative: users may preferentially report failures. Also include unreadable images in the acceptance-safety evaluation. An unreadable image with no trustworthy reference must not silently disappear from the denominator.

---

## 2. Integer/fraction boundary

**Recommendation: first preserve and inspect native-resolution boundary evidence; then add a separate boundary head. Do not use a fixed digit-count prior to manufacture information absent from the image.**

The first experiment should be an **oracle-crop resolution sweep**, not another seed sweep:

- manually crop the full numeric row, including fraction digits and nearby boundary context;
- compare reader heights **64, 96, and 128**;
- sample directly from the original photo, not from the locator’s 256×256 tensor;
- annotate whether the decimal is visible in the native image.

If the dot or another distinguishing cue is genuinely absent at native resolution, several integer/fraction interpretations can be observationally indistinguishable. No head or sequence loss removes that ambiguity. The correct response is abstention.

The preferred ranking is **(c), then (b), then a corrected version of (a), then (d), with (e) only as supporting evidence**. Numerical accuracy gains are **unknown** from the supplied aggregates.

| Option | Expected benefit | Confident-error risk | Data needed | CPU implication |
|---|---|---|---|---|
| **(c) 128×896 input** | Best first test when downsampling destroys a real dot; cannot recover absent native detail | Small artifacts may become false dots; sharpness alone is not correctness | Paired resolution evaluation, verified dot/boundary annotations on difficult cases | Approximately **4× reader convolutional work**, not necessarily 4× wall time; locator unchanged |
| **(b) 1-D boundary head** | Directly represents the task; can exploit spacing, dot, neighboring marks and context | Can learn count/type shortcuts and remain confident without visual evidence | Full-row crops with spatially verified integer endpoint, including variable integer lengths | Usually small incremental work if sharing features; exact latency unknown |
| **(a) “last integer digit” head** | Useful endpoint supervision with minimal architectural change | Same shortcut risk; a literal exclusive 12th class conflicts with digit identity | Verified location of the last integer digit, not merely string length | Negligible incremental head cost relative to backbone, but measure it |
| **(d) CTC with boundary token** | Removes some hand-coded assembly assumptions and models ordering | Language/count priors can suppress unusual valid readings or hallucinate boundaries | Preferably complete sequence transcripts, including fraction and separator | Depends on sequence backbone/head; cannot infer cost from CTC alone |
| **(e) type → count prior** | Can flag implausible outputs or select a validated specialist | Especially dangerous when type and count errors are systematic | Meter-disjoint examples covering variants, lengths and operating states | Potentially inexpensive; safety weakness is informational, not computational |

### Concrete implementation choices

**For (b): use a distribution, not a bare scalar regressor.**

Predict a categorical distribution over horizontal boundary positions, with an explicit **unresolved/no-supported-boundary state**. A scalar L1 prediction can average two plausible endpoints into a meaningless intermediate position.

Possible lightweight design:

- vertically pool reader features;
- apply a short 1-D convolutional head;
- predict boundary logits over the feature-map columns;
- associate the resulting endpoint with a digit boundary.

Do not declare “posterior ≥0.95 means safe.” Calibrate its contribution to the complete selective gate. Boundary peak margin and disagreement under crop perturbation are useful rejection features.

**For (a): make endpoint identity auxiliary.**

“Last integer digit” and “digit 7” are not mutually exclusive labels. Use a **separate heat-map channel/head**, while retaining the digit class. Do not send this auxiliary channel through ordinary cross-class NMS or count it as a competing digit `alt`.

Knowing \(N=\mathrm{len}(\text{label})\) is insufficient unless:

- labels preserve the displayed integer string appropriately;
- displayed digits have been spatially aligned;
- no leading digit was missed;
- the candidate crop includes the intended row.

Otherwise, you train the endpoint on the current reader’s mistakes.

**For (d): specify the transcription problem.**

CTC is **Graves et al. (2006), “Connectionist Temporal Classification.”** CRNN-style scene-text recognition is **Shi, Bai and Yao (2017), “An End-to-End Trainable Neural Network for Image-Based Sequence Recognition and Its Application to Scene Text Recognition.”**

A target such as `123<B>45` requires fraction transcription or a carefully implemented partial-label objective. Training only `123<B>` against an image containing additional digits permits those digits to be absorbed into blanks; it is not equivalent to fully supervising the physical separator.

### Initial data budget

As an engineering pilot—not a statistical guarantee—annotate **100–200 difficult full-row crops**, emphasizing:

- Crystal variable-length readings;
- same-height fractions;
- absent/weak dots;
- non-Crystal look-alikes;
- multiple meters per appearance variant.

Your integer-only locator target also deserves reconsideration. It makes the locator implicitly responsible for a boundary it may be unable to see at 256×256. A clean alternative is:

> locate the complete numeric row at high recall → determine the integer boundary at reader resolution.

Compare both targets on development data. Do not change the locator, decoder and gate simultaneously without ablation.

---

## 3. Using the 612 photos without line boxes

**Recommendation: manually verify boxes for this finite, hard subset; use automatic proposals to reduce annotation time, not reader-label agreement as proof of localization correctness.**

These are not random unlabeled examples. They were **selected by weak-localizer failure**, so they likely contain exactly the coverage gaps you need to fix. More self-training on easy successes will preserve that selection bias.

### Reliability ranking

1. **Manual boxes, assisted by proposals**
2. **Current locator proposals plus human verification**
3. **Expanded weak localization with strict filtering and audits**
4. **MIL/reading-consistency training as a research experiment**

Manual annotation is inexpensive relative to three more days of seed search. At **30–60 seconds per image**, 612 images take approximately **5–10 hours**, excluding adjudication and unusually difficult cases.

Annotate, preferably in one pass:

- complete numeric-row box;
- integer endpoint;
- visible decimal location, if any;
- readability and ambiguity;
- wrong-line risks;
- meter identity or an identity-group key.

For this dataset, review **all ambiguous cases and all automatically matched Crystal cases**, plus a **10–20% random sample** of the remainder.

### Why string equality is not “hard verification”

`reader_output == human_label` is useful evidence, but does not verify the box:

- the same string may appear on another display or register;
- a wide box may contain multiple lines;
- a clipped box may accidentally produce the expected string;
- leading-zero normalization can conceal alignment errors;
- extensive window search creates multiple opportunities for accidental agreement;
- a human reading may refer to another screen state or be normalized differently.

Moreover, the reader generates the hypothesis and supplies the acceptance signal. Its errors are correlated with the pseudo-labeling decision. This is the confirmation-bias problem discussed by **Arazo et al. (2020), “Pseudo-Labeling and Confirmation Bias in Deep Semi-Supervised Learning.”**

### Concrete weak-labeling pilot

For proposal generation only:

- lower the proposal threshold to approximately **0.05–0.10**;
- use **3–4 scales**;
- retain **3–5 spatially distinct candidates**;
- present proposals with decoded strings to the annotator;
- retain “none of these / unreadable” as a valid response.

Those thresholds are recall-oriented starting points, not acceptance thresholds.

If you must use unattended pseudo-labels, require:

- exact agreed string representation;
- one spatially coherent matching candidate;
- no plausible competing line;
- crop-perturbation consistency;
- conservative geometry checks.

Still perform stratified manual audits. Even **100 audited boxes with zero errors only give a 2.95% one-sided upper bound** under independent representative sampling. Given that there are only 612 images, full verification is preferable.

MIL or reading-consistency loss can lock onto discriminative fragments or spurious regions rather than the full object. This is a general weak-localization failure, discussed in **Choe et al. (2020), “Evaluating Weakly Supervised Object Localization Methods.”** It is not the first investment I would make here.

---

## 4. Ghost-segment confusions

**Recommendation: prioritize real hard digit crops and measured on/off-segment synthesis; treat a segment head as an interpretable auxiliary experiment, not a safety guarantee.**

The likely domain gap is not “seven-segment font versus another font.” It is the joint distribution of:

- active-segment contrast;
- visible inactive-segment contrast;
- glare and viewing angle;
- background texture;
- digit scale and blur;
- segment-to-segment variation.

Rendering 24,000 clean seven-segment strings can leave that distribution almost untouched.

### Priority order

**1. Build a real confusion set**

Collect a development set of approximately **200–500 verified difficult digit crops**, distributed across meters rather than many adjacent photos of one meter.

Include:

- the cited confusions;
- correct but low-contrast digits;
- high-confidence wrong digits;
- inactive segments that are unusually dark;
- weak active segments.

Maintain an untouched, meter-disjoint subset. Do not turn the frozen challenge images into training examples without retiring them as evaluation.

**2. Fit synthetic ghosting to real measurements**

For each synthetic digit, render all seven physical segments, but sample active and inactive appearance separately:

- contrast distributions;
- per-segment deviations;
- spatial illumination gradients;
- blur and downsampling;
- glare/saturation;
- weak or partially occluded active segments.

Estimate the ranges from real crops. Do not choose arbitrary ghost opacity and assume realism.

A useful controlled ablation is:

- existing synthesis;
- synthesis with inactive segments;
- inactive segments plus weak-active-segment variation;
- the preceding setup plus hard real examples.

The general value of synthetic text training is established by **Jaderberg et al. (2014), “Synthetic Data and Artificial Neural Networks for Natural Scene Text Recognition.”** It does **not** establish efficacy for LCD ghosting.

**3. Compare normalization carefully**

Test raw grayscale against one restrained local-normalization variant, retaining raw intensity if adding a second channel.

Do not automatically apply aggressive CLAHE, thresholding or sharpening. They can amplify inactive segments and destroy the active/inactive contrast distinction.

**4. Add a seven-segment auxiliary head**

Seven on/off logits per digit can:

- expose which segment caused a confusion;
- support explicit ambiguity rejection;
- impose useful representation structure.

But segment targets derived solely from digit labels add no new annotation information: they are a deterministic recoding of the class. They may help inductive bias, but can also confidently reproduce the same mistake.

A stronger version uses verified segment visibility/ambiguity on a small real subset. For example, explicitly distinguish an uncertain lower-left segment in a 5/6 case rather than forcing it into a clean binary target.

Do not force every noisy segment vector to the nearest valid digit code. That guarantees an answer precisely when abstention may be needed.

### Published ghosting-specific evidence

**Unknown:** I do not know a peer-reviewed result demonstrating a transferable reduction of these particular ghost-segment errors under a closely matching mobile LCD setup. I would not claim a published gain for an auxiliary segment head here.

Use **exact-reading accepted error**, not only digit accuracy, as the primary endpoint. A method that improves average digit accuracy while making its remaining 5→6 errors more confident is a regression for this product.

---

## 5. Model selection with tiny evaluation sets

**Recommendation: stop choosing among dozens of seeds on the same challenge sets; use grouped development folds, one trajectory-level averaging method, and one fresh locked evaluation.**

The reported seed variation measures training randomness **conditional on these particular images**. It does not measure uncertainty over new meters.

Searching 27 locators and 31 readers and selecting a favorable zero-error result creates a multiple-comparison problem. “Only four seeds had zero accepted errors” is evidence that the current gate is unstable, not a reason to select one of those four and call it safe.

### Weight averaging

Your uniform soups combine separately trained seeds. This is not automatically justified.

**Wortsman et al. (2022), “Model Soups”** primarily studies fine-tuned models with a common pretrained origin and compatible solutions. Networks trained independently from scratch can have different channel permutations and incompatible parameter-space locations.

Thus non-monotonic soup results are unsurprising. Also check whether batch-normalization statistics were recomputed after averaging.

Prefer:

- **EMA within one training trajectory**, or
- **SWA within one trajectory**, with an appropriate schedule and normalization-statistic update.

SWA: **Izmailov et al. (2018), “Averaging Weights Leads to Wider Optima and Better Generalization.”**

A concrete low-cost experiment:

- EMA decay **0.995**, giving roughly a 200-update averaging scale;
- start after approximately **500 updates**;
- compare against the ordinary final checkpoint;
- refresh normalization statistics if the implementation requires it;
- select the recipe on grouped development data, not TH34.

This is a proposed starting point, not an established optimal decay for your models.

### Better selection metrics

Locator IoU50 is too coarse. Track:

- integer-row/full-row recall, according to the chosen target;
- first- and last-integer-digit containment;
- wrong-line selection;
- fraction intrusion into the reader crop;
- end-to-end exact reading;
- coverage and error at a **fixed development gate**.

A box can pass IoU50 while removing the first digit or adding the fraction. Your saturated locator validation metric is therefore unsurprising.

Use **three meter-grouped folds** to compare a small number of recipes. An oracle-crop reader experiment should accompany this: it separates localization failures from recognition/boundary failures.

### Two-model inference

If latency allows, two readers with exact-string **and boundary** agreement can be a useful rejection mechanism. But:

- agreement is not independent evidence;
- shared ghosting errors may agree;
- averaged logits can increase confidence in the same error.

Keep each model’s ambiguity checks. Benchmark a shared-locator/two-reader configuration: this adds roughly one reader inference, not necessarily twice the entire app latency.

EMA is common in detector training; inference ensembles are common in benchmarks but less attractive under strict mobile latency. Neither supplies a risk guarantee.

---

## 6. Training efficiency on eight CPU cores

**Recommendation: benchmark kernel/thread configurations once, then spend compute on targeted ablations and better data—not additional blind seed searches.**

Whether **0.4 seconds/step** is near the hardware floor is **unknown** without the CPU model, convolution shapes and profiler trace. Parameter count is a poor predictor of CPU training time.

First reconcile the timing:

\[
3000\times0.4\text{ s}=1200\text{ s}=20\text{ min}.
\]

Adding 0.03 seconds of non-overlapped data time per step gives about **21.5 minutes**, not 50. Different machines may explain this, but otherwise inspect evaluation, checkpointing, preprocessing and logging.

### Benchmark matrix

On each four-core machine separately, test:

| Setting | Values |
|---|---|
| PyTorch intra-op threads | 1, 2, 4 |
| Concurrent jobs | 4×1 thread, 2×2 threads, 1×4 threads |
| Memory layout | contiguous, `channels_last` |
| Execution | eager, `torch.compile` |
| Data-loader workers | 0, 1, 2 |

Use fixed shapes, approximately **50 warm-up steps and 200 timed steps**. Measure complete training-step throughput, memory, startup/compile time and sustained behavior.

Prevent oversubscription:

- set inter-op threads explicitly, usually **1** for this benchmark;
- coordinate `OMP_NUM_THREADS`/`MKL_NUM_THREADS`;
- disable extra OpenCV threads;
- remember each concurrent process may create its own thread pools.

Four sandbox cores plus four VPS cores are not one eight-core shared-memory machine. Independent experiments across the two hosts are the natural arrangement.

### Likely wins and non-wins

- **`channels_last`:** worth testing with oneDNN convolutions; gains depend on shapes and conversion overhead.
- **`torch.compile`:** potentially useful, but small fixed-shape CPU models can still lose to compilation overhead or graph breaks. Include compile cost when comparing 3,000-step jobs. See **Ansel et al. (2024), “PyTorch 2.”**
- **Data caching:** useful if rendering or decoding is on the critical path. Your stated 0.03 seconds is only about 7% of step time, so it cannot explain a major acceleration.
- **Grayscale synthetic cache:** 27,000 images at 64×448 occupy about **0.77 GB as uint8**, before metadata and extra views. Avoid expanding everything to float32 unnecessarily.
- **Mixed precision:** do not pursue it on a Xeon where it is slower. Native BF16 capabilities matter.
- **Batch 64 with half as many steps:** not an equivalent optimization. It halves parameter updates and changes optimization noise. Benchmark it only as a new training recipe.
- **Longer schedules:** justify with grouped validation and learning curves, not parameter count.

Use total completed useful experiments per machine-hour as the optimization objective. Given the observed seed results, data and objective changes have much higher expected value than another 30 initializations.

---

## 7. Practices that currently undermine trustworthiness

**Recommendation: retire the repeatedly used “frozen” sets as final tests, rebuild meter-disjoint manifests, and distinguish observational results from safety claims.**

### A. Photo-key splitting is not sufficient

Different photos of the same meter share:

- layout and digit spacing;
- scratches, glare patterns and background;
- possibly the same reading;
- acquisition conditions.

A photo-key split can substantially overestimate deployment generalization.

Split by **physical meter**, and preferably acquisition session. Audit the old ft6 data, m3, ERP, owner evaluation and field feedback jointly for overlap and near-duplicates.

Report separately:

- unseen meters of known families;
- genuinely new variants/families;
- repeated use of a previously seen meter, if that is a relevant deployment scenario.

### B. “Never trained on” does not mean untouched

If TH34 and the owner photos repeatedly determine seed choice, soup size, synthesis design or thresholds, they participate in model selection.

They remain valuable challenge sets. They are not an unbiased final assessment.

This is the model-selection bias discussed by **Cawley and Talbot (2010), “On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation.”**

### C. A and B are paired views, not extra independent examples

Mode A and mode B on one photo share the same underlying meter and reading. Do not pool them as independent observations for confidence bounds.

### D. Your denominators need an audit

The reported m3 type counts sum to **528**, not 531.

The listed types among the 612 failed-localization photos sum to **441**, leaving 171 unspecified.

A 15% split of 531 photos is approximately 80, not 68; grouping, exclusions or deduplication may explain that, but the accounting must be explicit.

Also clarify whether the 73 examples are the **39 readable owner cases plus TH34**. If so, that excludes the ten unreadable owner cases from the quoted safety assessment.

Create one immutable manifest with:

- image and source identifiers;
- meter group;
- split;
- label provenance;
- label normalization rules;
- readability;
- inclusion/exclusion reason;
- whether the image has influenced model or gate selection.

### E. Saturated IoU50 does not validate the pipeline

It hides the boundary errors that matter and may coexist with identity leakage. Replace it as the primary model-selection criterion, not merely lower the IoU threshold.

### F. Human readings do not automatically validate derived localization labels

A reader-matching weak-labeler can create a dataset of examples that the existing reader already handles. The 612 failures are evidence of that filtering mechanism.

Document exactly which labels and boxes were human-verified.

### G. The synthetic ratio is a hypothesis, not a standard

A 50/50 real/synthetic mix is not inherently wrong. Neither is owner-example weighting. But both alter the training distribution, and neither is supported by the Crystal result.

Run a small controlled ratio study—e.g. **0%, 25%, 50% synthetic**—with matched total updates and grouped development evaluation. Distinguish better synthesis from simply more synthesis.

### H. The confidence calculation omits whole-string failure modes

The minimum score over detected digits does not penalize:

- a digit that was never detected;
- an incorrect integer/fraction boundary;
- confidently reading another line;
- a common-mode error across TTA views.

Therefore, raising `min_conf` alone cannot solve the observed problem. The failure taxonomy already demonstrates this.

### I. Deployment claims require device measurements

“0.21M parameters” does not establish <100 ms. Measure on the target Android CPU:

- warm p50 and p95 end-to-end latency;
- initialization separately;
- crop/resize, ONNX execution and assembly separately;
- configured thread count;
- sustained/thermal behavior;
- every proposed high-resolution or multi-reader path.

Quantization, resolution changes, decoder changes and different locator weights can shift the score distribution. Each materially changed pipeline needs its gate revalidated.

### Immediate order of work

1. Audit identities, labels and denominators.
2. Box the failed-localization photos and annotate difficult boundaries.
3. Run native-resolution, oracle-crop and ghosting ablations.
4. Compare a few recipes with meter-grouped development folds.
5. Freeze the complete pipeline and gate.
6. Collect a new representative acceptance-safety set.

Until then, the defensible statement is **“zero observed errors among 17 accepted examples under this evaluation”**, not “0.0 error achieved.”
