# gpt-5.2 — 2026-10-21 06:43 UTC (96s)

## 1) Integer/decimal boundary when decimals are same height and dot ≈ 1 px

When the decimal dot is effectively invisible and decimal digits have the same glyph size as integer digits, the boundary is **not reliably recoverable from local per-digit appearance**. It becomes a **layout/type** problem (how many decimals this meter format has; where “kWh” sits; fixed cell lattice), not a “find the dot / find a shorter digit” problem. Your measured stats (height ratio median 0.99; dot peak 0.07–0.29) already prove the current cues are non-identifying.

**Best formulation for a tiny on-device system:** **(e) type-conditional priors**, plus a very small boundary head for “how many integer digits” (equivalently “last integer digit index”). Concretely:

- Add a lightweight **meter-type classifier** (6–10 classes incl. “unknown”) on the *rectified LCD crop* (or on the full meter crop if LCD not found yet). This can be a ~50–150k-param CNN (MobileNetV3-small 0.35–0.5 style) trained with strong augmentation.
- For each type, store a prior: `{num_decimals, max_integer_digits, expected lattice}`.
- Add a head predicting **integer_length K** (0..8) or **boundary index** (0..N-1). This is essentially your option **(a)** (“last integer digit”) but implemented as a **global classification head** on the shared features, not another heatmap class that competes with digits.

Then parse as:
1) recognize digits (detector or sequence recognizer),
2) choose K using `{type prior + boundary head}`,
3) output only first K digits.

Why this over the other options:

- **(c) higher-res dot**: stride-2/upsampled heads help for tiny objects, but the dot is near the quantization/compression/noise floor. Even if recall improves, you still have cases where dot is absent/occluded/glared → catastrophic boundary errors remain.
- **(b) per-digit “is_decimal” attribute**: without dot/height cues, this becomes an ill-posed per-instance classification; it will overfit spacing artifacts and fail under tilt/perspective.
- **(d) CTC with explicit `<dot>`** (Graves et al., 2006; CRNN Shi et al., 2016): good for recognition, but does not magically solve “dot not visible”. If trained to emit `<dot>`, it will be underconfident/unstable; if trained without dot, it will still sometimes include decimal digits unless you explicitly supervise boundary or crop integer-only.
- **(a) extra heatmap class “last integer digit”**: workable, but only if (i) you have robust supervision for that “last-integer” keypoint (derivable from text + digit ordering), and (ii) the LCD is rectified so ordering is stable. I’d prefer **global K** because it’s cheaper and less sensitive to local peak noise.

**Remaining failure modes even with type priors:**
- **Unknown/novel meter layouts** (or firmware variants) where decimal count differs.
- **Partial LCD visibility** (crop cuts off rightmost digits/“kWh”) → K becomes ambiguous.
- **Recognition missing digits**: if one integer digit is missed, “total_digits − decimals” logic breaks unless you model blanks explicitly (CTC helps here).

Pragmatic mitigation: if type is “unknown” or K confidence is low → **reject** (see Q4).

---

## 2) Locator training with 368–1000 text-only labels: critique + alternatives + hard negatives

Your “slide the reader, pick the window whose reading equals the human text” is a strong idea: it’s basically **discriminative search with text supervision**. It resembles weak supervision / MIL-style localization but using an exact-match constraint.

**Critique (what can go wrong):**
1) **Collision risk**: wrong region can coincidentally produce the same integer string (especially short readings like 2–4 digits). This silently poisons training.
2) **Bias toward easy cases**: if the reader only works when LCD is clean/upright, then the found boxes come from the easy subset → same “self-training trap” you already identified.
3) **Compute + multiplicity**: sliding windows over full-res images is expensive; worse, there may be multiple near-matches with different boxes (instability).
4) **Exact match is brittle**: a single OCR digit error yields “no box”, dropping hard examples.

**How to keep it, but make it safer:**
- Use a **score, not a boolean**: maximize `log P(text | window)` (or a surrogate: sum of digit confidences aligned to the target) rather than exact match.
- Require **spatial stability**: the chosen box must remain the argmax under small jitters/scales/rotations of the image (consistency regularization; cf. “Mean Teacher” Tarvainen & Valpola 2017 conceptually).
- Add a **margin constraint**: accept pseudo-box only if best score exceeds second-best by Δ.
- Prefer longer readings for pseudo-labeling; for 2–4 digit meters, collision probability is high → require extra checks (presence of “kWh”, lattice pattern, etc.).

**Alternatives / complements:**
- **Pay for a small amount of real geometry labels** (highest ROI): 300–800 images with LCD quadrilateral (4 corners) + type. At ~5 s/photo, this is a few hours and breaks the bootstrap loop immediately.
- **CAM-style weak localization** (Oquab et al., 2015; Zhou et al., 2016): train a classifier “contains this reading?” is not feasible (too many classes). But you *can* train “LCD present + type” and use CAM to propose regions; then refine with box regression.
- **MIL** (Ilse et al., 2018 attention MIL): treat windows as instances, reading-score as bag label. Works, but heavier engineering than your current approach.
- **SAM segmentation** (Kirillov et al., 2023): can propose LCD-like rectangles, but will fail under reflections and may segment irrelevant rectangular stickers. Use only as *proposal generator* + human confirm; don’t trust it as ground truth.
- **VLM pseudo-labels (GPT-class vision)**: useful for bootstrapping *candidates*, but treat as noisy labels; you’ll still need human verification. Also expect systematic bias on dark LCDs / glare.

