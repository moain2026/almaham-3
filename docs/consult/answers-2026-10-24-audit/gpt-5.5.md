# gpt-5.5 — 2026-10-24 08:47 UTC (246s)

## Q1. Ghost detections

**Rank for immediate 0-wrong selective reading: `a` > `c` > `b` > `e` > `d`, with one caveat: implement `a` as class-agnostic lattice/same-cell suppression, not just pairwise IoU NMS.** The current failure is not “too many low-confidence random detections”; it is “more than one detection per physical digit cell.” IoU NMS is the wrong geometry because two boxes can sit side-by-side in one LCD cell with low IoU. A class-agnostic 1-D same-cell NMS/clustering along x is the lowest-risk decode fix. Keep suppressed detections as ambiguity evidence: if a suppressed different-class candidate has score ratio `suppressed / kept > 0.65–0.8`, return `EMPTY`, not a confident reading.

**Implement 1-D same-cell suppression before `assemble.py`, excluding the dot class.** Do not estimate pitch from nearest-neighbor distances, because ghosts will bias the pitch downward. Estimate pitch from a robust lattice fit or from the mode of plausible pairwise x-distances. Then suppress/cluster detections whose centers are closer than about `0.50–0.65 * pitch`.

```python
DIGIT_CLASSES = set(range(10))
DOT_CLASS = 10

def estimate_pitch(dets, min_score=0.25):
    xs = np.array(sorted([
        d.cx for d in dets
        if d.cls in DIGIT_CLASSES and d.score >= min_score
    ]), dtype=np.float32)
    if len(xs) < 3:
        return None

    ws = np.array([
        d.w for d in dets
        if d.cls in DIGIT_CLASSES and d.score >= min_score
    ], dtype=np.float32)
    med_w = np.median(ws) if len(ws) else None

    # Pairwise spacings; avoid nearest-neighbor-only because ghosts dominate NN.
    dxs = []
    for i in range(len(xs)):
        for j in range(i + 1, min(i + 8, len(xs))):
            dx = xs[j] - xs[i]
            if dx > 2:
                dxs.append(dx)
    dxs = np.array(dxs, dtype=np.float32)
    if len(dxs) == 0:
        return None

    if med_w is not None and med_w > 0:
        # For 7-seg digits, bbox width is usually ~0.45-0.75 pitch.
        lo, hi = 0.9 * med_w, 2.8 * med_w
        dxs = dxs[(dxs >= lo) & (dxs <= hi)]
    if len(dxs) == 0:
        return None

    # Histogram mode, 2 px bins in reader input coordinates.
    bin_w = 2.0
    bins = np.arange(dxs.min(), dxs.max() + bin_w, bin_w)
    hist, edges = np.histogram(dxs, bins=bins)
    p0 = 0.5 * (edges[np.argmax(hist)] + edges[np.argmax(hist) + 1])

    # Refine with a small RANSAC-like lattice score.
    best_p, best_score = p0, -1e9
    for p in np.linspace(0.8 * p0, 1.2 * p0, 41):
        if p <= 1:
            continue
        # Score how well points fall near some phase modulo p.
        phases = np.mod(xs, p)
        for phase in phases:
            dist = np.minimum(np.mod(xs - phase, p), p - np.mod(xs - phase, p))
            score = np.sum(np.exp(-(dist / (0.12 * p + 1e-6)) ** 2))
            if score > best_score:
                best_score, best_p = score, p
    return float(best_p)


def same_cell_nms_1d(dets, alpha=0.58, ambig_ratio=0.70):
    p = estimate_pitch(dets)
    if p is None:
        return dets, {"pitch": None, "ambiguous": False}

    digits = [d for d in dets if d.cls in DIGIT_CLASSES]
    others = [d for d in dets if d.cls not in DIGIT_CLASSES]

    keep = []
    suppressed = []
    for d in sorted(digits, key=lambda z: z.score, reverse=True):
        hit = None
        for k in keep:
            if abs(d.cx - k.cx) < alpha * p:
                hit = k
                break
        if hit is None:
            keep.append(d)
        else:
            suppressed.append((d, hit))

    ambiguous = False
    for d, k in suppressed:
        if d.cls != k.cls and d.score >= ambig_ratio * k.score:
            ambiguous = True

    out = sorted(keep + others, key=lambda z: z.cx)
    return out, {"pitch": p, "ambiguous": ambiguous}
```

