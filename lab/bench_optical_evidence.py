"""Reproduce independent no-training experiments without original private photos.

The five already-versioned ARGB fixtures are read from a PINNED git commit into
memory. No image is published/written. Predictions are frozen before loading
reference readings. This is exploratory evidence, NOT a new independent holdout.

Run from repo root: OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python lab/bench_optical_evidence.py
Optional synthetic identity experiment: install zxing-cpp==2.3.0 and add --barcode.
"""
import argparse
from collections import Counter
from dataclasses import asdict
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import types

import cv2
import numpy as np

import optical_evidence as oe
import paths
import serial_identity as si
import sevenseg as v1
import sevenseg2 as v2
import sevenseg6 as v6

FIXTURE_REF = '5486ed44510ca1930e1dc119eee08b47a3d6486f'
FIXTURES = {
    '23066': 'c0e932be7eeaf6e4a200ceff603d137c70a73e77',
    '23070': '5d6ba3b0379ef88441e3d1b06842f242d3d3d1bd',
    '23082': '316120c54af24795543a4c381de0161fbb68cd14',
    '23091': '7ea58dab786354748dba422f5a84b7273a7b7e50',
    '23108': 'd8cdfc010233f6e453dad3c550c9ed3dc1bdfecf',
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def decode_argb(raw):
    if len(raw) < 8:
        raise ValueError('truncated ARGB header')
    w, h = (int(x) for x in np.frombuffer(raw[:8], '>i4'))
    if w <= 0 or h <= 0 or w * h > 10_000_000 or len(raw) != 8 + 4 * w * h:
        raise ValueError('invalid ARGB dimensions or length')
    pixels = np.frombuffer(raw[8:], '>u4').reshape(h, w)
    if np.any((pixels >> 24) != 255):
        raise ValueError('transparent fixture unsupported')
    return np.stack([pixels & 255, (pixels >> 8) & 255, (pixels >> 16) & 255], 2).astype(np.uint8)


def fixture_images():
    for name, expected_blob in FIXTURES.items():
        path = f'app/meterocr/src/test/resources/forensic/{name}.argb'
        try:
            raw = subprocess.check_output(['git', 'show', f'{FIXTURE_REF}:{path}'], cwd=paths.REPO)
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f'Fetch source commit first: git fetch origin {FIXTURE_REF}') from exc
        blob = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
        if blob != expected_blob:
            raise ValueError(f'fixture blob mismatch: {name}')
        yield name, decode_argb(raw), {'blob': blob, 'sha256': digest(raw), 'git_path': path}


def nuisance_probes(im):
    h, w = im.shape[:2]
    rotation = cv2.getRotationMatrix2D((w / 2, h / 2), 2, 1)
    glare = im.copy()
    glare[:, int(.46 * w):int(.54 * w)] = 240
    return {
        'original': im,
        'dimmer': np.clip(im.astype(float) * .65, 0, 255).astype(np.uint8),
        'gamma_1.4': np.clip(255 * (im / 255.) ** 1.4, 0, 255).astype(np.uint8),
        'blur_sigma1': cv2.GaussianBlur(im, (5, 5), 1),
        'rotate_2deg': cv2.warpAffine(im, rotation, (w, h), borderMode=cv2.BORDER_REPLICATE),
        'erased_vertical_strip': glare,
    }


def infer_fixtures(repeats):
    rows, probes = [], []
    for name, im, source in fixture_images():
        # Warm-up excluded; no loading/IO time counted as inference time.
        evidence = oe.read_evidence(im, expected_cells=6)
        times = []
        for _ in range(repeats):
            t0 = time.perf_counter()
            actual = oe.read_evidence(im, expected_cells=6)
            times.append(1000 * (time.perf_counter() - t0))
            if actual != evidence:
                raise AssertionError('nondeterministic inference')
        baselines = {m.__name__: m.read_line(im)[0] for m in (v1, v2, v6)}
        rows.append({'id': name, 'shape': list(im.shape), 'source': source,
                     'evidence': evidence, 'baseline_values': baselines, 'warmed_ms': times})
        for variation, probe in nuisance_probes(im).items():
            r = oe.read_evidence(probe, expected_cells=6)
            probes.append({'id': name, 'variation': variation, 'value': r['value'],
                           'top1': r['top1'], 'status': r['status']})
    return rows, probes


def score(values, truth):
    n = len(values)
    exact = sum(v == truth[k]['reading'] for k, v in values.items())
    wrong = sum(bool(v) and v != truth[k]['reading'] for k, v in values.items())
    accepted = exact + wrong
    return {'n': n, 'exact': exact, 'wrong_accepted': wrong, 'abstained': n - accepted,
            'coverage': accepted / n if n else None,
            'error_among_accepted': wrong / accepted if accepted else None,
            'wrong_per_total': wrong / n if n else None,
            'zero_error_upper95_if_independent': oe.zero_error_upper_bound(accepted) if wrong == 0 else None}


