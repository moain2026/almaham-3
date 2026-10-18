"""Profile-based deterministic LCD reader, registration and segment-level fusion.

No training, no reference readings, no per-image IDs. Profiles contain geometry
and private reference pixels ONLY for static-background alignment. Reference digit
pixels are masked out during registration and NEVER used as reading evidence.
All outputs are research-only; conditional agreement is not a calibrated probability.
"""
from dataclasses import dataclass
import hashlib

import cv2
import numpy as np

import optical_evidence as oe
import sevenseg as v1
import sevenseg2 as v2


@dataclass(frozen=True)
class Settings:
    jitter: float = .35
    ambiguity_fraction: float = .12
    min_contrast: float = .06
    max_bad_segment_fraction: float = .12
    min_static_pixels: int = 100
    min_ecc: float = .75
    max_alignment_translation: float = .12
    max_alignment_degrees: float = 8.
    max_static_residual: float = 18.
    glare_min_residual: float = 18.
    glare_noise_multiplier: float = 5.
    min_background_samples: int = 40
    max_frames: int = 8
    max_pixels: int = 12_000_000


DEFAULT = Settings()


@dataclass
class Profile:
    cells: tuple
    template: np.ndarray
    shear: float = 0.
    verified: bool = False
    name: str = 'unverified'

    def validate(self):
        validate_image(self.template)
        h, w = self.template.shape[:2]
        if not 1 <= len(self.cells) <= 10 or not np.isfinite(self.shear) or abs(self.shear) > .5:
            raise ValueError('invalid profile count or shear')
        right = -1.
        for c in self.cells:
            if len(c) != 4 or not np.isfinite(c).all():
                raise ValueError('invalid cell')
            x0, y0, x1, y1 = c
            if not (0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h and x1 - x0 >= 3 and y1 - y0 >= 8):
                raise ValueError('cell outside canonical image or too small')
            if x0 < right:
                raise ValueError('cells must be ordered and nonoverlapping')
            right = x1

    def metadata(self):
        return {'version': 1, 'cells': [list(c) for c in self.cells], 'shear': self.shear,
                'verified': self.verified, 'name': self.name,
                'size': [self.template.shape[1], self.template.shape[0]],
                'template_sha256': image_hash(self.template),
                'contains_reading_label': False}


def validate_image(image, cfg=DEFAULT):
    if (not isinstance(image, np.ndarray) or image.dtype != np.uint8 or image.ndim != 3
            or image.shape[2] != 3 or min(image.shape[:2]) < 8
            or image.shape[0] * image.shape[1] > cfg.max_pixels):
        raise ValueError('expected uint8 BGR image, 8x8 minimum, 12 MP maximum')


def image_hash(image):
    return hashlib.sha256(str(image.shape).encode() + image.tobytes()).hexdigest()


def rectify_quad(image, corners, size):
    """Explicit TL,TR,BR,BL screen corners; no learned detector or guessed labels."""
    validate_image(image)
    points = np.asarray(corners, np.float32)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        raise ValueError('four finite screen corners required')
    h, w = image.shape[:2]
    if (points < 0).any() or (points[:, 0] >= w).any() or (points[:, 1] >= h).any():
        raise ValueError('corners outside image')
    if not cv2.isContourConvex(points) or abs(cv2.contourArea(points)) < 64:
        raise ValueError('quadrilateral must be convex and nondegenerate')
    ow, oh = size
    if not (8 <= ow <= 2048 and 8 <= oh <= 2048):
        raise ValueError('unsupported output size')
    target = np.float32([[0, 0], [ow - 1, 0], [ow - 1, oh - 1], [0, oh - 1]])
    matrix = cv2.getPerspectiveTransform(points, target)
    return cv2.warpPerspective(image, matrix, (ow, oh))


def enroll(image, expected_cells, verified=False, name='unverified'):
    """Propose geometry only. Human-confirmed layout required before acceptance.

    Enrollment on a test photo is geometry calibration, NOT an independent test.
    Never save profiles containing customer pixels to the public repository.
    """
    validate_image(image)
    aligned, geom = oe.propose_geometry(image)
    if geom is None or len(geom['cells']) != expected_cells:
        raise ValueError('cannot propose requested layout; supply explicit cells')
    p = Profile(tuple(tuple(c) for c in geom['cells']), aligned, geom['shear'], verified, name)
    p.validate()
    return p


def static_mask(profile):
    mask = np.ones(profile.template.shape[:2], np.uint8) * 255
    for x0, y0, x1, y1 in profile.cells:
        pad = max(3, int((y1 - y0) * .12))
        mask[max(0, int(y0) - pad):int(y1) + pad, max(0, int(x0) - pad):int(x1) + pad] = 0
    return mask


