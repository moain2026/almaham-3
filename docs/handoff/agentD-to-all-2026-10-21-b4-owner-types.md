# Agent D -> all agents: OWNER-VERIFIED labels + type folders (2026-10-21, batch b4)

## Summary
- `benchmark/data/erp/labels_agentD.csv` = **785 readings, digits only (no X/P)**.
  - **owner = 425**: every one **visually read and typed in by the owner himself** on the phone page (`confidence=owner_visual`). These are ground truth. The meter TYPE of the new uncommon photos was also confirmed by the owner while reading them.
  - **agentD = 360**: 158 by the 5-layer method + 202 Tomas where 4 different models (gpt-5.6-sol, grok-4.7, gpt-6-sol, claude-opus-4-8) agreed 4/4 AND agent D confirmed visually (`confidence=4models+visual`).
- X/P (unclear / several meters) are **NOT** in the labels file: `labels_agentD_rejected.csv` (62 rows) -> `load_labels()` removes them from training.
- New this batch: **owner +215 digits** (uncommon types: SMART_YELLOW 46, TAGADOD 38, CRYSTAL 35, OTHER 23, MECHANICAL 15, KENWELL 12, GLORY 3, HPL 1, + 42 Tomas), **30 X** moved to rejected.

## Type naming decision by the owner (IMPORTANT)
- `SMART_YELLOW` = the yellow-case smart meter ("Iraqi meter", SMART MT10/DMC). When its cover is open you see a **green circuit board with a green and a red button** - it is the SAME meter. Former labels `EMETER_GREEN` and `SMART_MT10` were merged into `SMART_YELLOW`.
- New types now present: `KENWELL` (green electronic LCD), `GLORY`, `MECHANICAL` (drum counter: integer black drums only), `HPL` (3-phase), `OTHER` (People Electric, CHINT, Enertec, Veto ...).

## Counts by type
| type | owner | agentD | total |
|---|---|---|---|
| TOMAS_SMART | 77 | 224 | 301 |
| CRYSTAL | 102 | 22 | 124 |
| TAGADOD | 67 | 23 | 90 |
| SMART_YELLOW | 75 | 14 | 89 |
| OTHER | 56 | 28 | 84 |
| TOMAS_STATIC | 16 | 49 | 65 |
| MECHANICAL | 15 | 0 | 15 |
| KENWELL | 12 | 0 | 12 |
| GLORY | 3 | 0 | 3 |
| HPL | 2 | 0 | 2 |

## Photos (private repo `moain2026/almaham-3-private-data`)
- `erp/by_type/<TYPE>/` - one folder per meter type, **whole-meter crop** (like the app: aim, press, the whole meter is cut out; not the LCD only). `index.csv` per folder: filename,reading,labeller,source,crop.
- Originals: `erp/photos/<filename>`; crop boxes: `erp/manifests/meter_bbox_agentD_2026-10-21.jsonl` (fractions x1,y1,x2,y2 of the original photo).
- Owner raw entries: `erp/manifests/owner_labels_b3_2026-10-21.json`, `owner_labels_b4_2026-10-21.json`.
- Not used for training: 44 multi-meter photos (`pools_b3_agentD.json` -> group), Tomas backlog ~600 unclear (owner decided: enough Tomas).

## Rules unchanged
- The 49 test photos (benchmark/data/photos.sha256) and testset_human are never labelled/trained.
- Readings = integer part with displayed leading zeros (fixed-width types padded to 6; owner raw kept in `owner_raw`).

## CORRECTION (later on 2026-10-21) — owner page b4 bug, labels removed
- Bug found by agent D: the b4 phone page reused the browser storage of the b3 page (same URL/token). Photos #1–#43 of b4
  were pre-filled with the owner's b3 readings (Tomas photos). 42/43 matched b3 exactly → those b4 labels were NOT the owner's
  reading of those photos. **All 43 removed** (41 from labels_agentD.csv, 2 from rejected).
- Cross-check: the two strongest models on a 41-photo owner benchmark (gpt-6.1-sol 36/41 correct, gpt-6-astra 31/41, 0 wrong when the
  top-4 strong models agree) re-read every remaining owner label. **60 owner labels where neither model matched (±1 trailing decimal digit)
  were also removed** (they go back to the owner for a second look). 324 owner labels confirmed.
- labels_agentD.csv now = 763 (owner 324 confirmed, agentD 439). Page server fixed: saves only when filename matches, new token.
- Model benchmark (48 owner photos, uncommon types): gpt-6.1-sol best, then gpt-6-astra, gemini (gsk understand_images), claude-opus-5-5.
  Old set (gpt-5.6-sol, grok-4.7, gpt-6-sol, claude-opus-4-8) is weaker on uncommon types → not used alone any more.

## b6 — 4-strong-model consensus + agent-D visual check (2026-10-21)
- Models: gpt-6.1-sol, gpt-6-astra, gemini (gsk understand_images), claude-opus-5-5. Benchmark on 41 owner-read uncommon photos: when all 4 agree → 24/24 correct.
- 576 non-Tomas photos run → 275 with 4/4 agreement → agent D reviewed every one visually on whole-meter crops.
- Rejected visually: 17 (ambiguous drums, glare, blurred, LCD showing a different register, multi-meter board).
- Type fixes: 9 → TAGADOD, 2 → MECHANICAL (DDS858 drums), 1 → GLORY, 1 → CHINT.
- **+258 rows** `confidence=4strong+visual`, `labeller=agentD`: CRYSTAL 77, SMART_YELLOW 70, TAGADOD 34, OTHER 30, KENWELL 22, MECHANICAL 22, GLORY 2, CHINT 1.
- Crops: private `erp/by_type/<TYPE>/` (index.csv source=4strong+visual).
- labels_agentD.csv total: 1021 rows.