**Hard negatives (barcodes/serial labels/stamps) in CenterNet:**
Right now they’re “background”, but your model confuses them with the target, meaning the features are too similar under your loss.

Two robust options:
1) **Multi-class locator**: add explicit classes: `{LCD, barcode/serial-label, stamp/sticker}`. CenterNet (Duan et al., 2019) naturally supports multi-class heatmaps; this forces representational separation.
2) **Two-stage “LCDness” verifier**: after locator proposes top-K boxes, run a tiny binary classifier on the crop: `is_LCD` (trained with mined negatives). This is often cheaper than making the detector perfect, and improves selective rejection.

---

## 3) Add meter-body + LCD 4-corner + legibility head? Rectification vs augmentation

Given your measured tilt tolerance (≈±10°) and “locator finds no line / wrong thing” failures, **rectification is worth it**, but you don’t need a heavy middle stack.

Minimal recommended change:
- Replace “reading-line box” with **LCD quadrilateral (4 corners)** + **legibility score** in one tiny network.
- Warp to a canonical rectangle (homography) on-device (OpenCV or custom). Cost is small relative to CNN inference.

This is essentially using the idea of geometric normalization (STN: Jaderberg et al., 2015; many scene-text rectifiers like RARE 2016 / ASTER 2018 show why rectification reduces recognition burden).

Why augmentation alone is unlikely to match rectification here:
- Perspective distortion changes character widths/spacing nonlinearly; your digit detector + rule assembler is sensitive to ordering and spacing.
- Rectification makes downstream parsing (including “K last integer digits”) far more stable and reduces the need for complex heuristics.

If labeling corners is painful: label **tight LCD box** first (cheap), then add corners for a smaller subset and train corner head with mixed supervision (box-only images contribute only box loss).

---

## 4) “0.0 error”: operating point, calibration, and expected rejection

You want **practically zero wrong-and-confident outputs** → treat this as **selective prediction** (Chow, 1970; risk–coverage curves in Geifman & El-Yaniv, 2017).

**Define outputs as:**
- `ACCEPT(reading)` only if confidence ≥ τ
- else `REJECT` and ask for retake / manual entry

**Confidence should not be raw peak height alone.** Use a calibrated composite:
- `c = min( c_locator, c_legibility, c_recognition, c_consistency )`
Where:
- `c_locator`: detector probability / margin vs 2nd-best proposal
- `c_legibility`: dedicated head predicting readable/unreadable (blur/glare/occlusion)
- `c_recognition`: for digits, use margin between top1/top2 per position; for CTC, use normalized sequence logprob
- `c_consistency`: checks like monotonic left-to-right ordering, plausible digit count for the type, no overlaps, etc.

**Calibration:**
- Use **temperature scaling** (Guo et al., 2017) or isotonic regression on a held-out *calibration* set (not your frozen 49/34). Calibrate `P(correct | c)`.
- Report:
  - accuracy vs rejection (coverage) curve,
  - precision@coverage targets (e.g., 99%, 99.5%),
  - ECE/Brier on accepted predictions.

**What rejection rate to expect:** for real-world reflective LCDs + multiple meter types, hitting **99.5% precision** commonly costs **high rejection early on**. Without your exact distribution it’s guesswork, but expect **30–70% rejection** initially if you truly enforce near-zero errors; with rectification + type priors + legibility gating, you may get into **10–30%** on “normally captured” photos. (The honest way: measure the risk–coverage curve and pick τ by business cost.)

Also: claiming “0 errors” needs statistics. If you observe 0 wrong among N accepted samples, the 95% Clopper–Pearson upper bound is roughly ~3/N. So you need **hundreds to thousands** of accepted test cases to justify “effectively zero”.

---

## 5) Top 3 risks + single highest-leverage change

**Top risks**
1) **Label bias / self-training loop**: training localization only on already-successful cases will keep brittleness on Crystal/Emeter/dark LCDs and non-upright shots.
2) **Intrinsic ambiguity of decimal boundary**: if you don’t hard-code/learn per-type decimal count (or K), you will keep appending decimals with high confidence.
3) **OOD + glare = confident wrong**: reflective covers, motion blur, partial LCD, extreme angles, and unseen meter variants will produce plausible digit detections unless you add legibility + rejection.

**Single highest-leverage change**
Collect **~500–1000 real photos** with **(a) LCD quadrilateral**, **(b) meter type**, **(c) integer reading** (no digit boxes needed), and retrain as:

1) LCD quad detector + legibility (tiny)
2) rectify
3) recognition + boundary using **type-conditioned K**

This breaks the bootstrap trap, fixes tilt, and makes decimal handling a prior-driven decision rather than fragile dot/height heuristics—all while staying tiny and CPU-friendly.