def canonicalize(image, profile):
    validate_image(image)
    h, w = profile.template.shape[:2]
    ih, iw = image.shape[:2]
    if abs(iw / ih / (w / h) - 1) > .08:
        raise ValueError('aspect ratio changed; rectify the screen first')
    # Same interpolation as enrollment; do not introduce a registration mismatch.
    resized = cv2.resize(image, (w, h), interpolation=cv2.INTER_LINEAR)
    return cv2.merge([v1.shear(c, profile.shear) for c in cv2.split(resized)])


def align_frame(image, profile, register=True, cfg=DEFAULT):
    moving = canonicalize(image, profile)
    h, w = moving.shape[:2]
    info = {'ok': True, 'method': 'caller_aligned', 'correlation': None}
    # Deskew creates uncovered border pixels; they are missing evidence, not OFF.
    valid = v1.shear(np.ones((h, w), np.uint8), profile.shear)
    if not register:
        return moving, valid, info
    if np.array_equal(moving, profile.template):
        return moving, valid, {'ok': True, 'method': 'identical_pixels', 'correlation': 1.}
    mask = static_mask(profile)
    if np.count_nonzero(mask) < cfg.min_static_pixels:
        return moving, valid, {'ok': False, 'reason': 'insufficient_static_background'}
    ref = cv2.cvtColor(profile.template, cv2.COLOR_BGR2GRAY).astype(np.float32)
    cur = cv2.cvtColor(moving, cv2.COLOR_BGR2GRAY).astype(np.float32)
    if float(np.std(ref[mask > 0])) < 3:
        return moving, valid, {'ok': False, 'reason': 'textureless_registration'}
    try:
        correlation, matrix = cv2.findTransformECC(
            ref / 255, cur / 255, np.eye(2, 3, dtype=np.float32), cv2.MOTION_EUCLIDEAN,
            (cv2.TERM_CRITERIA_COUNT | cv2.TERM_CRITERIA_EPS, 60, 1e-5), mask, 3)
    except cv2.error:
        return moving, valid, {'ok': False, 'reason': 'registration_failed'}
    angle = abs(float(np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0]))))
    if (not np.isfinite(matrix).all() or correlation < cfg.min_ecc
            or angle > cfg.max_alignment_degrees
            or abs(matrix[0, 2]) > cfg.max_alignment_translation * w
            or abs(matrix[1, 2]) > cfg.max_alignment_translation * h):
        return moving, valid, {'ok': False, 'reason': 'registration_out_of_bounds'}
    aligned = cv2.warpAffine(moving, matrix, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP)
    valid = cv2.warpAffine(valid, matrix, (w, h), flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP)
    a = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)[mask > 0].astype(float)
    b = ref[mask > 0].astype(float)
    design = np.stack([a, np.ones_like(a)], 1)
    fit = np.linalg.lstsq(design, b, rcond=None)[0]
    error = float(np.median(np.abs(design @ fit - b)))
    return aligned, valid, {'ok': error <= cfg.max_static_residual, 'method': 'static_background_ecc',
                            'correlation': float(correlation), 'residual': error,
                            'matrix': matrix.tolist(), 'reason': 'ok' if error <= cfg.max_static_residual else 'static_mismatch'}


