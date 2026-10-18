"""Plausibility checks + prior-guided digit correction + multi-frame vote for meter readings (agent T, 2026-10-18).

Pure Python, no numpy / OpenCV, so it ports line-by-line to Kotlin (proposed: app/meterocr/Plausibility.kt, owner A).
It sits AFTER the reader + assembler (assemble.py / vote) and BEFORE the entry field is filled. It never invents
a reading from nothing: it only (a) flags readings that contradict the meter's history, (b) chooses between
alternatives the reader itself proposed (top-2 per digit) when exactly one combination is physically plausible,
(c) fuses several frames of the same meter.

Why: the reader is weakest exactly where history is strongest. An electricity meter reading is monotonic and
grows by a bounded amount per day; its high-order digits almost never change between two visits and its number of
integer cells is fixed. Commercial readers (Anyline, Cognex/ML Kit pipelines in utility apps) all apply this
"expected range" check — see docs/research/agentT-algorithms-2026-10-18.md.

API (all inputs plain types):
    check(value, prev, days, daily_avg=None, cells=None) -> Check
    correct(digits, prev, days, daily_avg=None, cells=None) -> Correction
        digits = [(cls, score, alt_cls, alt_score), ...] left->right, integer part only (assemble.Digit fields)
    vote(frames) -> Vote
        frames = ["003155", "003155", "008155", ...] integer texts (leading zeros kept), "" = no read
"""
from dataclasses import dataclass, field
from itertools import product
from typing import List, Optional, Sequence, Tuple

CONFIG = {
    "MIN_DAILY_KWH": 1.0,        # floor for the expected daily consumption when history is thin
    "MAX_DAILY_FACTOR": 4.0,     # consumption above this x the daily average is implausible (WARN)
    "HARD_DAILY_KWH": 400.0,     # absolute ceiling per day for a residential meter (REJECT above)
    "ROLLOVER_MARGIN": 0.02,     # a decrease is a rollover only if prev is within this fraction of 10^cells
    "MAX_ALT_DIGITS": 3,         # combinations explored: at most this many uncertain digits (2^3 = 8 candidates)
    "ALT_MIN_RATIO": 0.15,       # an alternative is considered only if alt_score >= this x best score
    "VOTE_MIN_FRAMES": 2,        # need at least this many non-empty frames to vote
    "VOTE_AGREE_MIN": 0.6,       # per-position agreement needed for a confident fused digit
}


@dataclass
class Check:
    status: str                  # OK | WARN | REJECT | NO_HISTORY
    reasons: List[str] = field(default_factory=list)
    delta: Optional[int] = None  # consumption since prev (with rollover handled)


def _cells(value_text: str, cells: Optional[int]) -> int:
    return cells if cells else max(len(value_text), 1)


def check(value: str, prev: Optional[str], days: Optional[float], daily_avg: Optional[float] = None,
          cells: Optional[int] = None) -> Check:
    """value/prev: integer readings as text (leading zeros allowed). days: days between the two readings."""
    if not value or not value.isdigit():
        return Check("REJECT", ["empty"])
    if prev is None or not str(prev).isdigit():
        return Check("NO_HISTORY")
    cur, old = int(value), int(prev)
    n = _cells(value, cells)
    reasons = []
    if cells and len(value.lstrip("0") or "0") > cells:
        return Check("REJECT", [f"more than {cells} integer digits"])
    delta = cur - old
    if delta < 0:
        top = 10 ** n
        if old >= top * (1 - CONFIG["ROLLOVER_MARGIN"]):
            delta = cur + top - old
            reasons.append("rollover")
        else:
            return Check("REJECT", [f"reading decreased by {-delta}"], delta)
    d = max(days or 1.0, 1.0)
    expected = max(daily_avg or 0.0, CONFIG["MIN_DAILY_KWH"])
    if delta > CONFIG["HARD_DAILY_KWH"] * d:
        return Check("REJECT", reasons + [f"{delta} kWh in {d:g} days exceeds hard ceiling"], delta)
    if daily_avg and delta > CONFIG["MAX_DAILY_FACTOR"] * expected * d:
        reasons.append(f"consumption {delta / d:.1f}/day > {CONFIG['MAX_DAILY_FACTOR']:g}x average {expected:.1f}")
        return Check("WARN", reasons, delta)
    if delta == 0 and d >= 20:
        reasons.append("zero consumption over 20+ days (meter stopped / wrong meter?)")
        return Check("WARN", reasons, delta)
    return Check("OK", reasons, delta)


