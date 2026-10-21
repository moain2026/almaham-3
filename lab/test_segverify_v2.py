"""Independent rectangular-stroke fixtures (not the verifier's polygon renderer)."""
import unittest
from types import SimpleNamespace

import cv2
import numpy as np

import segverify_v2 as v

# Explicit fixtures, deliberately not imported from the implementation.
PATTERNS = ("abcdef", "bc", "abged", "abgcd", "fgbc", "afgcd", "afgedc", "abc", "abcdefg", "abcdfg")


def fixture(cls, bg=220, fg=35, ghost=None):
    im = np.full((88, 62), bg, np.uint8)
    strokes = {"a": (20, 10, 39, 15), "b": (40, 16, 45, 41),
               "c": (40, 46, 45, 71), "d": (20, 72, 39, 77),
               "e": (14, 46, 19, 71), "f": (14, 16, 19, 41),
               "g": (20, 41, 39, 46)}
    for name, rect in strokes.items():
        color = fg if name in PATTERNS[cls] else ghost
        if color is not None:
            a, b, c, d = rect
            im[b:d + 1, a:c + 1] = color
    return im, (14, 10, 46, 78)


class SegmentVerifierV2Tests(unittest.TestCase):
    def assert_digit(self, cls, **kwargs):
        im, box = fixture(cls, **kwargs)
        evidence = v.segment_ink(im, *box)
        self.assertIsNotNone(evidence)
        self.assertEqual(v.best_pattern_class(evidence)[0], cls)
        self.assertTrue(np.isfinite(evidence.strengths).all())
        self.assertTrue(np.all((evidence.class_scores >= 0) & (evidence.class_scores <= 1)))
        self.assertGreater(v.agreement(evidence, cls), 0)
        return evidence

    def test_0(self): self.assert_digit(0)
    def test_1(self): self.assert_digit(1)
    def test_2(self): self.assert_digit(2)
    def test_3(self): self.assert_digit(3)
    def test_4(self): self.assert_digit(4)
    def test_5(self): self.assert_digit(5)
    def test_6(self): self.assert_digit(6)
    def test_7(self): self.assert_digit(7)
    def test_8(self): self.assert_digit(8)
    def test_9(self): self.assert_digit(9)

    def test_narrow_one(self):
        im, _ = fixture(1)
        evidence = v.segment_ink(im, 39, 10, 46, 78)
        self.assertTrue(evidence.narrow)
        self.assertEqual(v.best_pattern_class(evidence)[0], 1)

    def test_faint_ghosts_all_digits(self):
        for cls in range(10):
            with self.subTest(cls=cls):
                self.assert_digit(cls, ghost=175)

    def test_light_on_dark(self):
        for cls in range(10):
            with self.subTest(cls=cls):
                e = self.assert_digit(cls, bg=25, fg=215, ghost=55)
                self.assertEqual(e.polarity, "light_on_dark")

    def test_dark_display_is_not_necessarily_inverted(self):
        e = self.assert_digit(2, bg=75, fg=15)
        self.assertEqual(e.polarity, "dark_on_light")

    def test_otsu_endpoint_not_lost(self):
        self.assert_digit(0, bg=255, fg=0)

    def test_slanted_digit(self):
        im, _ = fixture(2)
        # Whole-cell shear: top is shifted right, bottom remains in place.
        matrix = np.float32([[1, -.16, 13], [0, 1, 0]])
        im = cv2.warpAffine(im, matrix, (80, 88), borderValue=220)
        evidence = v.segment_ink(im, 14, 10, 58, 78)
        self.assertEqual(v.best_pattern_class(evidence)[0], 2)

    def test_planar_background_is_unknown(self):
        y, x = np.mgrid[:80, :60]
        im = (80 + x + y).astype(np.uint8)
        self.assertIsNone(v.segment_ink(im, 10, 10, 45, 70))

    def test_blank_is_not_one_or_perfect_agreement(self):
        e = v.segment_ink(np.full((64, 48), 150, np.uint8), 4, 4, 40, 60)
        self.assertIsNone(e)
        self.assertEqual(v.best_pattern_class(e), (-1, 0.0))
        self.assertEqual(v.agreement(e, 1), 0)
        self.assertIsNone(v.on_pattern(e))

    def test_invalid_and_small_boxes(self):
        im, _ = fixture(8)
        for box in [(0, 0, 10, 15), (10, 10, 5, 30), (0, 0, 0, 50),
                    (100, 0, 120, 40), (float('nan'), 0, 20, 40), (0, 0, float('inf'), 40)]:
            with self.subTest(box=box):
                self.assertIsNone(v.segment_ink(im, *box))

    def test_uint8_and_grayscale_contract(self):
        for image in [np.zeros((20, 20, 3), np.uint8), np.zeros((20, 20), float)]:
            with self.assertRaises(ValueError):
                v.segment_ink(image, 0, 0, 20, 20)

    def test_invalid_class_rejected(self):
        with self.assertRaises(ValueError):
            v.agreement(None, 10)

    def test_verify_never_rewrites_reader_class(self):
        im, box = fixture(2)
        d = SimpleNamespace(cls=8, x1=box[0], y1=box[1], x2=box[2], y2=box[3])
        self.assertEqual(v.verify(im, [d]), 1)
        self.assertEqual(d.cls, 8)
        self.assertEqual(d.seg_cls, 2)
        self.assertTrue(d.seg_valid)

    def test_missing_evidence_is_not_confident(self):
        d = SimpleNamespace(cls=8, x1=0, y1=0, x2=12, y2=10)
        self.assertEqual(v.verify(np.full((30, 30), 120, np.uint8), [d]), 1)
        self.assertEqual((d.seg_agree, d.seg_cls, d.seg_valid), (0., -1, False))

    def test_all_on_not_relative_midpoint_off(self):
        e = self.assert_digit(8)
        self.assertTrue(np.all(v.on_pattern(e)))


if __name__ == '__main__':
    unittest.main()