**Use the same-cell NMS as a precision-preserving filter: if it changes the returned integer and the suppressed alternatives are not clearly lower-score, veto the reading.** For product behavior, the safe rule is: “NMS may remove duplicate physical-cell hypotheses, but if the removed hypothesis is plausible, confidence becomes false.” This avoids converting ghost cleanup into silent wrong readings.

**Option `c`, CenterNet heatmap max-pool NMS `3→5` along x, is useful only if made class-agnostic over digit classes.** Standard CenterNet-style local max pooling, as in CenterNet / “Objects as Points” by Zhou et al. 2019, is usually classwise. Classwise NMS will not remove a `5` and `6` peak in the same physical cell if they are in different heatmap channels. Use a digit-class max heatmap, apply `1×5` or `1×7` NMS along x, then keep only the winning class at each kept center. Keep the dot separate.

```python
# hm: torch.Tensor [B, 11, H, W], sigmoid probabilities or logits after sigmoid.
# Apply to digit classes 0..9 only.
def class_agnostic_x_nms(hm, kx=5):
    assert kx % 2 == 1
    digits = hm[:, :10]                     # [B,10,H,W]
    dot = hm[:, 10:11]

    max_digit, win_cls = digits.max(dim=1, keepdim=True)  # [B,1,H,W]
    pooled = torch.nn.functional.max_pool2d(
        max_digit, kernel_size=(1, kx), stride=1, padding=(0, kx // 2)
    )
    keep_center = (max_digit == pooled)

    onehot = torch.zeros_like(digits, dtype=torch.bool)
    onehot.scatter_(1, win_cls, True)

    filtered_digits = digits * (keep_center & onehot).float()

    # Leave dot on normal 3x3 or its existing decode path.
    return torch.cat([filtered_digits, dot], dim=1)
```

**Option `b`, raising `RD_PEAK_MIN`, is a safety knob, not a ghost fix.** It will remove some ghosts but will also remove true MT10/EMETER_GREEN digits whose correct-cell scores are only `0.3–0.4`. Use per-class or global `RD_PEAK_MIN` only inside a calibrated selective gate. Do not expect exact-read accuracy to improve much; expect coverage to drop.

**Option `d`, “train with Gaussian radius tuned to cell width so neighbouring peaks are suppressed,” is weak as stated and can be harmful.** CenterNet/CornerNet Gaussian radius, following CornerNet by Law and Deng 2018 and CenterNet by Zhou et al. 2019, shapes the positive target around each object center; it does not explicitly suppress duplicate local maxima. If the Gaussian radius is too large relative to digit pitch, neighboring true digit centers start to overlap and classification gets worse. If the current radius is extremely small, modestly increasing it may improve score smoothness, but do not use radius as the primary anti-ghost mechanism. Keep output-space radius roughly `<= 0.25–0.35 * pitch_out`; avoid radii that make adjacent digit Gaussians overlap strongly.

**Option `e`, a CTC/sequence head, is the best long-term architectural fix but the highest short-term risk.** CRNN+CTC, following Graves et al. 2006 and Shi et al. 2016, naturally avoids “two detections in one cell” by predicting a sequence rather than object boxes. But it needs a separate training/evaluation path, string labels, and careful rejection calibration. It is not a 3-day fix for 0-wrong behavior. It becomes attractive after the boundary/type problem is under control.

