"""Per-digit vote between DigitNet (neural) and forensic_reader (deterministic) — contract §5.

Rule (position-aligned from the RIGHT, since meter integers are right-anchored and the left cells are zeros):
  * both agree on the digit            -> keep, conf = max(conf_a, conf_b)
  * only one engine returned a reading -> keep it, its own conf; digit uncertain if conf < HIGH
  * disagree at a position             -> take the one with conf >= HIGH if exactly one is high; else uncertain,
                                          keep the higher-conf one but mark uncertain (UI colours it)
  * different lengths                  -> if one is high-confidence on all its digits, take it; else take the longer
                                          reading, mark the unmatched positions uncertain
Output: Reading-like dict {text, value, digits:[{cls, conf, uncertain, src}], confident, status}.
Measured on the 46 photos by eval_vote.py (exact, wrong&confident) for A/B/vote.
"""
HIGH = 0.8


def _digits(reading):
    """Normalise either engine's output to [(cls, conf)]."""
    if reading is None:
        return []
    if isinstance(reading, dict):
        return [(int(d["cls"]), float(d["conf"])) for d in reading.get("digits", [])]
    return [(d.cls, min(d.score, 1.0) * (1.0 if d.seg_agree >= 6 / 7 and d.alt_score < 0.5 * d.score else 0.5)) for d in reading.digits]


def vote(neural, forensic):
    a, b = _digits(neural), _digits(forensic)
    if not a and not b:
        return {"text": "", "value": "", "digits": [], "confident": False, "status": "EMPTY"}
    if not a or not b:
        src = "neural" if a else "forensic"
        ds = [{"cls": c, "conf": p, "uncertain": p < HIGH, "src": src} for c, p in (a or b)]
        return _finish(ds, "SINGLE")
    if len(a) != len(b):
        a_high = all(p >= HIGH for _, p in a)
        b_high = all(p >= HIGH for _, p in b)
        if a_high and not b_high:
            return _finish([{"cls": c, "conf": p, "uncertain": False, "src": "neural"} for c, p in a], "LEN_NEURAL")
        if b_high and not a_high:
            return _finish([{"cls": c, "conf": p, "uncertain": False, "src": "forensic"} for c, p in b], "LEN_FORENSIC")
    n = max(len(a), len(b))
    ra = [None] * (n - len(a)) + a
    rb = [None] * (n - len(b)) + b
    ds = []
    for x, y in zip(ra, rb):
        if x is None or y is None:
            c, p = x or y
            ds.append({"cls": c, "conf": p, "uncertain": True, "src": "neural" if x else "forensic"})
        elif x[0] == y[0]:
            ds.append({"cls": x[0], "conf": max(x[1], y[1]), "uncertain": False, "src": "both"})
        else:
            xa, yb = x[1] >= HIGH, y[1] >= HIGH
            if xa and not yb:
                ds.append({"cls": x[0], "conf": x[1], "uncertain": False, "src": "neural"})
            elif yb and not xa:
                ds.append({"cls": y[0], "conf": y[1], "uncertain": False, "src": "forensic"})
            else:
                best = x if x[1] >= y[1] else y
                ds.append({"cls": best[0], "conf": best[1], "uncertain": True, "src": "conflict"})
    return _finish(ds, "VOTE")


def _finish(ds, status):
    text = "".join(str(d["cls"]) for d in ds)
    value = str(int(text)) if text.isdigit() else ""
    return {"text": text, "value": value, "digits": ds, "confident": bool(ds) and not any(d["uncertain"] for d in ds), "status": status}
