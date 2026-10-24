# lab/tools — one-off helpers used by agent S (kept so nothing lives only in a sandbox)
- `eval_one.sh <loc.pt> <rd.pt> <tag>` — full evaluation of a weight pair: eval_ckpt (49 A/B) + eval_testset_human (34) + risk_coverage (73). Log in lab/logs/eval_<tag>.log. Run with `setsid nohup … &`, 1 thread.
- `seed_analysis.py` — seed-variance study over autotrain results (docs/research/autotrain-seed-analysis-2026-10-24.md).
Analysis tools in lab/ proper: `fault_split.py` (locator vs reader attribution on the 49), `dets_oracle.py` (raw digit sequences on oracle crops), `ghost_study.py` (post-processing rule study, cached dets), `fit_diag.py` (train-vs-val fit), `build_m4_input.py` (R verdicts -> text_locate json).
Data artefacts (small JSON, no photos): data/fault_check_ref_2026-10-24.json, data/locator_residuals_49.json, data/ghost_cache.json.