**At training level, first audit whether every visible digit inside the reader crop is either labeled or masked.** If fraction digits are visible in the crop but sometimes unlabeled, focal loss treats them as background, which creates inconsistent gradients and low/unstable peaks. For CenterNet-style dense losses, unlabeled positives are poisonous. Action: dump 100 reader crops with labels overlaid; verify all visible integer, fraction, and dot cells are consistently labeled or explicitly ignored.

**For training, prefer “one physical cell → one hypothesis” supervision over more detector seeds.** If you keep the detector, add hard examples with same-height fraction digits, low contrast, and faint dots; add class-agnostic center suppression in decode; and optionally add a small 1-D cell/lattice auxiliary head. If you move architectures, use a line OCR model with CTC or a cell-classifier after lattice fitting; both directly remove the duplicate-detection degree of freedom.

**Measure ghost fixes with four numbers, not just final exact reads.** On the 38 human-line crops with display text, compute:  
1. full-display raw sequence exact rate;  
2. duplicate detections per physical cell after alignment;  
3. integer exact rate before confidence;  
4. accepted count and wrong accepted count after the gate.  
Grid `alpha ∈ {0.45,0.50,0.55,0.60,0.65,0.70}`, `ambig_ratio ∈ {0.6,0.7,0.8}`, and heatmap `kx ∈ {3,5,7}`. Select parameters on m4 calibration, not on the 49/34 final sets.

---

## Q2. Integer/fraction boundary

**Do not trust one cue alone; combine boundary cues as agreement/veto signals.** The locator right edge, the dot, equal-height lattice structure, and `kWh` glyph are all imperfect. For 0-wrong behavior, return confidently only when the boundary cues agree within a fraction of pitch. If they disagree, return `EMPTY`.

**Immediate no-retraining fix: use the LOCATOR right edge as a conservative boundary prior, not as an unconditional clip.** Transform the predicted LINE box right edge into reader-crop coordinates and cut digit detections whose centers are clearly to the right of `line_x2 + k * pitch`. Reject if there is a high-score detection near the boundary, because that means the cut could remove the last integer or keep the first fraction.

```python
def apply_locator_boundary_veto(dets, locator_line_x2_reader, pitch,
                                k=0.30, guard=0.25, min_score=0.25):
    # Boundary for digit centers, not bbox edges.
    x_cut = locator_line_x2_reader + k * pitch

    # If any plausible digit lies near the cut plane, boundary is unsafe.
    near = [
        d for d in dets
        if d.cls in DIGIT_CLASSES
        and d.score >= min_score
        and abs(d.cx - x_cut) <= guard * pitch
    ]
    if near:
        return None, {"reject": True, "reason": "boundary_ambiguous", "x_cut": x_cut}

    kept = [
        d for d in dets
        if not (d.cls in DIGIT_CLASSES and d.cx > x_cut)
    ]
    return kept, {"reject": False, "x_cut": x_cut}
```

**Grid the locator clip on validation, separately for predicted locator and oracle human line.** Try `k ∈ {-0.1, 0.0, 0.15, 0.30, 0.45, 0.60}` and `guard ∈ {0.15,0.25,0.35}`. Report: exact integer rate, accepted coverage, wrong accepted count, and “last integer clipped” count. If predicted-locator clipping helps oracle but hurts predicted mode, the locator boundary is too noisy and must only be a veto.

**A tiny boundary head is the best general retraining fix for SMART_MT10/EMETER_GREEN-style equal-height fractions.** Add a 1-D boundary heatmap head to the reader that predicts the integer/fraction cut x-coordinate. This directly supervises the missing variable instead of hoping the detector/assembler infers it.

```python
# Example reader head on feature map feat: [B,C,H,W], W=112 at stride 4.
class BoundaryHead(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(c, c, 3, padding=1),
            nn.ReLU(inplace=True),
            nn.Conv2d(c, 1, 1)
        )

    def forward(self, feat):
        z = self.conv(feat)          # [B,1,H,W]
        z = z.mean(dim=2)            # [B,1,W], collapse y
        return z
```

