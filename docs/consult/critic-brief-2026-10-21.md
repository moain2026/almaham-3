# Critic round — attack the proposed plan (2026-10-21)

Below is (A) the original brief and (B) a reviewer's recommendations. You are a second, adversarial reviewer.
Your job: find what is WRONG or risky in (B) for THIS project (tiny CPU models, ~400-1000 labelled photos, no GPU,
owner can label corners/type via a web page, field photos with glare/tilt/handwriting/stickers).
Specifically answer:
1. Is "type-conditional K (integer length)" actually safe? Give concrete cases where it produces confident wrong
   readings (e.g., Crystal readings of 2 vs 3 vs 4 digits with no leading zeros; partial crops; unknown types). Would a
   per-image "last integer digit" keypoint or an "is_decimal" attribute be more robust in those cases? Decide.
2. Is a full LCD-quad + rectification stage justified at 213k params, or is a cheaper fix (rotation/perspective
   augmentation + top-K re-read) enough to pass ±25°? Quantify expected gains if you can from literature.
3. Text-supervised localisation collisions: propose a concrete acceptance test (margin, consistency under jitter,
   minimum digit count) with numbers.
4. Order of work for the next 72 hours with 1 engineer, 2 CPU boxes, owner labelling ~1 photo/5 s: what first, what
   measured gate must pass before the next step. Be ruthless about what NOT to do.
Under 900 words, concrete.

---- (A) BRIEF ----
# Consultation brief — offline Android electricity-meter reader (Yemen), 2026-10-21

## Goal
Field workers photograph the WHOLE meter (for archiving) inside a flexible rectangle; the app must find the LCD and
output the INTEGER kWh reading (no decimals), on-device, <0.5 s, with practically zero wrong-and-confident outputs.

## Current system (all measured, all numbers honest)
- Two CenterNet-lite nets (213k params each, stride 4, ONNX Runtime minimal, 7.7 MB APK):
  locator (256x256 letterbox of the crop → one "reading line" box) → pad 18%/45% → reader (64x448 letterbox →
  11 classes: digits 0-9 + decimal dot, peaks → boxes) → rule-based assembler decides the integer/decimal boundary
  (dot between digits, OR a digit shorter than 0.65x median height, OR a 6-cell default if ≥7 digits in a regular lattice).
- Meter types: TOMAS_SMART/STATIC (6 big integer cells + 2 small decimals, dot visible), TAGADOD, SMART_MT10 (dark LCD),
  EMETER_GREEN (LCD in green PCB), CRYSTAL (2-4 integer digits + 2 decimals of the SAME height, dot ~1 px, then "kWh"),
  OTHER/HPL/CHINT (3-phase, 5-6 digits + 1 decimal same height, label with serial/barcode right below).
- Training data: synthetic LCD renderer (dot drawn large; Crystal decimals drawn SMALL in 80% of samples — mismatch with
  reality), + weak labels from ~368 owner-verified readings (text only, no boxes). Weak boxes are made by running the
  current locator+reader and accepting the photo only when the digit count matches the human text
  ("build" step). Consequence: the locator trains ONLY on photos where it already succeeds (self-training trap).
- Evaluation: 49 field photos (39 readable after owner cleanup) and a frozen human test set of 34 ERP photos.

## Measured failure taxonomy (34-photo human set, latest models: 17/34 correct)
- 5 photos: locator finds NO line (Crystal ×3, Emeter ×2).
- ~6 photos: locator box on the wrong thing: serial barcode label, red sticker/stamp, only the decimal part.
- 8 photos: reader finds all integer digits correctly but APPENDS the decimals (Crystal "355.96"→3559; HPL
  "23746.4"→237464; "46.83"→4068828 with a ghost digit). Decimal cell height / integer height on 498 real crops:
  median 0.99, p95 1.15 → height rule is blind. Dot-class peak on Crystal: 0.07–0.29 (threshold 0.30) → invisible.
- Tilt tolerance measured ≈ ±10°. Beyond that it fails (no rectification stage).
- Owner-verified dataset: CRYSTAL 89, TOMAS_SMART 105, OTHER 61, TAGADOD 52, EMETER 37, TOMAS_STATIC 17, MT10 6.
  More photos can be labelled by the owner (text readings; boxes/corners possible via a web page, ~5 s/photo).
- Compute: 4-core CPU sandbox + 4 vCPU VPS, no GPU (GPU rental possible). Must stay tiny for an arm64 phone.

## Constraints
- No AGPL code in the product. Python lab and Kotlin app are literal mirrors with tests.
- The 49 and the 34 are evaluation-only; never trained or tuned on.

## Questions (answer each with reasoning, cite literature where relevant, be critical of our design)
1. Integer/decimal boundary when decimals have the same height and the dot is ~1 px: what is the most reliable
   learnable formulation for a tiny detector? Options we consider: (a) extra heat-map class "last integer digit";
   (b) per-digit binary attribute head "is_decimal"; (c) predict the dot at higher resolution (stride 2 / upsampled
   head) ; (d) sequence model with explicit <dot> token (CTC); (e) type-conditional priors (known cell layout per
   meter type, classify type first). Which, and why? What failure modes remain?
2. Locator on the whole meter photo: given 368–1000 text-only labels, how to get reliable boxes for training?
   We built "text-supervised localisation" (slide the reader over windows; the window whose reading equals the human
   text gives the box; 25/25 correct on a pilot). Critique it. Alternatives (MIL, point supervision, pseudo-labels from
   a large VLM such as GPT-5 vision, SAM-based LCD segmentation)? How to add hard negatives (barcodes, serial labels,
   stamps) correctly in CenterNet focal loss?
3. Should we add a meter-body detector + LCD 4-corner + legibility head (Laroca et al. 2021, Copel-AMR, CDCC-NET) as a
   middle stage? Is rectification worth it on a 213k-param pipeline, or should rotation/perspective augmentation suffice?
4. Reliability target: the owner wants "0.0 error". Define, for a field app, the right operating point and how to
   measure/calibrate it (selective prediction, confidence from heat-map peaks vs a dedicated head, ECE, accuracy-vs-
   rejection curve). What rejection rate should we expect at 99% / 99.5% precision for this kind of data?
5. Anything we are not seeing? Name the top 3 risks in our plan and the single highest-leverage change.
Be concrete: architectures, loss terms, data recipes, numbers. Keep it under 1500 words.

---- (B) REVIEWER RECOMMENDATIONS ----
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
