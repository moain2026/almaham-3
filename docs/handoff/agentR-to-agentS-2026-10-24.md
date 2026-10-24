# Agent R → Agent S handoff (2026-10-24)

Private files pushed to main (commit 7ba3f79): erp/review/line_boxes_v2_2026-10-24/verdicts_R.csv (462 rows) and verdicts_R_summary.md.

Recheck: 60 random rows + all 30 fixes. Coordinates are in the EXIF-upright frame (ImageOps.exif_transpose).

## Count per verdict

| verdict | proposals | unlocated | total |
|---|---|---|---|
| ok | 351 | 0 | 351 |
| fix | 15 | 15 | 30 |
| reject | 13 | 68 | 81 |

Of the rejects, 43 are "mechanical".

## Count per meter type

| meter_type | ok | fix | reject |
|---|---|---|---|
| CHINT | 0 | 0 | 3 |
| CRYSTAL | 55 | 7 | 12 |
| GLORY | 3 | 1 | 0 |
| KENWELL | 5 | 0 | 0 |
| MECHANICAL | 0 | 0 | 34 |
| OTHER | 24 | 4 | 9 |
| SMART_YELLOW | 75 | 8 | 13 |
| TAGADOD | 19 | 0 | 5 |
| TOMAS_SMART | 166 | 6 | 4 |
| TOMAS_STATIC | 4 | 4 | 1 |

## Reading vs display (for owner, readings NOT changed)

- 345ef2a1-3389-448c-a3df-4e1268ff2f67: reading mismatch: display shows 331 (label 337)
- document-f60bd56f-f813-5ef5-9852-56b92c99137f: label 2790 omits leading zeros shown on display (002790)
- pending-274446ed-5f18-4932-b0e5-a8a6e9c1734f…: unreadable: top half washed out, last integer digit uncertain (334 vs 337)

## Open item

19 unlocated photos with a readable-looking display were not boxed by R (time ran out). They are marked reject with the note "not boxed by R" and still need a manual box. Filenames are in the private summary.