**Train the boundary head with a Gaussian target over x and low loss weight.** Use target `x_cut` as the midpoint between the last integer center and first fraction center when fraction boxes exist. If only integer boxes exist, use `integer_line_x2 + k_gt * pitch`, with `k_gt` estimated from annotated examples; start around `0.25–0.40`. Use BCE/focal on the 1-D heatmap with loss weight `0.03–0.10`, not a large weight that disrupts digit detection.

**Use the boundary head as a veto/agreement signal, not just a hard cut.** At inference, compute `x_cut_reader`, `x_cut_locator`, and `x_cut_dot_or_glyph` when available. Accept only if the active cuts agree within `0.35–0.45 * pitch`. If only one boundary cue exists and the display has same-height 8-cell structure with no dot, require stricter TTA agreement.

**Add a `kWh/unit` class, but treat it as an auxiliary cue, not the universal boundary solution.** For CRYSTAL, the printed `kWh` glyph is likely the strongest visible cue. Label `kWh` boxes on CRYSTAL and similar types and add a 12th class or a separate small glyph detector. For SMART_MT10/EMETER_GREEN, it will only help if the glyph is consistently visible and geometrically tied to the fraction cells. Do not cut directly at the glyph x without measuring the offset distribution by type.

**Measurement protocol: define a “safe cut interval” per image.** For each annotated line, compute pitch and define a boundary prediction as correct if it falls between the last integer center and first fraction center with margin, e.g.

```text
safe if: x_last_int + 0.25*pitch < x_cut < x_first_frac - 0.25*pitch
```

Report boundary-safe rate overall and by type. Then report OCR exact rate using oracle detections plus predicted cut, and finally full end-to-end exact/selective results. This separates “boundary cue works” from “detector missed digits.”

---

## Q3. SMART_MT10 with zero training data

**Do not optimize to the 9 SMART_MT10 test photos.** Report them as an out-of-distribution type: `2/9` on SMART_MT10, `20/30` on trained readable types. If you tune synthesis, thresholds, or assembly to those 9 and then report them as test, the number is no longer an honest test result.

**Until real SMART_MT10 data exists, the safest product behavior is to return `EMPTY` more often for that appearance.** Add a conservative OOD/type condition if the model sees an 8-cell, same-height, dark-LCD pattern with faint/no dot and low digit scores. Do not force a confident read on a type with zero labeled training examples.

**Procedural MT10 synthesis is worth doing; style transfer is lower priority.** For 7-segment LCDs, procedural synthesis can work because the glyph manifold is low-dimensional: segment topology, segment thickness, slant, blur, contrast, LCD background, glare, and dot visibility. This is closer to domain randomization, e.g. Tobin et al. 2017 and Tremblay et al. 2018, and synthetic text generation such as Jaderberg et al. 2014 / Gupta et al. 2016. Neural style transfer or CycleGAN-style transfer, e.g. Zhu et al. 2017, is risky for OCR because it can alter strokes, dots, and faint segments while preserving neither labels nor geometry.

**For `synth2`, explicitly model the structural property that is missing: 6 integer cells + 2 fraction cells of the same height.** Generate 8 same-height seven-seg cells, a faint dot between cells 6 and 7 with random visibility `p(dot_visible) ≈ 0.2–0.6`, dark green/black LCD backgrounds, low contrast, yellow case edges, mild perspective/tilt, JPEG, glare, and underexposure. Make sure the training labels include the full display and the integer/fraction boundary.

**Use synthesis as a hypothesis test, not proof.** Train one m4+synth2 model and compare on m4 validation by trained types to ensure no regression. Use the 9 MT10 images only as a diagnostic table clearly labeled “OOD diagnostic, used for analysis.” Do not claim general MT10 performance until there are at least 30–50 real SMART_MT10 photos, ideally from different meters and lighting conditions.

