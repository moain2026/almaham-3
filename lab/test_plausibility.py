"""Unit tests for plausibility.py (python3 -m pytest lab/test_plausibility.py or python3 test_plausibility.py)."""
import plausibility as P


def d(text, weak=None):
    """digits with top-1 = text; weak = {pos: (alt_cls, alt_score, score)}"""
    out = []
    for i, ch in enumerate(text):
        if weak and i in weak:
            a, sa, s = weak[i]
            out.append((int(ch), s, a, sa))
        else:
            out.append((int(ch), 0.95, -1, 0.0))
    return out


def test_check_ok_normal_month():
    c = P.check("003255", "003155", 30, daily_avg=4)
    assert c.status == "OK" and c.delta == 100


def test_check_reject_decrease():
    assert P.check("003055", "003155", 30).status == "REJECT"


def test_check_rollover():
    c = P.check("000020", "999990", 10, cells=6)
    assert c.status == "OK" and c.delta == 30 and "rollover" in c.reasons


def test_check_warn_spike():
    assert P.check("004155", "003155", 30, daily_avg=5).status == "WARN"   # 33/day vs avg 5


def test_check_hard_ceiling():
    assert P.check("903155", "003155", 30).status == "REJECT"


def test_check_zero_long():
    assert P.check("003155", "003155", 30).status == "WARN"


def test_check_no_history():
    assert P.check("003155", None, None).status == "NO_HISTORY"


def test_correct_keeps_plausible_top1():
    r = P.correct(d("003255"), "003155", 30, daily_avg=4)
    assert r.status == "KEPT" and r.text == "003255"


def test_correct_8_vs_3_confusion():
    # reader read 008255 (8 at pos 2, runner-up 3); history 003155 -> only 003255 is plausible
    r = P.correct(d("008255", {2: (3, 0.4, 0.55)}), "003155", 30, daily_avg=4)
    assert r.status == "CORRECTED" and r.text == "003255" and r.changed == [2]


def test_correct_never_invents_class():
    # implausible and no alternative proposed -> unchanged, flagged
    r = P.correct(d("008255"), "003155", 30, daily_avg=4)
    assert r.status == "IMPLAUSIBLE" and r.text == "008255"


def test_correct_ambiguous_two_plausible():
    # pos 4 alt and pos 5 alt both give plausible readings -> ambiguous, keep top-1, UI must ask
    r = P.correct(d("002199", {4: (5, 0.4, 0.5), 5: (1, 0.4, 0.5)}), "003155", 30, daily_avg=4)
    # top1 002199 decreases -> not OK; candidates 002159/002191/002151 all < 003155 -> none plausible
    assert r.status == "IMPLAUSIBLE"
    r = P.correct(d("003999", {3: (1, 0.4, 0.5), 4: (6, 0.45, 0.5)}), "003155", 30, daily_avg=4)
    # 003199 and 003169? 003199 (pos3->1) OK, 003969 no, 003169 (both) OK -> 2 plausible -> AMBIGUOUS
    assert r.status == "AMBIGUOUS" and r.text == "003999"


def test_vote_majority_and_missing_digit_frame():
    v = P.vote(["003155", "003155", "008155", "03155"])
    assert v.text == "003155" and v.n_frames == 4
    assert abs(v.agreement[2] - 0.5) < 1e-9 and not v.confident


def test_vote_confident():
    v = P.vote(["003155", "003155", "003155", "003156"])
    assert v.text == "003155" and v.confident  # last digit 3/4 = 0.75 >= VOTE_AGREE_MIN 0.6
    v2 = P.vote(["003155", "003156"])
    assert not v2.confident  # 1/2 = 0.5 < 0.6


if __name__ == "__main__":
    import sys
    fails = 0
    for k, f in sorted(globals().items()):
        if k.startswith("test_"):
            try:
                f()
                print("ok  ", k)
            except AssertionError as e:
                fails += 1
                print("FAIL", k, e)
    sys.exit(1 if fails else 0)
