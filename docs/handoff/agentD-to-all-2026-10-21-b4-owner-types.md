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