**Real data beats both synthesis and style transfer here.** Ask the owner immediately for 30–50 SMART_MT10 photos with verified readings: straight, tilted, dark, glare, flash/no flash, close/far. If owner has 97 unlabeled tilted photos, triage them: if the display text is human-readable in the photo, double-transcribe them even if the owner did not separately record the reading. Use double entry or reviewer adjudication to avoid adding label noise.

---

## Q4. Honest validation

**Do not use the 49/34 sets for model choice.** The proposal “promote only if val-m4 ≥ reference AND 49/34 not worse” still uses 49/34 as a selection filter if repeated. Use m4 pHash-cluster validation/calibration for model and threshold choice. Run 49/34 once as a final release audit. If it fails, either revert to the previous frozen model or create a new frozen acceptance set before iterating again.

**Split m4 validation into model-selection and calibration partitions at the pHash-cluster level.** For example, from the 177 m4-val images, make `val_select ≈ 90` and `val_cal ≈ 87`, stratified by meter type/readability. Use `val_select` for seed/model choice. Use `val_cal` only for confidence threshold calibration. Keep all near-duplicates and same meter/session clusters in the same side.

**Treat small exact-count differences on 177 images as noise.** Reader `148/177 = 83.6%` has binomial standard error about `2.8 pp`; a `+2` or `+3` image improvement is not meaningful. Use paired wins/losses versus the reference: count images where new is correct and ref wrong, and vice versa. Require a practical margin, e.g. at least `+5` exact images or a meaningful zero-error coverage increase, before promoting.

**For the selective gate, report coverage and a one-sided Clopper–Pearson upper bound on error.** If a gate accepts `n` images with `0` wrong, the 95% upper bound on error is:

```text
upper_error_95 = 1 - 0.05 ** (1 / n)
```

Useful anchors:  
`n=17 → 16.2%`, `n=50 → 5.8%`, `n=100 → 3.0%`, `n=200 → 1.5%`, `n=300 → 1.0%`. So “0 wrong on 17 accepted” is not strong statistical evidence; it is only a useful safety check.

**Use final 49/34 as an audit table, not an optimizer.** Report exact accuracy, accepted count, wrong accepted count, and CP bounds overall and by type. If SMART_MT10 is OOD, report it separately. If any confident wrong occurs on final audit, do not tune the threshold on that set; revert or collect a new final set.

**pHash clustering is better than filename-prefix splitting, but still add type/session stratification.** pHash can miss semantic near-duplicates under crop/lighting changes. If metadata exists, group by meter ID, owner, collection session, and meter type before randomization. If CPU allows, add a cheap embedding duplicate check using MobileNet/DINO features, but do not block the current m4 split on that.

---

## Q5. Model capacity

**A 2× reader width is plausible but not the first suspected ceiling.** A 0.21M-param detector at `64×448` with 11 classes and varied LCD backgrounds is very small; doubling to about `0.8M` could improve feature quality and heatmap scores. But it will not solve zero SMART_MT10 training data, wrong boundary rules, poisoned labels, or duplicate-cell decode. Expect possible gains on trained types, not on unseen structural types.

**Run one controlled capacity experiment, not a broad sweep.** Train baseline-width and 2×-width reader on the same m4 train split, same augmentations, same synthetic ratio, same number of seen samples, same seed if possible, and same decode/assemble code. If batch size must shrink for 2×, use gradient accumulation to keep effective batch size the same. Evaluate both on the same `val_select`; calibrate gates separately on `val_cal`.

**Measure matched-cell score distributions, not only exact string accuracy.** For each validation digit matched to GT, log best heat score, runner-up ratio, center error, and duplicate detections per cell. Keep the wider model only if it improves at least one of these without increasing confident wrongs:  
- median correct-cell score rises by `≥0.05–0.10`;  
- duplicate/cell rate decreases or stays flat;  
- exact integer improves by `≥5` images on 177 or selective zero-error coverage improves materially.

