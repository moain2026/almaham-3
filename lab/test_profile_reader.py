"""Safety/geometry regression tests; synthetic success is not field validation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import cv2
import numpy as np

from bench_profile_reader import SYNTHETIC_CELLS, occlude, render_scene, synthetic_profile
import profile_reader as pr
import profile_cli as cli
import paths
from profile_policy import require_observed_segments


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.profile = synthetic_profile()
        cv2.setNumThreads(1)

    def test_explicit_profile_is_valid(self):
        self.profile.validate()
        self.assertFalse(self.profile.metadata()['contains_reading_label'])

    def test_read_all_digit_shapes(self):
        for text in ['012345', '678901', '111111', '000000', '999999']:
            r = pr.read_frames([render_scene(text)], self.profile, False)
            self.assertEqual(r['value'], str(int(text)))
            self.assertIsNone(r['calibrated_probability'])
            self.assertFalse(r['production_approved'])

    def test_reference_digits_do_not_supply_the_answer(self):
        p = pr.Profile(SYNTHETIC_CELLS, render_scene('999999'), verified=True)
        self.assertEqual(pr.read_frames([render_scene('123456')], p, False)['value'], '123456')

    def test_static_alignment_mask_excludes_every_digit(self):
        mask = pr.static_mask(self.profile)
        for x0, y0, x1, y1 in self.profile.cells:
            self.assertFalse(mask[y0:y1, x0:x1].any())

    def test_unverified_profile_never_accepts(self):
        r = pr.read_frames([render_scene('123456')], synthetic_profile(False), False)
        self.assertEqual(r['value'], '')
        self.assertEqual(r['status'], 'unverified_profile')

    def test_bad_and_overlapping_cells_rejected(self):
        for cells in [((-1, 2, 40, 80),), ((20, 20, 40, 80), (30, 20, 50, 80)),
                      ((20, 20, float('nan'), 80),), ()]:
            with self.assertRaises(ValueError):
                pr.Profile(cells, self.profile.template).validate()

    def test_changed_aspect_ratio_rejected(self):
        with self.assertRaises(ValueError):
            pr.canonicalize(np.zeros((100, 100, 3), np.uint8), self.profile)

    def test_no_frames_and_excess_frames_rejected(self):
        for frames in ([], [self.profile.template] * 9):
            with self.assertRaises(ValueError):
                pr.read_frames(frames, self.profile)

    def test_bad_input_rejected(self):
        for image in (None, np.zeros((20, 30), np.uint8), np.zeros((20, 30, 3), float)):
            with self.assertRaises(ValueError):
                pr.read_frames([image], self.profile)


class OcclusionFusionTests(unittest.TestCase):
    def setUp(self):
        self.profile = synthetic_profile()
        self.image = render_scene('123456')
        cv2.setNumThreads(1)

    def test_occluded_segments_are_unknown_not_off(self):
        r = pr.read_frames([occlude(self.image, 130, 158)], self.profile, False)
        self.assertEqual(r['value'], '')
        self.assertIn(-1, r['states'][2])

    def test_two_complementary_occlusions_recover_reading(self):
        a, b = occlude(self.image, 130, 158), occlude(self.image, 230, 258)
        self.assertEqual(pr.read_frames([a], self.profile, False)['value'], '')
        self.assertEqual(pr.read_frames([b], self.profile, False)['value'], '')
        self.assertEqual(pr.read_frames([a, b], self.profile, False)['value'], '123456')

    def test_same_occlusion_does_not_hallucinate(self):
        a = occlude(self.image, 130, 158)
        r = pr.read_frames([a, a.copy(), a.copy()], self.profile, False)
        self.assertEqual(r['value'], '')
        self.assertEqual(r['unique_frames'], 1)
        self.assertEqual(r['duplicate_frames_ignored'], 2)

    def test_duplicate_frames_do_not_raise_support(self):
        one = pr.read_frames([self.image], self.profile, False)
        repeated = pr.read_frames([self.image] * 4, self.profile, False)
        self.assertEqual(one['visible_observations'], repeated['visible_observations'])

    def test_reading_change_never_assembled_into_hybrid_number(self):
        r = pr.read_frames([self.image, render_scene('123457')], self.profile, False)
        self.assertEqual(r['value'], '')
        self.assertEqual(r['status'], 'reading_changed')

    def test_any_known_conflict_abstains(self):
        first = pr.observe(self.image, self.profile, False)
        second = copy.deepcopy(first)
        first['value'] = second['value'] = ''
        second['states'][0][0] = 1 - first['states'][0][0]
        r = pr.fuse_observations([first, second])
        self.assertEqual(r['value'], '')
        self.assertEqual(r['status'], 'conflicting_segment_evidence')

    def test_all_white_has_no_usable_evidence(self):
        r = pr.read_frames([np.full_like(self.image, 255)], self.profile, False)
        self.assertEqual(r['value'], '')

    def test_frame_order_does_not_change_fusion(self):
        a, b = occlude(self.image, 130, 158), occlude(self.image, 230, 258)
        first = pr.read_frames([a, b], self.profile, False)
        second = pr.read_frames([b, a], self.profile, False)
        self.assertEqual(first['states'], second['states'])
        self.assertEqual(first['value'], second['value'])


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        cv2.setNumThreads(1)
        self.profile = synthetic_profile()
        self.image = render_scene('123456')

    def test_static_background_registers_different_digits(self):
        r = pr.read_frames([self.image], self.profile, True)
        self.assertEqual(r['value'], '123456')
        self.assertEqual(r['observations'][0]['alignment']['method'], 'static_background_ecc')

    def test_small_rotation_translation_registers(self):
        m = cv2.getRotationMatrix2D((177, 74), 1.5, 1.)
        m[:, 2] += (2, -1)
        moved = cv2.warpAffine(self.image, m, (354, 148), borderMode=cv2.BORDER_REFLECT)
        r = pr.read_frames([moved], self.profile, True)
        self.assertEqual(r['value'], '123456')

    def test_textureless_template_rejected(self):
        p = pr.Profile(SYNTHETIC_CELLS, np.full_like(self.image, 180), verified=True)
        r = pr.read_frames([self.image], p, True)
        self.assertEqual(r['value'], '')
        self.assertFalse(r['observations'][0]['alignment']['ok'])

    def test_explicit_homography_identity(self):
        rect = pr.rectify_quad(self.image, [[0, 0], [353, 0], [353, 147], [0, 147]], (354, 148))
        np.testing.assert_array_equal(rect, self.image)

    def test_bad_quad_rejected(self):
        for points in ([[0, 0]] * 4, [[0, 0], [353, 147], [353, 0], [0, 147]],
                       [[-1, 0], [353, 0], [353, 147], [0, 147]]):
            with self.assertRaises(ValueError):
                pr.rectify_quad(self.image, points, (354, 148))


class AcceptancePolicyTests(unittest.TestCase):
    def test_unique_digit_with_unobserved_segment_is_not_accepted(self):
        raw = {'value': '7', 'status': 'conditional_singleton', 'states': [[1, 1, 1, 0, 0, -1, 0]]}
        result = require_observed_segments(raw)
        self.assertEqual(result['value'], '')
        self.assertEqual(result['candidate_value'], '7')
        self.assertEqual(raw['value'], '7')
        self.assertEqual(result['observed_segments'], 6)

    def test_complete_observed_digit_keeps_conditional_value(self):
        result = require_observed_segments({'value': '7', 'states': [[1, 1, 1, 0, 0, 0, 0]]})
        self.assertEqual(result['value'], '7')
        self.assertFalse(result['production_approved'])

    def test_missing_evidence_never_accepts(self):
        for states in ([], [[1, 1]], [[None]*7]):
            self.assertEqual(require_observed_segments({'value': '8', 'states': states})['value'], '')

    def test_policy_never_invents_rejected_candidate(self):
        result = require_observed_segments({'value': '', 'states': [[1]*7], 'status': 'unverified_profile'})
        self.assertEqual(result['value'], '')
        self.assertEqual(result['status'], 'unverified_profile')


class PrivateCLITests(unittest.TestCase):
    def setUp(self):
        paths.DATA.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=paths.DATA)
        self.directory = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_profile_round_trip(self):
        profile = synthetic_profile()
        file = self.directory / 'meter.json'
        cli.save_profile(profile, file)
        loaded = cli.load_profile(file)
        np.testing.assert_array_equal(loaded.template, profile.template)
        self.assertEqual(loaded.cells, profile.cells)

    def test_template_hash_tamper_detected(self):
        file = self.directory / 'meter.json'
        cli.save_profile(synthetic_profile(), file)
        obj = json.loads(file.read_text())
        obj['template_sha256'] = '0' * 64
        file.write_text(json.dumps(obj))
        with self.assertRaises(ValueError):
            cli.load_profile(file)

    def test_no_private_outputs_outside_ignored_data(self):
        with self.assertRaises(ValueError):
            cli.private_output(paths.REPO / 'private_customer_image.html')

    def test_preview_does_not_overwrite_profile(self):
        file = self.directory / 'meter.json'
        cli.save_profile(synthetic_profile(), file)
        before = file.read_bytes()
        cli.write_report(file.with_suffix('.html'), [], {'value': ''}, False)
        self.assertEqual(before, file.read_bytes())
        self.assertTrue(file.with_suffix('.result.json').exists())

    def test_full_enroll_read_command_chain(self):
        image = self.directory / 'reference.png'
        cv2.imwrite(str(image), render_scene('123456'))
        cells = self.directory / 'cells.json'
        cells.write_text(json.dumps(SYNTHETIC_CELLS))
        profile = self.directory / 'meter.json'
        command = [sys.executable, str(paths.LAB / 'profile_cli.py')]
        subprocess.run(command + ['enroll', '--image', str(image), '--profile', str(profile),
                                  '--cells', str(cells), '--confirm-layout'], check=True, capture_output=True)
        out = self.directory / 'read.html'
        subprocess.run(command + ['read', '--profile', str(profile), '--images', str(image),
                                  '--out', str(out)], check=True, capture_output=True)
        result = json.loads(out.with_suffix('.result.json').read_text())
        self.assertEqual(result['value'], '123456')
        self.assertIn('لا ضمان', out.read_text())

    def test_report_escapes_untrusted_title(self):
        section, _ = cli.scenario_html('<script>alert(1)</script>', [render_scene('123456')], synthetic_profile())
        self.assertNotIn('<script>', section)
        self.assertIn('&lt;script&gt;', section)


if __name__ == '__main__':
    unittest.main()