def flat_vote(exams, share, minimum_length):
    counts = Counter(t for _, _, t in exams if t and len(t) >= minimum_length)
    if not counts:
        return ''
    text, n = counts.most_common(1)[0]  # source-order tie-break, legacy reconstruction
    return text if n >= share * len(exams) else ''


def cached_audit(truth):
    path = paths.RESULTS_ENGINES / 'grid_variants_lineL.json'
    raw = path.read_bytes()
    grid = json.loads(raw)
    ids = set(next(iter(grid.values())))
    if any(set(v) != ids for v in grid.values()) or ids != set(truth):
        raise ValueError('cached matrix must exactly cover the readable reference set')
    exams = {k: [(name.split('|')[1], name.split('|')[0], v[k]) for name, v in grid.items()] for k in ids}
    policies = {}
    for minimum_length in (0, 2):
        for threshold in (.15, .2, .3):
            key = f'flat_minlen{minimum_length}_share{threshold}'
            values = {k: flat_vote(e, threshold, minimum_length) for k, e in exams.items()}
            policies[key] = {'scores': score(values, truth), 'predictions': values}
        for quorum in (2, 3):
            for threshold in (.5, .67, .8, 1.0):
                key = f'family_minlen{minimum_length}_quorum{quorum}_share{threshold}'
                values = {}
                for k, e in exams.items():
                    filtered = [(f, v, t if len(t) >= minimum_length else '') for f, v, t in e]
                    values[k] = oe.family_consensus(filtered, quorum, threshold)['value']
                policies[key] = {'scores': score(values, truth), 'predictions': values}
    signatures = {tuple(v[k] for k in sorted(ids)) for v in grid.values()}
    oracle = sum(any(v[k] == truth[k]['reading'] for v in grid.values()) for k in ids)
    return {'sha256': digest(raw), 'n_images': len(ids), 'examinations_per_image': len(grid),
            'distinct_prediction_vectors': len(signatures), 'candidate_oracle_exact': oracle,
            'oracle_scope': 'Only this fixed candidate matrix, not a bound on future algorithms.',
            'policy_selection_warning': 'All curves exploratory; do not choose a production threshold on this test set.',
            'policies': policies}


def infer_peers():
    """Run reviewed, pinned peer source in memory; never switch their branch.

    These are repository Python modules, not remote network downloads. No fixture
    answers enter their inference. multi_algo monkeypatches only its own fr module.
    """
    sources, predictions = {}, {}
    previous = {n: sys.modules.get(n) for n in ('forensic_reader', 'multi_algo')}
    try:
        for module_name in ('forensic_reader', 'multi_algo'):
            file = f'lab/{module_name}.py'
            raw = subprocess.check_output(['git', 'show', f'{FIXTURE_REF}:{file}'], cwd=paths.REPO)
            sources[file] = digest(raw)
            module = types.ModuleType(module_name)
            module.__file__ = f'git:{FIXTURE_REF}:{file}'
            sys.modules[module_name] = module
            exec(compile(raw, module.__file__, 'exec'), module.__dict__)
            values = {}
            for name, im, _ in fixture_images():
                t0 = time.perf_counter()
                if module_name == 'forensic_reader':
                    result = module.read_line(im)
                    raw_text = result['text']
                    values[name] = {'value': str(int(raw_text)) if raw_text else '',
                                    'status': result['status']}
                else:
                    examinations = module.examinations(im)
                    text, agree, valid = module.vote(examinations)
                    values[name] = {'value': module.value(text), 'agree': agree,
                                    'valid': valid, 'n_examinations': len(examinations)}
                values[name]['ms_single_run'] = 1000 * (time.perf_counter() - t0)
                print(f'peer {module_name} {name}: {values[name]}', flush=True)
            predictions[module_name] = values
    finally:
        for name, original in previous.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original
    return {'commit': FIXTURE_REF, 'source_sha256': sources, 'predictions': predictions}


