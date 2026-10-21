# gpt-5 — 2026-10-21 06:55 UTC (105s)

Below is a concrete plan aimed at meeting “offline, <0.5 s, tiny, near-zero confident errors” with the data and constraints you have.

1) Decimal boundary when decimals are same height and the dot is ~1 px

Recommendation: switch the reader to a tiny sequence recognizer (CRNN + CTC) and add an explicit boundary head trained from the text label. Concretely:
- Backbone: depthwise-separable CNN (MobileNetV3-Tiny style) with anisotropic strides (downsample height aggressively to 8–12 px, keep width high), then 1–2 BiGRU layers (hidden 64–96).
- Heads:
  - CTC sequence head over tokens {0–9, '.'} (Graves et al., 2006/2009; CRNN: Shi et al., 2016).
  - Boundary head: distribution over “break positions” between tokens (including “no-decimal” class). Train with cross-entropy: the index right after the dot in the label is the gold break. This learns the integer/decimal split even if the dot is visually missing.
- Decoding: take the most probable CTC sequence, then apply the boundary head to split; ignore everything right of the predicted break when outputting the integer.

Why this over the options:
- (a) “last integer digit” class and (b) per-digit is_decimal: both rely on local appearance; with same-height decimals, there’s no reliable per-glyph cue. You need sequence context.
- (c) Higher-res dot detection helps, but a 1 px low-contrast dot at 64 px height crops is fragile; you don’t want correctness hinging on a single pixel.
- (d) CTC gives global context and is the workhorse in OCR when spacing/appearance is ambiguous (Shi et al., 2016).
- (e) Type priors are valuable as a secondary cue; use them to regularize the boundary head (see below), not as a hard rule.

Add a light type-conditional prior: add a type classifier on the meter or LCD crop, then a learned prior P(break | type). Combine by adding log-priors to the boundary logits (only if type prob > τ, e.g., 0.8). This handles stable patterns (e.g., TOMAS 6+2), while letting data override on atypical layouts.

Remaining failure modes:
- Dot and break both absent and no stable type prior (e.g., obscured decimals). Boundary head may waffle; treat as low-confidence and reject.
- CRYSTAL with ultra-tiny dot and tight kerning; the CTC head may hallucinate digits; mitigated by boundary head and by including “kWh” suffix as an auxiliary token stream if it fits the crop.

Model size: with DW convs and 2×96 BiGRU you can stay ≈180–230k params. Inference: <10 ms on 64×448 on mid-range ARM if optimized (NNAPI, int8).

2) Training the locator with only text labels (getting reliable boxes)

Your “text-supervised localisation” (slide the reader and pick the window matching the human text) is a good start but has pitfalls:
- Confirmation bias: relies on your current reader; if the reader fails on decimals (your dominant error), you won’t harvest those boxes (self-training trap).
- Spurious matches: short substrings (e.g., “46”) will appear on serial labels/barcodes; you’ll collect wrong boxes.
- Search bias: windows/strides define what’s findable; near-misses won’t be learned.

Make it robust with an EM-style, MIL training loop:
- Candidates: generate a dense set of LCD-like proposals per image: CenterNet locator proposals (even wrong ones), plus sliding windows, plus SAM boxes prompted by “screen” (SAM: Kirillov et al., 2023, Apache-2.0; run offline in lab only), plus simple color/edge heuristics for “dark-on-light 7-seg clusters”.
- Reader scoring: run the CTC reader on each candidate at 2–3 scales. Score = normalized negative CTC loss to human label (not only exact match). Also penalize if the boundary head disagrees with the label’s dot index.
- MIL selection: for each image, select top-1 (or top-k) candidate with lowest CTC loss; treat it as positive, all others as negatives. Train the locator to reproduce the selected positive (CenterNet heatmap/object size) while suppressing negatives.
- Iterate: retrain locator on pseudo-boxes, rescore candidates with the improved locator+reader, and repeat 2–3 rounds. Keep only samples whose best candidate is well separated (loss margin > δ) to limit error propagation. Manually spot-check 50–100 borderline cases to anchor the loop.

Hard negatives (barcodes, serial labels, stamps):
- Harvest them automatically: all non-selected top candidates per image are labeled hard negatives; also detect 1D barcodes via ZXing (Apache-2.0) and add padded boxes around them as explicit negatives.
- In CenterNet (Zhou et al., 2019), negatives are every pixel not near a GT center. Upweight negatives inside mined hard-negative boxes by a factor λ (e.g., 3–5) in the focal loss. Do not “ignore” them; make them true negatives so the network learns to suppress peaks there.
- Optionally, add a second class “label region” if you have enough examples; multi-class heatmap helps the net route evidence and reduces confusion between LCD vs label.

Alternatives you can test quickly:
- Weakly supervised MIL loss: max over candidate scores per image vs label sequence (non-diff through argmax, but you can use softmax-pool to backprop).
- VLM pseudo-labels: use a big VLM (e.g., GPT-5V) once, offline, to click the LCD/reading region on a few hundred images; then filter and distill. Licensing is fine if used for labeling only, not shipped.
- SAM for LCD segmentation with a “screen” prompt + size/aspect filters; then box the largest plausible LCD. Works surprisingly well on smart meters; expect 70–85% good boxes after basic heuristics; use the reader loss to filter.

3) Add a meter-body detector + LCD 4-corner + legibility head? Is rectification worth it?

