"""Unit/property tests. Synthetic pixels test mechanics, NOT field accuracy."""
from itertools import product
import importlib.util
import unittest

import cv2
import numpy as np

import bench_optical_evidence as bench
import optical_evidence as oe
import serial_identity as si


class SegmentLogicTests(unittest.TestCase):
    def test_all_supported_glyphs(self):
        for digit, bits in oe.PATTERNS:
            self.assertEqual(oe.decode_erasure(bits), [digit])

    def test_all_single_erasures_keep_truth(self):
        for digit, bits in oe.PATTERNS:
            for i in range(7):
                erased = list(bits)
                erased[i] = None
                self.assertIn(digit, oe.decode_erasure(erased))

    def test_every_ternary_word_is_exact_constraint_intersection(self):
        for states in product((-1, 0, 1), repeat=7):
            expected = sorted({d for d, b in oe.PATTERNS
                               if all(s == -1 or s == v for s, v in zip(states, b))})
            self.assertEqual(oe.decode_erasure(states), expected)

    def test_erased_middle_is_not_forced_to_zero_or_eight(self):
        self.assertEqual(oe.decode_erasure([1, 1, 1, 1, 1, 1, None]), ['0', '8'])

    def test_missing_all_evidence_is_not_zero(self):
        self.assertEqual(len(oe.decode_erasure([None] * 7)), 10)
        self.assertEqual(oe.decode_erasure([0] * 7), [])

    def test_distance_one_cannot_correct_single_bit_errors(self):
        self.assertEqual(oe.code_distance(), 1)
        # Middle segment added to 0 makes another valid digit, 8.
        self.assertEqual(oe.decode_erasure([1] * 7), ['8'])

    def test_invalid_states(self):
        for invalid in ([1] * 6, [2] * 7, ['1'] * 7):
            with self.assertRaises(ValueError):
                oe.decode_erasure(invalid)


class PhotometryTests(unittest.TestCase):
    def test_background_plane_cancels(self):
        yy, xx = np.mgrid[:72, :40]
        bg = 140 + xx * .4 + yy * .3
        im = np.stack([bg, bg + 10, bg - 10], 2).astype(np.uint8)
        residual = oe.local_contrast(im)
        self.assertLess(float(residual.max()), .015)

    def test_dark_stroke_survives_and_holes_stay_clean(self):
        im = np.full((72, 40, 3), 190, np.uint8)
        im[1:10, 10:30] = 40
        vals = oe.measure_segments(oe.local_contrast(im))
        self.assertGreater(vals[0], .6)
        self.assertLess(vals[6], .02)

    def test_multiplicative_illumination_invariance(self):
        im = np.full((72, 40, 3), 200, np.uint8)
        im[1:10, 10:30] = 80
        a = oe.local_contrast(im)
        b = oe.local_contrast((im * .6).astype(np.uint8))
        np.testing.assert_allclose(a, b, atol=.01)

    def test_blank_image_abstains(self):
        for level in (0, 127, 255):
            r = oe.read_evidence(np.full((96, 400, 3), level, np.uint8), 6)
            self.assertEqual(r['value'], '')
            self.assertIsNone(r['calibrated_probability'])

    def test_bad_input_rejected(self):
        for im in (None, np.zeros((0, 0, 3), np.uint8), np.zeros((8, 8)),
                   np.zeros((8, 8, 4), np.uint8)):
            with self.assertRaises(ValueError):
                oe.read_evidence(im)

    def test_geometry_can_reconstruct_missing_cell_without_label(self):
        boxes = [(10, 10, 20, 70), (36, 10, 20, 70), (88, 10, 20, 70),
                 (114, 10, 20, 70), (140, 10, 20, 70)]
        g = oe._lattice(boxes, (100, 200), oe.DEFAULT)
        self.assertEqual(g['inserted'], 1)
        self.assertEqual(len(g['cells']), 6)


class ConsensusTests(unittest.TestCase):
    def test_empty_and_tied_votes_abstain(self):
        self.assertEqual(oe.family_consensus([])['value'], '')
        rows = [('a', 'x', '12'), ('a', 'y', '13'), ('b', 'x', '12')]
        self.assertEqual(oe.family_consensus(rows)['value'], '')

    def test_two_families_agree(self):
        rows = [('a', 'x', '12'), ('b', 'x', '12'), ('c', 'x', '')]
        self.assertEqual(oe.family_consensus(rows)['value'], '12')

    def test_third_family_conflict_is_not_outvoted(self):
        rows = [('a', 'x', '12'), ('b', 'x', '12'), ('c', 'x', '13')]
        self.assertEqual(oe.family_consensus(rows)['value'], '')

    def test_duplicate_examinations_idempotent(self):
        rows = [('a', 'x', '12'), ('b', 'x', '12')]
        self.assertEqual(oe.family_consensus(rows), oe.family_consensus(rows * 100))

    def test_one_family_cannot_impersonate_two(self):
        rows = [('a', str(i), '12') for i in range(100)]
        self.assertEqual(oe.family_consensus(rows)['value'], '')

    def test_conflicting_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            oe.family_consensus([('a', 'x', '12'), ('a', 'x', '13')])

    def test_abstentions_count_in_denominator(self):
        rows = [(f, str(i), '12' if i == 0 else '') for f in ('a', 'b') for i in range(10)]
        self.assertEqual(oe.family_consensus(rows)['value'], '')