**Use train-vs-val behavior to decide capacity vs data.** If 2× lowers train loss and improves validation, capacity was limiting. If 2× lowers train loss but validation exact/coverage is flat or worse, data/labels/domain are limiting. If neither model fits train cleanly, inspect labels/loss/optimization before changing architecture again.

**Recalibrate confidence after widening.** Larger models often produce sharper heatmaps and more overconfident errors; calibration literature such as Guo et al. 2017 shows that accuracy and calibration do not move together. Do not reuse the `0.45/0.55` thresholds from the narrow model.

---

## Q6. Confidence

**Expected utility for zero-wrong coverage: TTA agreement > segment verifier veto > temperature scaling.** Global temperature scaling changes probability calibration but not the ranking of predictions; if you recalibrate thresholds anyway, it rarely increases zero-error coverage. TTA adds new invariance evidence. The DSEG verifier adds a partially independent shape cue, but AUC `0.76` is only moderate, so use it as a veto/margin feature, not as a primary acceptor.

**Implement 5-run reader TTA because speed is not binding.** Use deterministic, mild transforms that should not change the true string: identity, gamma darker, gamma brighter, slight crop-pad expansion, slight crop-pad contraction or scale. Avoid large affine TTA that changes the line geometry. Decode each run independently with the same ghost NMS and boundary logic.

```python
TTAS = [
    {"gamma": 1.00, "pad_scale": 1.00},
    {"gamma": 0.85, "pad_scale": 1.00},
    {"gamma": 1.20, "pad_scale": 1.00},
    {"gamma": 1.00, "pad_scale": 0.96},
    {"gamma": 1.00, "pad_scale": 1.04},
]
```

**Start with a unanimity gate, then relax only on calibration.** Initial safe rule: all 5 TTA runs must return `OK`, all must return the same integer string, max aligned center std must be `<0.08*pitch`, and boundary cuts must agree within `<0.35*pitch`. This will reduce coverage but should reduce systematic ghost acceptances.

```python
def tta_accept(runs, pitch):
    ok = [r for r in runs if r.status == "OK"]
    if len(ok) != len(runs):
        return None, "not_all_ok"

    strings = [r.integer for r in ok]
    if len(set(strings)) != 1:
        return None, "string_disagreement"

    # Align same-position digit boxes across runs.
    max_std = aligned_center_std(ok) / max(pitch, 1e-6)
    if max_std > 0.08:
        return None, "unstable_centers"

    if boundary_spread(ok) / max(pitch, 1e-6) > 0.35:
        return None, "unstable_boundary"

    return strings[0], "accepted"
```

**Use DSEG as a per-digit veto with a fixed margin feature.** For each accepted detector digit crop, compute DSEG best-vs-second-best template margin or distance margin. Reject if any digit has low verifier margin or if detector class and DSEG best class disagree with high DSEG confidence. Since AUC is only `0.76`, do not allow DSEG to override the detector; only let it veto suspicious digits.

**Avoid overfitting the 73 final photos by predefining features and calibrating only on m4 calibration.** Use a small fixed feature set:  
- detector min score;  
- detector max runner-up/best ratio;  
- ghost suppressed/kept score ratio;  
- TTA vote fraction;  
- TTA center std / pitch;  
- boundary disagreement / pitch;  
- DSEG min margin.  

Then either use a lexicographic rule or a single scalar badness score. Do not train a flexible classifier on 73 photos.

```python
badness = max(
    1.0 - min_digit_score,          # lower score worse
    max_runner_ratio,               # higher ambiguity worse
    max_suppressed_ratio,           # higher ghost ambiguity worse
    1.0 - vote_fraction,            # TTA disagreement worse
    center_std_over_pitch / 0.08,    # >1 bad
    boundary_spread_over_pitch / 0.35,
    dseg_badness
)
# Choose threshold on m4 calibration only.
```