def visibility(image, profile, valid, cfg=DEFAULT):
    """Robust smooth background fit from the holes, independent of reference digits.

    Bright departures / clipping are missing evidence, NEVER assumed OFF. This
    does not detect every possible reflection; counters/examples must be retained.
    """
    h, w = image.shape[:2]
    yy, xx = np.mgrid[:h, :w].astype(float)
    xn, yn = xx / w, yy / h
    design = np.stack([np.ones_like(xn), xn, yn, xn * xn, xn * yn, yn * yn], 2)
    holes = np.zeros((h, w), bool)
    for x0, y0, x1, y1 in profile.cells:
        for a, b, c, d in oe.DEFAULT.background_windows:
            holes |= ((xx >= x0 + a * (x1 - x0)) & (xx < x0 + c * (x1 - x0))
                      & (yy >= y0 + b * (y1 - y0)) & (yy < y0 + d * (y1 - y0)))
    samples = holes & (valid > 0)
    if samples.sum() < cfg.min_background_samples:
        return np.ones((h, w), bool), {'reason': 'insufficient_background'}
    gray = image.max(2).astype(float)
    a, values = design[samples], gray[samples]
    coef = np.linalg.lstsq(a, values, rcond=None)[0]
    for _ in range(5):
        residual = values - a @ coef
        scale = max(2., float(np.median(np.abs(residual - np.median(residual)))) * 1.4826)
        weights = np.minimum(1., 1.5 * scale / np.maximum(np.abs(residual), 1e-6))
        coef = np.linalg.lstsq(a * np.sqrt(weights[:, None]), values * np.sqrt(weights), rcond=None)[0]
    threshold = max(cfg.glare_min_residual, cfg.glare_noise_multiplier * scale)
    bad = ((gray - design @ coef) > threshold) | (image.min(2) >= 250) | (valid == 0)
    bad = cv2.dilate(bad.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    return bad, {'bad_fraction': float(bad.mean()), 'background_noise': scale, 'bright_residual_threshold': threshold}


def _sample_bad(mask, cell):
    p = oe._patch(np.repeat(mask[..., None].astype(np.uint8), 3, axis=2), cell, 0, 0, oe.DEFAULT)[..., 0]
    h, w = p.shape
    return [float(p[int(b*h):max(int(b*h)+1, int(d*h)), int(a*w):max(int(a*w)+1, int(c*w))].mean())
            for a, b, c, d in (v1.WIN[s] for s in v1.SEG_ORDER)]


def observe(image, profile, register=True, cfg=DEFAULT):
    profile.validate()
    aligned, valid, alignment = align_frame(image, profile, register, cfg)
    empty = {'value': '', 'top1': '', 'states': [[-1]*7 for _ in profile.cells],
             'status': 'registration_rejected', 'alignment': alignment, 'usable': False,
             'calibrated_probability': None}
    if not alignment['ok']:
        return empty
    bad, quality = visibility(aligned, profile, valid, cfg)
    j = cfg.jitter
    scores = np.array([[oe.measure_segments(oe.local_contrast(oe._patch(aligned, c, dx, dy, oe.DEFAULT)))
                        for c in profile.cells] for dx, dy in ((0, 0), (j, 0), (-j, 0), (0, j), (0, -j))])
    central = scores[0]
    _, spread, low, high = v2.two_cluster_threshold(central.ravel())
    bad_fractions = np.array([_sample_bad(bad, cell) for cell in profile.cells])
    if spread < cfg.min_contrast:
        empty.update(status='low_contrast', quality=quality, bad_fractions=bad_fractions.tolist())
        return empty
    threshold, guard = (low + high) / 2, cfg.ambiguity_fraction * spread
    states = np.where(scores.min(0) > threshold + guard, 1,
                      np.where(scores.max(0) < threshold - guard, 0, -1))
    states[bad_fractions > cfg.max_bad_segment_fraction] = -1
    options = [oe.decode_erasure(s) for s in states.tolist()]
    text = ''.join(v2.classify(dict(zip(v1.SEG_ORDER, s)), threshold, spread)[0] for s in central)
    result = {'value': '', 'top1': str(int(text)), 'raw_top1': text, 'states': states.tolist(),
              'candidates': options, 'quality': quality, 'alignment': alignment, 'usable': True,
              'bad_fractions': bad_fractions.round(3).tolist(), 'scores': central.round(4).tolist(),
              'status': 'ambiguous', 'calibrated_probability': None}
    if not profile.verified:
        result['status'] = 'unverified_profile'
    elif all(len(o) == 1 for o in options):
        result.update(value=str(int(''.join(o[0] for o in options))), status='conditional_singleton')
    elif any(not o for o in options):
        result['status'] = 'inconsistent_segments'
    return result


def fuse_observations(observations, verified=True):
    useful = [o for o in observations if o['usable']]
    out = {'value': '', 'status': 'no_usable_frames', 'calibrated_probability': None}
    if not useful:
        return out
    states = np.array([o['states'] for o in useful])
    on, off = (states == 1).any(0), (states == 0).any(0)
    conflict = on & off
    fused = np.where(on & ~off, 1, np.where(off & ~on, 0, -1))
    options = [oe.decode_erasure(s) for s in fused.tolist()]
    out.update(states=fused.tolist(), candidates=options, conflicts=conflict.tolist(),
               visible_observations=(states != -1).sum(0).tolist(), status='ambiguous')
    full_values = {o['value'] for o in useful if o['value']}
    if len(full_values) > 1:
        out['status'] = 'reading_changed'
    elif conflict.any():
        out['status'] = 'conflicting_segment_evidence'
    elif any(not o for o in options):
        out['status'] = 'inconsistent_segments'
    elif not verified:
        out['status'] = 'unverified_profile'
    elif all(len(o) == 1 for o in options):
        out.update(value=str(int(''.join(o[0] for o in options))), status='conditional_singleton')
    return out


def read_frames(frames, profile, register=True, cfg=DEFAULT):
    if not frames or len(frames) > cfg.max_frames:
        raise ValueError('provide between one and eight frames')
    profile.validate()
    seen, observations = set(), []
    for frame in frames:
        validate_image(frame, cfg)
        fingerprint = image_hash(frame)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        observation = observe(frame, profile, register, cfg)
        observation['input_sha256'] = fingerprint
        observations.append(observation)
    result = fuse_observations(observations, profile.verified)
    result.update(observations=observations, unique_frames=len(observations),
                  duplicate_frames_ignored=len(frames)-len(observations),
                  production_approved=False, profile_name=profile.name)
    return result