class BoundTests(unittest.TestCase):
    def test_zero_errors_on_46_does_not_prove_one_percent(self):
        self.assertGreater(oe.zero_error_upper_bound(46), .06)
        self.assertLess(oe.zero_error_upper_bound(299), .01)
        self.assertGreater(oe.zero_error_upper_bound(298), .01)

    def test_empty_sample_cannot_establish_accuracy(self):
        self.assertEqual(oe.zero_error_upper_bound(0), 1.0)
        with self.assertRaises(ValueError):
            oe.zero_error_upper_bound(-1)


class BenchmarkContractTests(unittest.TestCase):
    def test_argb_decodes_channels_and_preserves_pixels(self):
        header = np.array([2, 1], dtype='>i4').tobytes()
        raw = header + np.array([0xff123456, 0xffabcdef], dtype='>u4').tobytes()
        decoded = bench.decode_argb(raw)
        np.testing.assert_array_equal(decoded, [[[0x56, 0x34, 0x12], [0xef, 0xcd, 0xab]]])

    def test_bad_argb_rejected_before_large_allocation(self):
        for raw in (b'', b'12345678', np.array([10000000, 10000000], dtype='>i4').tobytes(),
                    np.array([1, 1], dtype='>i4').tobytes() + bytes(4)):
            with self.assertRaises(ValueError):
                bench.decode_argb(raw)

    def test_legacy_short_answer_filter_is_not_universal(self):
        votes = [('a', 'v1', '0'), ('b', 'v1', '0')]
        self.assertEqual(bench.flat_vote(votes, .2, 0), '0')
        self.assertEqual(bench.flat_vote(votes, .2, 2), '')

    def test_error_denominators_and_no_answers(self):
        truth = {'a': {'reading': '12'}, 'b': {'reading': '13'}}
        result = bench.score({'a': '', 'b': '99'}, truth)
        self.assertEqual(result['error_among_accepted'], 1.)
        self.assertEqual(result['wrong_per_total'], .5)
        self.assertIsNone(bench.score({'a': ''}, truth)['error_among_accepted'])


class IdentityTests(unittest.TestCase):
    def test_serial_leading_zeros_not_removed(self):
        r = si.resolve_identity(['000123'], {'000123': 'test-meter'})
        self.assertEqual(r['serial'], '000123')
        self.assertNotIn('reading', r)

    def test_no_fuzzy_registry_correction(self):
        r = si.resolve_identity(['00123'], {'000123': 'test-meter'})
        self.assertEqual(r['status'], 'unregistered_serial')

    def test_two_meter_barcodes_not_guessed(self):
        r = si.resolve_identity(['001', '002'], {'001': 'test-meter'})
        self.assertEqual(r['status'], 'multiple_barcodes')
        self.assertEqual(r['serial'], '')

    def test_duplicate_symbol_is_one_identity(self):
        self.assertEqual(si.resolve_identity(['001'] * 4, {'001': 'm'})['serial'], '001')

    def test_untrusted_payload_not_executed_or_treated_as_serial(self):
        for s in ('https://bad.invalid', '<script>', '1\n2', 'A' * 65):
            self.assertEqual(si.resolve_identity([s], {s: 'm'})['status'], 'unsupported_payload')

    @unittest.skipUnless(importlib.util.find_spec('zxingcpp'), 'optional ZXing dependency absent')
    def test_generated_qr_and_code128_decode(self):
        import zxingcpp as zx
        for fmt in (zx.BarcodeFormat.QRCode, zx.BarcodeFormat.Code128):
            gray = np.asarray(zx.write_barcode(fmt, '000123456789', width=400, height=180, quiet_zone=12))
            bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            r = si.read_identity(bgr, {'000123456789': 'synthetic-meter'})
            self.assertEqual(r['serial'], '000123456789')
            self.assertEqual(si.read_identity(bgr, {})['status'], 'unregistered_serial')


if __name__ == '__main__':
    cv2.setNumThreads(1)
    unittest.main()
