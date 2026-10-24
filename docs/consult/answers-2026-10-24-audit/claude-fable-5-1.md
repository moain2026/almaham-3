# claude-fable-5-1 — 2026-10-24 08:43 UTC (265s)

# Consultation #2 — answers

## Q1. Ghost detections

**Diagnosis first (determines which fixes can work).** With PAD_X 0.18 the line occupies ≈448/1.36 ≈ 330 px; for 8 cells pitch ≈ 41 px ≈ 10 heatmap cells at stride 4, digit width ≈ 25–30 px. Your ghosts (`005337.88 → 00563307018`) are half-cell offset, i.e. ≈4–5 heatmap cells apart. CenterNet's 3×3 max-pool suppresses only ±1 cell; a 5-kernel only ±2. The training penalty is also not the cause: with `gaussian_radius(min_overlap=0.7)` on a 7×9-cell box, r≈2, σ≈0.83, so a negative at 1 cell has (1−Y)⁴≈0.07 but at 4 cells it is already ≈1.0 — ghosts at half-pitch are *fully* penalised during training yet still appear. That means the heatmap is genuinely bimodal on the cell: the net fires on digit *parts* (left/right vertical segment pairs; 0 ≈ two 1s, 8 ≈ 3+9 fragments) — a receptive-field / feature-ambiguity problem (Luo et al. 2016, *Understanding the Effective Receptive Field*), not a target-encoding problem. Compute your ERF: if it is <1.5 cells (~60 px) the net cannot see a whole cell plus its gaps when it votes for the centre.

**Ranking by gain/risk for 0-error:**

1. **(a) 1-D pitch-aware NMS at decode — do this today.** It directly targets the failure, needs no retraining, and is the only option that is pitch-adaptive. Crucial detail for 0-error: when the suppressed ghost has a *different class* (the `5/6`, `3/0` cases) you are not "removing noise", you are observing model uncertainty — fold the ghost's score into the kept digit's runner-up so the existing gate (`alt < 0.5·best`) sees it. Keeping the higher-scored of 5 vs 6 blindly would turn a MISSING/TOO_MANY (safe) error into a confident wrong reading (unsafe).

```python
def nms_1d(dets, ratio=0.6):
    # dets: list of dict(cx, cy, w, h, score, cls, alt)  (alt = runner-up class score at the peak)
    if len(dets) < 2: return dets
    dets = sorted(dets, key=lambda d: d['cx'])
    w_med = np.median([d['w'] for d in dets])
    gaps = np.diff([d['cx'] for d in dets])
    good = gaps[gaps > 0.75 * w_med]           # ghost gaps (~0.3–0.5 pitch) are excluded
    pitch = np.median(good) if len(good) else 1.3 * w_med
    keep = []
    for d in sorted(dets, key=lambda d: -d['score']):
        hit = next((k for k in keep if abs(k['cx'] - d['cx']) < ratio * pitch
                    and min(k['cy']+k['h']/2, d['cy']+d['h']/2) - max(k['cy']-k['h']/2, d['cy']-d['h']/2) > 0.3*min(k['h'], d['h'])), None)
        if hit is None:
            d = dict(d, n_ghost=0); keep.append(d)
        else:
            hit['n_ghost'] += 1
            if d['cls'] != hit['cls']:
                hit['alt'] = max(hit['alt'], d['score'])   # ambiguity, not noise
    return sorted(keep, key=lambda d: d['cx'])
```

Also replace the 2-D box NMS `IoU 0.45` with intersection-over-min on the x-interval (IoM_x > 0.5) — it catches containment and side-by-side boxes on one cell that IoU misses. Port to Kotlin and add the 49 parity cases.

2. **(c) wider max-pool along x** — cheap, harmless, insufficient alone. Kernel (1×5) catches ghosts ≤2 cells away; the typical ghost is 4–5 cells away, so you would need ~13 along x, which kills legitimate neighbours on 9–10 digit displays or tight lines. Use 1×5 as a complement to (a), not instead. Implement in post-processing (Kotlin/NumPy) rather than in the ONNX graph so the exported model doesn't change.