**Temperature scaling is still useful for reporting, not for discovering safer reads.** Fit temperature on digit-level calibration NLL if you want calibrated probabilities, following Guo et al. 2017. Do not expect it to turn low-score but correct MT10 digits into safe acceptances, because it adds no new visual evidence.

**Use selective-prediction reporting, not only thresholds.** Frame this as selective classification in the sense of Chow 1970 and Geifman & El-Yaniv 2017: report risk among accepted samples and coverage. For every gate version, report accepted count, wrong accepted count, and CP upper bound.

---

## Q7. Next 3 days: stop/start priorities

**Stop tuning recipes against the frozen 49/34 sets.** Do not run more seed soups, AUG v3 variants, or threshold tweaks judged by those sets. Use them only once as final audit after the m4-selected model/gate is frozen.

**Stop treating raw detector score thresholds as the main lever.** The current dominant issues are same-cell duplicates, boundary ambiguity, OOD type, and validation leakage. Raising `RD_PEAK_MIN` alone will mostly reduce coverage.

**Stop style-transfer work unless all procedural/data fixes are blocked.** CycleGAN-like style transfer is not the right first response for seven-seg OCR because preserving faint dots and segment topology is exactly the hard part.

**Day 1 priority: implement and evaluate class-agnostic same-cell NMS plus ambiguity veto.** Cache reader heatmaps/top-K detections for m4-val, the 38 human-line crops, and final sets. Grid `alpha`, `ambig_ratio`, and heatmap `kx`, but choose parameters on m4 calibration only. Produce a table: exact integer, full-display raw exact on 38, accepted count, wrong accepted count, duplicate/cell rate.

**Day 1 priority: implement locator-boundary conservative clipping as a veto.** Transform locator LINE right edge to reader coordinates, grid `k` and `guard`, and report oracle-locator versus predicted-locator behavior. Keep the rule only if it reduces fraction leakage without clipping last integers; otherwise use it only as an uncertainty feature.

**Day 1 priority: split m4-val into `val_select` and `val_cal` by pHash cluster and type.** Use `val_select` to choose among the currently running m4 seeds. Use `val_cal` for the confidence gate. Write the split IDs to disk and do not reshuffle during this cycle.

**Day 2 priority: add TTA consensus gate.** Run 5 deterministic reader TTAs on cached crops. Start with unanimity, stable centers, stable boundary, and ghost ambiguity veto. Calibrate only on `val_cal`. Report coverage and CP upper error.

**Day 2 priority: consume the unused real data after label audit.** Add the 134 labeled photos only after checking the 41 two-digit CRYSTAL cases and removing/repairing V/A/PF poisoned labels. Box the 19 remaining photos if they are readable. Real cleaned data is higher value than another augmentation sweep.

**Day 2 priority: ask the owner for SMART_MT10 data immediately.** Request 30–50 verified SMART_MT10 photos with varied tilt/exposure and full-meter context. Also ask for the 97 unlabeled tilted photos; double-transcribe visible displays if possible. This is the only credible way to close the zero-example gap.

**Day 2/3 optional: build procedural MT10 synthesis, not neural style transfer.** Generate 2k–5k MT10-style reader lines and some scene-level examples with yellow case/dark LCD. Train one ablation `m4 + synth2`; require no regression on m4 trained types before considering it useful. Treat the 9 MT10 final images as diagnostic only.

**Day 3 optional: run one 2× reader-width experiment.** Only do this after the decode/boundary/TTA harness is fixed, because otherwise the wider model will be evaluated through broken assembly. Compare against same-seed baseline using the same split, same training budget, and separately calibrated gates.

**End of Day 3 deliverable: one release table and one error table.** Release table: exact accuracy, accepted coverage, wrong accepted count, CP upper bound, by type and overall, for m4-select, m4-cal, and final audit. Error table: locator IoU failure, reader-from-human-box failure, boundary failure, ghost duplicate failure, OOD type. Use that table to decide whether the next week is data collection, boundary-head training, or model capacity.
