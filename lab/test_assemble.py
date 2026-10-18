"""Unit tests for the reference reading assembler (python3 -m pytest lab/test_assemble.py or python3 test_assemble.py)."""
import assemble as A


def box(cls, x, y=10, w=20, h=40, score=0.9):
    return (cls, score, x, y, x + w, y + h)


def test_plain_six_digits_with_small_decimals():
    dets = [box(int(c), 10 + i * 30) for i, c in enumerate("003155")]
    dets += [box(4, 200, y=30, w=10, h=20), box(2, 215, y=30, w=10, h=20)]  # small decimals, no dot
    r = A.assemble(dets, 400, 64)
    assert r.status == "OK" and r.text == "003155" and r.value == "3155" and r.confident


def test_dot_separates_decimals_of_equal_height():
    dets = [box(int(c), 10 + i * 30) for i, c in enumerate("21")]
    dets.append((10, 0.8, 66, 44, 72, 50))  # dot between digit 2 and 3
    dets += [box(4, 80), box(8, 110)]
    r = A.assemble(dets, 400, 64)
    assert r.text == "21" and r.value == "21"


def test_secondary_smaller_line_is_ignored():
    dets = [box(int(c), 10 + i * 30) for i, c in enumerate("000538")]
    dets += [box(0, 20, y=55, w=8, h=14), box(5, 32, y=55, w=8, h=14)]  # "0.5A" line below
    r = A.assemble(dets, 400, 80)
    assert r.text == "000538"


def test_missing_digit_is_flagged_not_guessed():
    dets = [box(int(c), 10 + i * 30) for i, c in enumerate("0067")] + [box(1, 10 + 5 * 30), box(9, 10 + 6 * 30)]
    r = A.assemble(dets, 400, 64)
    assert r.status == "MISSING_DIGIT" and not r.confident


def test_alternative_class_makes_digit_uncertain():
    dets = [box(int(c), 10 + i * 30) for i, c in enumerate("0024")]
    dets.append(box(8, 10 + 3 * 30, score=0.6))  # same box as the '4', competing '8'
    r = A.assemble(dets, 400, 64)
    assert r.text == "0024" and r.digits[3].uncertain and not r.confident


def test_low_score_digit_is_uncertain_but_reading_returned():
    dets = [box(int(c), 10 + i * 30, score=(0.3 if i == 2 else 0.9)) for i, c in enumerate("0024")]
    r = A.assemble(dets, 400, 64)
    assert r.text == "0024" and r.digits[2].uncertain and not r.confident


def test_empty_when_no_digits():
    assert A.assemble([(10, 0.9, 1, 1, 5, 5)], 100, 50).status == "EMPTY"
    assert A.assemble([], 100, 50).value == ""


def test_too_many_digits():
    dets = [box(1, 10 + i * 30) for i in range(9)]
    assert A.assemble(dets, 400, 64).status == "TOO_MANY_DIGITS"


def test_far_away_digits_split_off():
    dets = [box(int(c), 10 + i * 30) for i, c in enumerate("2887")] + [box(1, 330), box(5, 360)]
    r = A.assemble(dets, 400, 64)
    assert r.text == "2887"


def test_truth_from_boxes_matches_assembler_rules():
    boxes = [(0, 10, 10, 30, 50), (3, 40, 10, 60, 50), (10, 62, 44, 66, 48), (1, 70, 10, 90, 50)]
    assert A.truth_from_boxes(boxes, (11, 10, 10, 90, 50)) == "03"


if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("ok  ", name)
            except AssertionError:
                fails += 1
                print("FAIL", name)
    sys.exit(1 if fails else 0)