Yes, add geometric rectification. Your measured ±10° tolerance is too tight, and many of your locator errors are “wrong object.” A tiny 4-corner LCD head is the highest ROI for robustness:
- Replace your current locator head with a multitask head: heatmap for LCD center, box size, and 4 corner offsets (or a rotated box angle). Regress corners with Wing/Charbonnier loss to tolerate label noise.
- After detection, rectify the LCD via a homography and feed the rectified strip to the sequence reader. Add a small “legibility” head (binary) on rectified crops to veto low-contrast/blurred inputs (Laroca et al., 2021; CDCC-NET-style pipelines use ROI + rectification + legibility with marked gains).
- Data: hand-label 200–400 LCD quadrilaterals across types; augment with perspective/tilt ±40°, motion blur, reflections. This will extend your tilt tolerance massively and reduce confusion with barcodes/labels.

With careful design, the corner head adds <50k params and negligible runtime. Rectification beats trying to learn perspective invariance in a 213k net. Augmentation alone did not suffice in your current setup; the empirical ±10° cap is the tell.

4) “0.0 error” in the field: operating point, measurement, calibration

Define a selective prediction protocol:
- Per-sample confidence q composed of:
  - q_ctc: mean per-character log-prob of the Viterbi CTC path (length-normalized).
  - q_break: margin between top-2 boundary logits.
  - q_loc: locator peak value normalized by local heatmap statistics, plus geometric sanity (aspect ratio, corner convexity).
  - q_consistency: agreement between two perturbations (flip TTA; small gamma/brightness jitter). If decoded integers differ, penalize heavily.
- Train a tiny logistic regressor (or isotonic) on a dev set to map features → calibrated acceptance probability p̂. Calibrate each component with temperature scaling first (Guo et al., 2017). Report ECE and reliability diagrams.

Evaluation/monitoring:
- Report accuracy vs coverage (risk–coverage curve; SelectiveNet: Geifman & El-Yaniv, 2019). Target: at the chosen threshold τ, precision ≥99–99.5% (1–0.5% wrong among accepted).
- Expectation for this domain after fixes above:
  - Before fixes: 99% precision likely requires >50% rejection (your current errors are frequent and systematic).
  - After adding 4-corner rectification, MIL-trained locator, and CTC+boundary reader: 99% precision at 20–30% rejection is realistic; 99.5% at 30–45% rejection. On easy types (TOMAS 6+2), you can be at 90%+ coverage with 99% precision; CRYSTAL/OTHER will dominate rejections.
- Field UX: if rejected, prompt the user to reframe (on-screen LCD polygon overlay + “move closer/tilt less”). This is the cheapest way to get to low-error in practice.

5) What you’re not seeing: top risks and highest-leverage change

Top 3 risks
- Self-training bias in the locator: your weak boxes come only from images the current system already solves. This explains poor generalization to CRYSTAL/EMETER and “wrong-object” locks.
- Data realism gap in the dot/decimals: synthetic renderer draws a large dot and (for CRYSTAL) small decimals much of the time; reality is 1 px dot and same-height decimals. This directly caused your main reader error (decimals appended).
- No geometric correction: ±10° tolerance is not field-robust. Perspective/tilt and glare will keep biting you without rectification, yielding both locator and reader errors.

Single highest-leverage change
- Replace the reader with a tiny CRNN+CTC and add an explicit boundary head, and pair it with a 4-corner LCD rectification in the locator. This combination directly removes your dominant failure (decimal appending) and expands tolerance to pose/lighting, with minimal param increase. It also enables reliable text-supervised learning (CTC loss) to break the self-training trap for the locator.

Concrete implementation checklist (next 4–6 weeks)
- Reader v2 (≈200k params): DW-CNN → BiGRU(96)×2 → CTC(11 classes) + boundary head (positions 0..N, N≈12). Train on: improved synthetic (true 1 px dot distribution; decimals same height in ≥80% for CRYSTAL; add “kWh” tokens for relevant types) + all real crops with only text labels (optimize CTC). Add random dot erasure to force boundary head learning.
- Locator v2 (≈230k params total): CenterNet-tiny backbone + heads: heatmap, size, 4 corners. Train with MIL pseudo-boxes + 300 manual corner labels. Upweight focal negatives in mined barcode/label regions (λ=3–5). Add strong brightness/glare/tilt aug.
- Rectify and feed reader. Add legibility head (binary CE) trained to predict acceptance vs rejection label from dev set thresholds.
- Confidence: compute q_ctc, q_break, q_loc, q_consistency; temperature-scale; logistic fuse; choose τ to hit 99–99.5% precision on a dev set that excludes the 49+34 eval sets.

Citations
- CenterNet: Objects as Points (Zhou et al., 2019)
- Focal Loss (Lin et al., 2017)
- CTC (Graves et al., 2006/2009)
- CRNN for text (Shi, Bai, Yao, 2016)
- Spatial Transformer Networks (Jaderberg et al., 2015) for rectification if you prefer learned TPS
- Laroca et al., 2021 (AMR pipelines using detection + rectification + legibility)
- SAM (Kirillov et al., 2023) for offline pseudo-labeling
- Calibration: On Calibration of Modern Neural Networks (Guo et al., 2017)
- Selective prediction: SelectiveNet (Geifman & El-Yaniv, 2019)

If you do only one engineering sprint: deliver the rectified CRNN+boundary reader and re-bootstrap the locator with MIL and mined hard negatives. That alone should eliminate most decimal appends and “wrong object” locks, and give you a workable acceptance/rejection curve for the field.
