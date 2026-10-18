"""Post-hoc audit + fresh preregistered challenge for full-observation policy.

The old challenge selected this policy, so only the new seed is a fresh synthetic
check. Neither set establishes field accuracy. Never overwrite the old raw results.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time

import cv2
import numpy as np

from bench_profile_reader import SYNTHETIC_CELLS, render_scene, summarize, synthetic_profile
import paths
from profile_policy import require_observed_segments
import profile_reader as pr


def fresh_challenge():
    rng = np.random.default_rng(20261020)
    profile = synthetic_profile()
    rows = []
    for index in range(40):
        text = ''.join(str(v) for v in rng.integers(0, 10, 6))
        exposure, angle = float(rng.uniform(.5, 1.15)), float(rng.uniform(-3, 3))
        dx, dy = (float(v) for v in rng.uniform(-3, 3, 2))
        sigma = float(rng.uniform(.3, 1.1))
        image = render_scene(text, ghost=index % 3 == 0).astype(float) * exposure
        image += rng.normal(0, 1.5, image.shape)
        image = cv2.GaussianBlur(np.clip(image, 0, 255).astype(np.uint8), (5, 5), sigma)
        matrix = cv2.getRotationMatrix2D((177, 74), angle, 1)
        matrix[:, 2] += (dx, dy)
        image = cv2.warpAffine(image, matrix, (354, 148), borderMode=cv2.BORDER_REFLECT)
        blocked = image.copy()
        x0, y0, x1, y1 = SYNTHETIC_CELLS[int(rng.integers(0, 6))]
        cv2.rectangle(blocked, (x0 + 5, y0 + 8), (x1 - 5, y1 - 8), (245, 245, 245), -1)
        for mode, frame in [('fresh_mixed', image), ('fresh_local_glare', blocked)]:
            t0 = time.perf_counter()
            result = require_observed_segments(pr.read_frames([frame], profile, True))
            rows.append({'truth': str(int(text)), 'mode': mode, 'result': result,
                         'parameters': {'exposure': exposure, 'angle': angle, 'dx': dx, 'dy': dy,
                                        'blur_sigma': sigma, 'ghosts': index % 3 == 0},
                         'ms': 1000 * (time.perf_counter() - t0)})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=paths.RESULTS_ENGINES / 'profile_policy_2026-10-18.json')
    args = parser.parse_args()
    cv2.setNumThreads(1)
    old_path = paths.RESULTS_ENGINES / 'profile_reader_2026-10-18.json'
    old = json.loads(old_path.read_text())
    posthoc, changes = {}, []
    for group in ('synthetic', 'stress', 'real'):
        rows = []
        for row in old[group]['rows']:
            gated = require_observed_segments(row['result'])
            rows.append({**row, 'result': gated})
            if row['result']['value'] != gated['value']:
                changes.append({'group': group, 'id': row.get('id'), 'mode': row['mode'],
                                'truth': row['truth'], 'before': row['result']['value'],
                                'after': gated['value'], 'reason': gated['status']})
        posthoc[group] = summarize(rows)
    fresh = fresh_challenge()
    report = {'policy': 'all_segments_observed_v1', 'production_approved': False,
              'posthoc_summary': posthoc, 'posthoc_changes': changes,
              'old_result_sha256': hashlib.sha256(old_path.read_bytes()).hexdigest(),
              'fresh_seed': 20261020, 'fresh_summary': summarize(fresh), 'fresh_rows': fresh,
              'warning': 'New seed is a fresh synthetic check only; do not claim independent real-data accuracy.',
              'source_sha256': {p: hashlib.sha256((paths.LAB / p).read_bytes()).hexdigest()
                                for p in ('profile_reader.py', 'profile_policy.py', 'bench_profile_policy.py', 'bench_profile_reader.py')},
              'command': 'OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python lab/bench_profile_policy.py --out ' + str(args.out),
              'hardware': 'sandbox Linux x86_64, OpenCV threads=1, no phone'}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'posthoc_summary': posthoc, 'fresh_summary': report['fresh_summary']}, indent=2))


if __name__ == '__main__':
    main()
