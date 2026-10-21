# Agent D — final summary 2026-10-21 (single source of truth)

## Files (public repo `moain2026/almaham-3`, branch `genspark_ai_developer`)
| File | Content |
|---|---|
| `benchmark/data/erp/labels_agentD.csv` | **1127** training readings. Columns: `filename,text,labeller,ts,n_labels,meter_type,confidence,owner_raw` |
| `benchmark/data/erp/labels_agentD_rejected.csv` | **234** X/P photos. These are NOT for training; `load_labels()` drops them |
| `benchmark/data/erp/testset_human.csv` / `.sha256` / `_siblings.csv` | Frozen human test set + siblings. Excluded by `erp_finetune.EXCLUDE_FILES` |
| `benchmark/data/erp/agentD_tooling/` | All agent D scripts (`mm/` = multi-model, bbox, classify, merge; `owner_page/server.py` = phone page) |
| `docs/handoff/agentD-to-all-2026-10-21-b4-owner-types.md` | Batch-by-batch log b4–b8 + the CORRECTION section |

Format: integer part only, with leading zeros as shown on the display. No decimals and no red decimal drum.

## Counts (labels_agentD.csv = 1127)
- **labeller**: owner 466, agentD 661.
- **confidence**:
  - `owner_visual` 466 — visually verified by the owner personally. Highest trust.
  - `4strong+visual` 258 — gpt-6.1-sol + gpt-6-astra + gemini + claude-opus-5-5 all agree, and agent D checked each one by eye.
  - `4models+visual` 281 — 4 older models agree + agent D visual check.
  - `4/4` 122 — 4 models agree (older Tomas batch).
- **meter_type**: TOMAS_SMART 292, CRYSTAL 249, SMART_YELLOW 172, OTHER 130, TAGADOD 129, TOMAS_STATIC 62, KENWELL 46, MECHANICAL 36, GLORY 7, CHINT 3, HPL 1.
  - SMART_YELLOW = the Iraqi yellow smart meter, including the same meter opened (green PCB, blue/red buttons). EMETER_GREEN and SMART_MT10 are merged into it.
- **CRYSTAL integer digits**: 1-digit 8, 2-digit 67, 3-digit 164, 4-digit 10.

## Strong-model benchmark (41 owner-read uncommon photos)
gpt-6.1-sol 36✓/3✗, gpt-6-astra 31/2, gemini 30/6, claude-opus-5-5 30/7, gpt-6-sol 27/9, claude-opus-4-8 25/15, gpt-5.6-sol 21/19, grok-4.7 20/12.
When the top 4 agree: 24/24 correct. Even so, a visual check stays mandatory (agent D rejected 17 of 275 4/4 cases).

## Safety checks (run 2026-10-21, all pass)
- 0 overlap between labels and rejected; 0 X/P/non-digit in labels; CSV uses LF line endings.
- 0 labels whose photo hash is in `benchmark/data/photos.sha256` (the 49 test photos).
- 0 labels in `testset_human.csv` or `testset_human_siblings.csv`. In the final check, 36 old `4/4` rows were found that overlapped the test set / siblings. They were removed from the labels and from the by_type crops. Training was never affected, because `erp_finetune` already excluded them.
- Every label has a whole-meter crop in private `erp/by_type/<TYPE>/`.
- No passwords or tokens in any file (ERP credentials are env vars only).

## Private repo `moain2026/almaham-3-private-data` (branch `main`)
- `erp/photos/` — 7144 ERP photos.
- `erp/by_type/<TYPE>/*.jpg + index.csv` — whole-meter crops (`filename,reading,labeller,source,crop`).
- `erp/crops_full/agentD_2026-10-21/` — Tomas whole-meter crops.
- `erp/manifests/`:
  - `owner_labels_b2..b8_*.json` + `owner_b*_items.json` — raw owner page saves.
  - `owner_b8_conflict4.json` — 4 photos where the owner and agent D's zoom disagree. Held back: not in labels, not in rejected.
  - `agentD_2026-10-21_work/` — all raw model votes (`strong.jsonl` etc.), bboxes, type classifications, visual review notes (`vs_rej.txt`, `vs_type.txt`, `vs_review_index.csv`).

## Open items
1. `owner_b8_conflict4.json` — the owner should confirm these 4 photos.
2. HPL / CHINT / GLORY are very rare (≈1 per 1500 photos). Waiting for the owner to name the area or collector that has them.
3. About 4000 newly downloaded photos are not yet classified or read by the strong models.
