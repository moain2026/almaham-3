"""Frozen profile-reader experiments. Synthetic frames are NOT field accuracy.

python lab/bench_profile_reader.py --out benchmark/results/engines/profile_reader_2026-10-18.json
Real fixtures use same-image geometry enrollment and --register=False explicitly:
this measures recognition with calibrated geometry, not automatic localization.
"""
import argparse
from dataclasses import asdict
import csv
import hashlib
import json
from pathlib import Path
import platform
import time

import cv2
import numpy as np

import bench_optical_evidence as old_bench
import paths
import profile_reader as pr
import sevenseg as v1


SYNTHETIC_CELLS = tuple((28 + i * 50, 36, 64 + i * 50, 116) for i in range(6))


def render_scene(text, ghost=False):
    """Independent polygon renderer, no reader sampling masks used to draw glyphs."""
    if len(text) != 6 or not text.isascii() or not text.isdigit():
        raise ValueError('renderer needs six ASCII digits')
    yy, xx = np.mgrid[:148, :354]
    base = 175 + .05 * xx + .035 * yy
    image = np.stack([base + 6, base + 10, base], 2).astype(np.uint8)
    cv2.rectangle(image, (8, 10), (344, 138), (75, 80, 75), 2)
    cv2.putText(image, 'STATIC METER kWh', (18, 26), cv2.FONT_HERSHEY_SIMPLEX, .4, (55, 70, 55), 1)
    for x in (15, 155, 330):
        cv2.circle(image, (x, 130), 3, (40, 55, 50), -1)
    # Canonical cell 36x80; six-vertex segments retain realistic disconnected ends.
    shapes = {
        'a': [(5, 0), (31, 0), (35, 4), (30, 8), (6, 8), (1, 4)],
        'g': [(6, 36), (30, 36), (35, 40), (30, 44), (6, 44), (1, 40)],
        'd': [(6, 72), (30, 72), (35, 76), (31, 79), (5, 79), (1, 76)],
        'f': [(0, 6), (7, 11), (7, 33), (1, 38), (0, 33)],
        'b': [(35, 6), (35, 33), (29, 38), (28, 33), (28, 11)],
        'e': [(0, 43), (7, 48), (7, 69), (1, 74), (0, 69)],
        'c': [(35, 43), (35, 69), (29, 74), (28, 69), (28, 48)],
    }
    for digit, (x0, y0, _, _) in zip(text, SYNTHETIC_CELLS):
        for segment, polygon in shapes.items():
            on = segment in v1.DIGITS[digit]
            if on or ghost:
                color = (35, 40, 32) if on else (155, 174, 168)
                cv2.fillConvexPoly(image, np.array(polygon, np.int32) + (x0, y0), color)
    return image


def synthetic_profile(verified=True):
    # Digit values intentionally differ from all evaluated targets.
    return pr.Profile(SYNTHETIC_CELLS, render_scene('888888'), verified=verified, name='synthetic-six-cell')


def occlude(image, left, right):
    result = image.copy()
    result[:, left:right] = 250
    return result


def synthetic_experiment():
    profile = synthetic_profile()
    rng = np.random.default_rng(20261018)
    targets = ['000782', '002921', '123456', '987654', '111111', '000000']
    targets += [''.join(str(v) for v in rng.integers(0, 10, 6)) for _ in range(24)]
    rows = []
    for text in targets:
        image = render_scene(text)
        matrix = cv2.getRotationMatrix2D((177, 74), 1.5, 1)
        matrix[:, 2] += (2, -1)
        moved = cv2.warpAffine(image, matrix, (354, 148), borderMode=cv2.BORDER_REFLECT)
        left = occlude(image, 130, 158)
        right = occlude(image, 230, 258)
        cases = [('clean', [image], False), ('registered_motion', [moved], True),
                 ('occlusion_a', [left], False), ('complementary_occlusions', [left, right], False)]
        for mode, frames, register in cases:
            t0 = time.perf_counter()
            result = pr.read_frames(frames, profile, register=register)
            rows.append({'kind': 'synthetic', 'truth': str(int(text)), 'mode': mode,
                         'result': result, 'ms': 1000 * (time.perf_counter() - t0)})
    changed = pr.read_frames([render_scene('123456'), render_scene('123457')], profile, False)
    duplicate = pr.read_frames([render_scene('123456')] * 4, profile, False)
    return {'rows': rows, 'changed_reading_control': changed, 'duplicate_control': duplicate,
            'note': '30 generated digit strings, four scenarios each; not 120 independent real scenes.'}