def synthetic_identity():
    import zxingcpp as zx
    rows = []
    registry = {'000123456789': 'synthetic-a', 'TEST-000042': 'synthetic-b', '009876543210': 'synthetic-c'}
    for fmt in (zx.BarcodeFormat.Code128, zx.BarcodeFormat.QRCode):
        for serial in registry:
            gray = np.asarray(zx.write_barcode(fmt, serial, width=400, height=180, quiet_zone=12))
            probes = {'original': gray, 'rot90': np.ascontiguousarray(np.rot90(gray)),
                      'dim': (gray * .6 + 30).astype(np.uint8),
                      'blur': cv2.GaussianBlur(gray, (3, 3), .7)}
            for variation, p in probes.items():
                r = si.read_identity(cv2.cvtColor(p, cv2.COLOR_GRAY2BGR), registry)
                rows.append({'format': str(fmt), 'synthetic_serial': serial, 'variation': variation,
                             'result': r, 'ok': r['serial'] == serial})
    # Negative controls: line crops have NO serial barcode, never invent one.
    negatives = {k: si.read_identity(im, registry)['status'] for k, im, _ in fixture_images()}
    return {'dataset': 'Generated symbols, NOT field meter photographs; same-library round trip.',
            'n': len(rows), 'exact': sum(r['ok'] for r in rows), 'rows': rows,
            'real_lcd_negative_controls': negatives}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=paths.RESULTS_ENGINES / 'optical_evidence_2026-10-18.json')
    parser.add_argument('--repeats', type=int, default=5)
    parser.add_argument('--barcode', action='store_true')
    parser.add_argument('--peers', action='store_true', help='run pinned peer readers; slower')
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error('--repeats must be positive')
    cv2.setNumThreads(1)
    rows, probes = infer_fixtures(args.repeats)
    peers = infer_peers() if args.peers else {'status': 'not_requested'}
    # Ground truth is read ONLY after every pixel prediction has finished.
    all_truth = list(csv.DictReader(paths.GROUND_TRUTH.open()))
    truth = {r['filename'][:5]: r for r in all_truth if r['reading'].isdigit()}
    for r in rows:
        ref = truth[r['id']]
        r.update(reference=ref['reading'], uncertain_reference=ref['uncertain'] == '1')
    summary = {}
    for name, values in [('optical_top1', {r['id']: r['evidence']['top1'] for r in rows}),
                         ('optical_conditional', {r['id']: r['evidence']['value'] for r in rows})]:
        summary[name] = score(values, truth)
        confirmed = {k: v for k, v in values.items() if truth[k]['uncertain'] != '1'}
        summary[name + '_confirmed_reference_only'] = score(confirmed, truth)
    for name in ('sevenseg', 'sevenseg2', 'sevenseg6'):
        summary[name] = score({r['id']: r['baseline_values'][name] for r in rows}, truth)
    for name, predictions in peers.get('predictions', {}).items():
        summary['peer_' + name + '_top1'] = score({k: v['value'] for k, v in predictions.items()}, truth)
        if name == 'forensic_reader':
            gated = {k: v['value'] if v['status'] == 'OK' else '' for k, v in predictions.items()}
            summary['peer_forensic_reader_OK_only'] = score(gated, truth)
        else:
            for threshold in (.2, .3, .4, .5):
                gated = {k: v['value'] if v['valid'] and v['agree'] / v['valid'] >= threshold else ''
                         for k, v in predictions.items()}
                summary[f'peer_multi_algo_gate{threshold}'] = score(gated, truth)
    times = [t for r in rows for t in r['warmed_ms']]
    probe_summary = {v: score({r['id']: r['value'] for r in probes if r['variation'] == v}, truth)
                     for v in nuisance_probes(np.full((96, 400, 3), 127, np.uint8))}
    packages = {'numpy': np.__version__, 'opencv': cv2.__version__}
    if args.barcode:
        packages['zxing-cpp'] = importlib.metadata.version('zxing-cpp')
    report = {
        'command': ' '.join(sys.argv),
        'environment': {'platform': platform.platform(), 'python': platform.python_version(),
                        'logical_cpus': os.cpu_count(), 'opencv_threads': cv2.getNumThreads(),
                        'openblas_threads_env': os.environ.get('OPENBLAS_NUM_THREADS'), 'packages': packages},
        'inference_sources_sha256': {p: digest((paths.LAB / p).read_bytes())
                                    for p in ['optical_evidence.py', 'serial_identity.py', 'sevenseg.py', 'sevenseg2.py', 'sevenseg6.py']},
        'fixture_commit': FIXTURE_REF,
        'protocol': {'training': False, 'pixel_inputs': 5, 'original_49_photos_available': False,
                     'mode': 'manually cropped/resized line fixtures, exploratory, not end-to-end',
                     'fixed_expected_cells': 6, 'format_note': 'Six-cell hypothesis is unsupported for CRYSTAL; no per-ID overrides.',
                     'independent_holdout': False, 'mobile_measurement': False,
                     'nuisance_probes_are_independent_samples': False,
                     'confidence_is_calibrated': False, 'production_autofill_approved': False,
                     'metric_note': 'wrong_accepted means nonempty wrong output of the named policy; top1 is diagnostic, not a confidence gate.'},
        'config': asdict(oe.DEFAULT), 'fixture_summary': summary, 'fixture_rows': rows,
        'warmed_timing_ms': dict(zip(('p50', 'p95', 'max'), [float(np.median(times)), float(np.percentile(times, 95)), max(times)])),
        'nuisance_probe_summary': probe_summary, 'nuisance_probe_rows': probes,
        'cached_audit': cached_audit(truth), 'peer_baselines': peers,
        'segment_code_min_hamming_distance': oe.code_distance(),
        'zero_error_upper95_n46': oe.zero_error_upper_bound(46),
        'zero_error_required_n_for_upper95_below_one_percent': 299,
        'identity_experiment': synthetic_identity() if args.barcode else {'status': 'not_requested'},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + '\n')
    print(json.dumps({'fixture_summary': summary, 'warmed_timing_ms': report['warmed_timing_ms'],
                      'nuisance_probe_summary': probe_summary,
                      'identity_exact': report['identity_experiment'].get('exact'),
                      'output': str(args.out)}, indent=2))


if __name__ == '__main__':
    main()