@dataclass
class Correction:
    text: str                    # chosen integer text ("" when nothing plausible)
    changed: List[int]           # positions replaced by the reader's own runner-up class
    status: str                  # KEPT | CORRECTED | AMBIGUOUS | IMPLAUSIBLE | NO_HISTORY
    check: Optional[Check] = None
    candidates: int = 0


def correct(digits: Sequence[Tuple[int, float, int, float]], prev: Optional[str], days: Optional[float],
            daily_avg: Optional[float] = None, cells: Optional[int] = None) -> Correction:
    """Choose among the reader's top-2 classes per digit using history. Never changes a digit to a class the reader
    did not propose. If more than one combination is plausible, keep the reader's top-1 when it is plausible,
    otherwise report AMBIGUOUS (the UI should colour the digits and let the user confirm)."""
    top1 = "".join(str(c) for c, _, _, _ in digits)
    if prev is None:
        return Correction(top1, [], "NO_HISTORY", None, 1)
    base = check(top1, prev, days, daily_avg, cells)
    if base.status == "OK":
        return Correction(top1, [], "KEPT", base, 1)
    # candidate positions: digits whose runner-up is a real alternative, weakest first
    pos = [i for i, (c, s, a, sa) in enumerate(digits) if 0 <= a <= 9 and a != c and sa >= CONFIG["ALT_MIN_RATIO"] * s]
    pos = sorted(pos, key=lambda i: digits[i][1])[:CONFIG["MAX_ALT_DIGITS"]]
    best, plausible, n = None, [], 0
    for mask in product((0, 1), repeat=len(pos)):
        if not any(mask):
            continue
        t = list(top1)
        score = 1.0
        for i, (c, s, a, sa) in enumerate(digits):
            score *= s
        for m, i in zip(mask, pos):
            if m:
                c, s, a, sa = digits[i]
                t[i] = str(a)
                score *= sa / max(s, 1e-6)
        n += 1
        txt = "".join(t)
        ck = check(txt, prev, days, daily_avg, cells)
        if ck.status == "OK":
            plausible.append((score, txt, [i for m, i in zip(mask, pos) if m], ck))
    if len(plausible) == 1:
        _, txt, ch, ck = plausible[0]
        return Correction(txt, ch, "CORRECTED", ck, n + 1)
    if len(plausible) > 1:
        plausible.sort(reverse=True)
        return Correction(top1, [], "AMBIGUOUS", base, n + 1)
    return Correction(top1, [], "IMPLAUSIBLE", base, n + 1)


@dataclass
class Vote:
    text: str
    agreement: List[float]       # per position, fraction of frames agreeing with the fused digit
    confident: bool
    n_frames: int


def vote(frames: Sequence[str]) -> Vote:
    """Right-aligned per-position majority over several frames of the same meter (preview buffer / burst)."""
    fs = [f for f in frames if f and f.isdigit()]
    if len(fs) < CONFIG["VOTE_MIN_FRAMES"]:
        return Vote(fs[0] if fs else "", [1.0] * len(fs[0]) if fs else [], False, len(fs))
    # length = most common length (a frame that missed a digit is outvoted)
    lens = {}
    for f in fs:
        lens[len(f)] = lens.get(len(f), 0) + 1
    L = max(lens.items(), key=lambda kv: (kv[1], kv[0]))[0]
    same = [f for f in fs if len(f) == L]
    out, agr = [], []
    for i in range(L):
        counts = {}
        for f in same:
            counts[f[i]] = counts.get(f[i], 0) + 1
        ch, k = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
        out.append(ch)
        agr.append(k / len(fs))
    return Vote("".join(out), agr, min(agr) >= CONFIG["VOTE_AGREE_MIN"], len(fs))