def stress_experiment():
    """Preregistered seed/ranges; settings frozen before these scenes are seen."""
    rng = np.random.default_rng(20261019)
    profile = synthetic_profile()
    rows = []
    for index in range(60):
        text = ''.join(str(v) for v in rng.integers(0, 10, 6))
        exposure = float(rng.uniform(.5, 1.15))
        angle = float(rng.uniform(-3, 3))
        dx, dy = (float(v) for v in rng.uniform(-3, 3, 2))
        sigma = float(rng.uniform(.3, 1.1))
        image = render_scene(text, ghost=index % 3 == 0).astype(float) * exposure
        image += rng.normal(0, 1.5, image.shape)
        image = cv2.GaussianBlur(np.clip(image, 0, 255).astype(np.uint8), (5, 5), sigma)
        matrix = cv2.getRotationMatrix2D((177, 74), angle, 1)
        matrix[:, 2] += (dx, dy)
        image = cv2.warpAffine(image, matrix, (354, 148), borderMode=cv2.BORDER_REFLECT)
        blocked = image.copy()
        cell = SYNTHETIC_CELLS[int(rng.integers(0, 6))]
        x0, y0, x1, y1 = cell
        cv2.rectangle(blocked, (x0 + 5, y0 + 8), (x1 - 5, y1 - 8), (245, 245, 245), -1)
        for mode, frame in [('mixed_nuisance', image), ('mixed_nuisance_local_glare', blocked)]:
            t0 = time.perf_counter()
            result = pr.read_frames([frame], profile, True)
            rows.append({'kind': 'synthetic_stress', 'truth': str(int(text)), 'mode': mode,
                         'parameters': {'exposure': exposure, 'rotation': angle, 'dx': dx, 'dy': dy,
                                        'blur_sigma': sigma, 'ghosts': index % 3 == 0},
                         'result': result, 'ms': 1000 * (time.perf_counter() - t0)})
    return {'seed': 20261019, 'rows': rows, 'note': 'Preregistered synthetic stress only; no threshold tuning after scoring.'}


def real_experiment():
    rows = []
    # Predictions first; reference values are deliberately unavailable here.
    for name, image, source in old_bench.fixture_images():
        try:
            profile = pr.enroll(image, 6, verified=True, name='fixture-calibrated')
        except ValueError as exc:
            modes = list(old_bench.nuisance_probes(image)) + ['original_plus_occlusion', 'derived_exposure_stack']
            for mode in modes:
                rows.append({'id': name, 'mode': mode, 'result': {'value': '', 'status': 'unsupported_layout'},
                             'reason': str(exc), 'source': source, 'ms': None})
            continue
        probes = old_bench.nuisance_probes(image)
        # Fixed geometry from original; no re-enrollment per perturbation.
        cases = [(name, [frame]) for name, frame in probes.items()]
        cases += [('original_plus_occlusion', [probes['original'], probes['erased_vertical_strip']]),
                  ('derived_exposure_stack', [probes['original'], probes['dimmer'], probes['gamma_1.4']])]
        for mode, frames in cases:
            t0 = time.perf_counter()
            result = pr.read_frames(frames, profile, register=False)
            rows.append({'id': name, 'mode': mode, 'result': result, 'source': source,
                         'ms': 1000 * (time.perf_counter() - t0)})
    truth = {r['filename'][:5]: r for r in csv.DictReader(paths.GROUND_TRUTH.open())}
    for row in rows:
        row['truth'] = truth[row['id']]['reading']
        row['uncertain_reference'] = truth[row['id']]['uncertain'] == '1'
    return {'rows': rows, 'note': 'Same-photo geometry calibration; 4 supported / 5 available crops. '
            'No independent holdout, no real temporal frames, registration disabled explicitly.'}


def summarize(rows):
    output = {}
    for mode in sorted({r['mode'] for r in rows}):
        selected = [r for r in rows if r['mode'] == mode]
        good = sum(r['result']['value'] == r['truth'] for r in selected)
        wrong = sum(bool(r['result']['value']) and r['result']['value'] != r['truth'] for r in selected)
        times = [r['ms'] for r in selected if r['ms'] is not None]
        output[mode] = {'n': len(selected), 'correct': good, 'wrong_nonempty': wrong,
                        'abstained': len(selected) - good - wrong,
                        'p50_ms_sandbox': float(np.median(times)) if times else None}
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=paths.RESULTS_ENGINES / 'profile_reader_2026-10-18.json')
    args = parser.parse_args()
    cv2.setNumThreads(1)
    synthetic = synthetic_experiment()
    stress = stress_experiment()
    real = real_experiment()
    report = {'settings': asdict(pr.DEFAULT), 'synthetic': synthetic, 'stress': stress, 'real': real,
              'synthetic_summary': summarize(synthetic['rows']), 'stress_summary': summarize(stress['rows']),
              'real_summary': summarize(real['rows']),
              'source_sha256': {p: hashlib.sha256((paths.LAB / p).read_bytes()).hexdigest()
                                for p in ('profile_reader.py', 'bench_profile_reader.py', 'optical_evidence.py')},
              'hardware': {'platform': platform.platform(), 'python': platform.python_version(),
                           'opencv': cv2.__version__, 'numpy': np.__version__, 'opencv_threads': 1},
              'production_approved': False,
              'command': 'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python lab/bench_profile_reader.py --out ' + str(args.out)}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({k: report[k] for k in ('synthetic_summary', 'stress_summary', 'real_summary')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