3. **(d) Gaussian radius** — low gain, as computed above; if anything a *smaller* radius or a hard-negative-weighted band at 0.3–0.7 pitch from each centre would push harder, but the fix for part-firing is RF/depth (see Q5), plus synthetic lines with tight pitch (gap/width 0.1–0.3) and narrow fonts so the net must learn whole-cell context. Put this in the next retrain, don't block on it.

4. **(b) raising RD_PEAK_MIN per class** — no. Ghost scores (0.30–0.45) overlap the correct-cell scores on MT10/EMETER_GREEN (0.3–0.4); any threshold that removes ghosts removes real digits on the weak types. Per-class thresholds on 11 classes tuned on 38 photos is pure overfitting.

5. **(e) CTC/sequence head** — highest cost, unproven at your data scale, last. CRNN (Shi et al. 2016) works for plates/meters with thousands of real lines; Laroca et al. (2019, UFPR-AMR; 2021, Copel-AMR 12.5k) found a detection-based reader (CR-NET) *beat* CRNN on meters, and Gómez et al. (2018, *Cutting Sayre's Knot*) needed large synthetic+real sets. CTC also gives no per-digit box, which your integer/fraction cut and per-digit gate need. Where a sequence model *is* worth it later: as an independent **verifier** (string agreement = gate feature), not as the primary reader.

**Measurement (you have raw dets vs display text for 38; plus val-m4 with digit boxes):**
- Tune `ratio` ∈ {0.45, 0.5, 0.55, 0.6, 0.65, 0.7} on **val-m4** (digit-box labels → per-detection TP/FP via centre-in-box), not on the 38. Report per-ratio: ghost rate (dets with another det within 0.5 pitch), FP/photo, recall, and *confident-wrong*.
- On the 38 (one look): (i) exact-string match rate (currently 1/38), (ii) mean Levenshtein distance between assembled digit string and display text, (iii) count of photos where `n_cells` after NMS equals the display's cell count, (iv) how many "cut at 6" rule fires now vs before. Expect exact-string to jump to roughly the 60–70% region on trained types if ghosts are the main defect; if it doesn't, the residual is classification (3/5/6/8/9) and the fix is Q5/Q6, not decoding.

## Q2. Integer/fraction boundary

**Order of operations:** fix ghosts first (Q1), *then* re-measure boundary errors. Today's "lattice → cut at 6" rule is defeated by ghosts, so you cannot yet tell how much is a genuine boundary problem. Expected: after NMS, the structural rule alone recovers a good share of TOMAS/TAGADOD; what remains is MT10/EMETER_GREEN/CRYSTAL with equal-height fraction cells.

**12th class for the kWh glyph — not as primary cue.** Reasons: (i) it needs new labels on ~900 photos, (ii) the glyph is printed text ~8–12 px tall at 64×448, marginal for a stride-4 0.21M net, (iii) it exists on CRYSTAL but you don't know it exists on MT10 (zero data), (iv) it's a per-type hack. Only add it if after the boundary head CRYSTAL remains the dominant boundary error.

**Boundary keypoint head — recommended, zero labelling cost.** Add one heatmap channel `bnd` to the reader: a Gaussian at x = midpoint between the right edge of the last integer digit and the left edge of the next cell (or the LINE box right edge if no fraction), y = line centre. You already have the labels: the LINE box is the union of integer boxes, so `last_integer = max(right edge of boxes inside LINE)`. It is cue-agnostic (dot, height drop, glyph, cell spacing, position in display) and operates at reader resolution (≈4× finer than the locator's right edge at 256²). Add `+ focal(bnd)` with weight 1.0; decode as argmax x along the line row with its score `s_bnd`.

```python
# label construction (reader target builder)
int_boxes = [b for b in digit_boxes if b.cx < line_box.x2 + 0.25*pitch]
x_cut = 0.5 * (max(b.x2 for b in int_boxes) + min((b.x1 for b in digit_boxes if b.cx > line_box.x2), default=line_box.x2 + 0.5*pitch))
draw_gaussian(heat[11], (x_cut/stride, cy/stride), radius=2)
```

**Locator as a second, coarse cue — keep it, don't "trust harder".** Your LINE_CLIP mixed result is what a ±0.5-cell-accurate right edge predicts: it decides the count correctly except when the edge lands near a cell centre. Use it as `n_int_loc = #digits with cx < line_right + 0.5·pitch` (in reader coordinates), never as a hard clip. Then:

- `n_int_bnd` from the boundary head, `n_int_rule` from dot/height/lattice rule, `n_int_loc` from the locator.
- Reading is **confident only if ≥2 of the 3 agree, and none disagrees with s_bnd ≥ 0.3** (i.e. a confident boundary head veto counts). This is the same "independent-cue agreement" pattern you'll use in Q6.

**Protocol.** On val-m4 (where integer counts are known from LINE boxes): report `|n_int_pred − n_int_true|` histogram per cue and per type, and the agreement-gate coverage/wrong. On the 38: one pass, same table. Success criterion: boundary-caused wrong readings under the agreement gate = 0 at coverage ≥ 60% of correctly-detected lines. If the boundary head's own accuracy is <85% on val, inspect its ERF (it needs ~1.5 cells of context either side).

## Q3. SMART_MT10 with zero data

**Scope decision first (owner, not model):** MT10 is from a region outside the labelled pool. Decide with the owner whether it is in product scope. If it is, the only reliable fix is **20–30 MT10 photos**, which can be unlabelled: current model + 1-D NMS pre-boxes them, a reviewer corrects digits in ~1 min/photo. Ask for them now; 9 test photos is 23% of your headline number and you are otherwise reporting a type you've never trained on. Note the 9 test photos must not be used to design synth styles (looking at them to decide "dark LCD, faint dot" is already a mild leak — fine once, document it, stop).

**(b) synth — yes, but randomise, don't imitate.** For 7-segment LCDs synthetic glyphs transfer well (DSEG geometry is exactly the real geometry); the gap is photometric/background. Domain randomisation (Tobin et al. 2017) beats targeted imitation when you can't observe the target: extend `line_s1` with **both polarities** (light-on-dark and dark-on-light — check whether MT10 is inverted; if yes this is probably the single missing factor), contrast range down to 0.15, dot visibility 0–1 (alpha), uniform cell height for fraction cells (0–2 of them), background tint swept over yellow/green/grey/black, specular streaks. Add **polarity inversion** as a real-data photometric aug too (p=0.3) — you have gray/channel-perm but no invert.

**(c) style transfer** — real CycleGAN-style transfer with 0 clean target images is not viable; the cheap version (apply MT10-like photometric to TOMAS crops) is just (b)'s randomisation applied to real crops, so do it as augmentation, not as a separate pipeline.

**Measurement honesty:** you have no MT10 val, so you cannot tune anything; you can only train with the wider randomisation, confirm no regression on val-m4, and then read the 9 once. Realistic expectation: +1–3 of 9 if polarity/contrast was the blocker; ~0 if MT10 has a different font aspect or faint segments. Report MT10 separately in every table with CP bounds (2/9 → 95% CI [2.8%, 60%] — i.e. no information).

## Q4. Honest validation

**Split:** pHash 16×16 (256 bit) at Hamming ≤24 (~9%) is a reasonable near-dup threshold. Two gaps: (i) it does not group *the same meter re-photographed with different framing* — if your data have any meter/customer ID, union-find on that too; (ii) **stratify clusters by type** so val has every type in proportion and you can report per-type (EMETER_GREEN 1/6 is otherwise invisible).

**Noise floor:** val-m4 n=177 at 84% → CP 95% CI ≈ [78%, 89%]; SE ≈ 2.8 pts. Differences between seeds of 1–3 photos are noise. Picking the best seed on val is a winner's curse that inflates the reported val by ~1 SE. Fixes:

1. **Don't pick — ensemble.** Speed is not a constraint: run the 3 seeds and average heatmaps (and wh/offset) before decoding. Output-averaging is monotone-improving unlike your weight soups (Wortsman et al. 2022 soups need a shared basin; your non-monotone result says they aren't). Deep ensembles (Lakshminarayanan et al. 2017) also improve calibration, which is what your gate needs. Three 0.21M models ≈ 3 MB total, ~3× reader latency — irrelevant.
2. If you must pick one (size budget), pick by a **pre-registered composite**: primary = coverage at 0 confident-wrong on val-cal half, tie-break = exact accuracy; never pick by the 49/34.

**Promotion rule critique:**
- "val-m4 ≥ reference": with ±5 pt CI this is a coin flip. Replace with a **paired McNemar / paired bootstrap on the same 177 photos**, require "not worse at p<0.2 one-sided" plus improvement on the primary metric (coverage at 0 wrong). Paired tests are far more sensitive than comparing two accuracies.
- "49/34 not worse" and "strict-gate wrong = 0 on test": every such check *selects* on the test set. Treat 49 as a dev-test looked at once per model-family change and the 34 as a release-only set (Dwork et al. 2015, *reusable holdout*); keep a log of every look.
- Gate threshold: calibrate on half of val (~88), evaluate coverage/wrong on the other half, then swap (2-fold) and report both. With 0 wrong of n accepted, the 95% upper bound on the wrong-rate is ≈3/n (rule of three, Hanley & Lippman-Hand 1983): 17 accepted → ≤17.6% (CP 19.5%); 88 → ≤3.4%. **State this plainly in the report: "0.0 error" is currently unverifiable below ~18%; demonstrating ≤1% at 95% needs ≈300 accepted readings with 0 wrong.** That number is the real roadmap for the data pool.

## Q5. Capacity

**Low absolute scores don't indicate under-capacity.** CenterNet focal heatmaps peak at 0.4–0.8 for correct detections even in ResNet-101 models; the ranking and the *gap* to the runner-up matter. The discriminating diagnostic is the **train/val gap**: evaluate the current model on 177 *training* photos (same metric). If train ≈ val (≈85%) you are under-fitting/optimisation-limited → width/depth helps; if train ≥ 95% you are data/generalisation-limited → width won't help, data and gating will.

**One controlled experiment (overnight on 8 cores):** three widths {0.7×, 1×, 2×} channels (≈0.1/0.21/0.8M), identical recipe, 3 seeds each, same 3000 steps, same m4 split. Report mean ± std on val-m4 for: exact accuracy, mean margin (best − runner-up on correct cells), ghost rate, and ensemble-of-3 accuracy. If 2× gives >+3 pts mean with std <2, keep it; if the width curve is flat, capacity is not your bottleneck. CPU cost: 2× width ≈ 4× FLOPs; if 1× takes ~1.5 h, 2× ≈ 6 h — run it as the last job of the day.

**What I'd actually expect to matter more than width:** (i) **depth / ERF** — part-firing ghosts and boundary decisions need ≥1.5 cells of context; add two 3×3 stride-1 convs at the stride-4 level (or a dilated pair) before the heads: cheap in params, large ERF gain; (ii) **real:synth ratio** — 50/50 at 4000 synth vs 900 real means synth dominates; try 70/30 real-weighted (not in your exhausted list); (iii) the m4 data itself (+70% real lines).

## Q6. Confidence / gate

**Temperature scaling (Guo et al. 2017): useless here.** It is a monotone transform of heat values; your gate thresholds on min-score and a ratio, so ranking-preserving transforms change nothing unless you mix heterogeneous signals. Skip.

**What moves coverage at 0 wrong:** your errors are mostly *structural* (ghost → extra cell, boundary → wrong count), not digit misclassification, so structural checks are highly informative and essentially free of false rejects:

- `n_cells ∈ {6,7,8}` after NMS; pitch CV < 0.12; height CV < 0.15; `n_ghost_with_other_class == 0` (or folded into alt as in Q1).
- Boundary agreement (Q2): ≥2 of 3 cues agree.
- **Ensemble/TTA string agreement**: 3-seed ensemble string == each member's string == strings under TTA (gamma 0.7/1.4, scale 0.92/1.08). Ensembles outperform TTA for uncertainty (Ashukha et al. 2020); since you'll have 3 seeds anyway, use both; TTA costs ~4 extra passes, irrelevant.
- **Monotonic prior**: if the app knows the customer's previous reading, require `prev ≤ new < prev + max_monthly` — near-zero false-reject, catches most residual digit swaps. Also a product-level option: when not confident, ask for a second photo and require agreement.
- Segment verifier at AUC 0.76: as a veto it rejects ~1 correct per wrong caught at any operating point — use only as a *tie-breaker* when exactly one of the above checks fails, or drop it. Don't spend time improving it.

**Combination without overfitting 73–177 photos:** fix the gate *structure* a priori as a conjunction (all structural checks AND agreement AND `min_score ≥ t`), leaving **one** tunable `t`. Choose `t` on the val-cal half as the smallest value with 0 wrong, then add a margin of 0.05; evaluate on the other half; report coverage with its CP interval and the rule-of-three bound (Geifman & El-Yaniv 2017 for the selective-prediction framing; conformal-style calibration if you want a formal bound — Angelopoulos & Bates 2021 tutorial). Expected effect (from your fault table): structural checks alone should lift coverage from 23% toward 40–50% on trained types while keeping 0 wrong, because the 0.45–0.6 TOMAS cells are correct and were only being rejected by the global 0.55 min-score.

## Q7. Stop / start — 3 days, 8 cores

**Stop now:** seed hunting on m3, EMA/soup/aug-v3 variants, masking experiments (all inside the ±5-pt noise band); raising/lowering global thresholds; looking at the 49/34 more than once per change; treating MT10 as a modelling problem.

**Day 1 (decode & gate, no training):**
1. Implement `nms_1d` + IoM_x merge + ghost→alt folding; Kotlin port; parity tests. Tune ratio on val-m4 digit boxes.
2. Rewrite `assemble.py` structural checks (cell count, pitch/height CV) and the fixed-structure gate with one threshold; 2-fold calibrate on val-m4.
3. Heatmap-averaging ensemble of the 3 m4 seeds when they finish. One look at the 38/49: exact-string rate, coverage at 0 wrong, per-type table with CP bounds.
4. Add boundary-head label generation and polarity-inversion aug (real) + polarity/contrast/dot-alpha randomisation (synth). Kick off reader with boundary head, 3 seeds, overnight.

**Day 2 (data & locator):**
5. Clean and add the 134 photos (model pre-boxes → reviewer verifies) and the 41 CRYSTAL 2-digit labels *after* re-checking the V/A/PF poisoning on every one; add the 19 unboxed.
6. Locator is your largest fault bucket (9/39). Three cheap moves: (a) label LINE boxes on the owner's 97 tilted photos (locator needs only a box, ~20 s each — no reading required); (b) raise locator input 256→384 (speed is free; at 256² the LCD line is ~60 px wide); (c) ensemble locator seeds. Start locator retrain on m4 + 97 tilted with AUG v3 (it helped TH34), 3 seeds, overnight.
7. Evaluate boundary-head reader on val-m4; wire the 3-cue boundary agreement.

**Day 3 (capacity probe & report):**
8. Width experiment {0.7×,1×,2×} + the ERF/depth variant, 3 seeds each, run as the overnight job; read the train/val gap first thing (decides whether width is even worth it).
9. Write the report: per-type accuracy and coverage with CP intervals, the explicit rule-of-three statement on "0.0 error", the test-set look log, and a data request to the owner: 30 MT10, 30 EMETER_GREEN, 30 CRYSTAL field photos with readings, plus the target of ~300 accepted/0 wrong readings for a ≤1% claim.

Honest summary of expected outcomes: decode+gate (Day 1) is the highest-certainty gain and should turn most ghost failures into either correct or safely-abstained readings; the boundary head and locator data are medium-certainty; width is low-certainty until the train/val gap says otherwise; MT10 is unfixable without its own data.
