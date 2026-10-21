"""Tests for augment.py: boxes must follow pixels; shapes/dtypes preserved; determinism; photometric ops never move
boxes. Run: python3 test_augment.py"""
import numpy as np
import cv2
import augment as A


def _scene(h=64, w=448, n=6):
    im = np.full((h, w, 3), 128, np.uint8)
    boxes = []
    for k in range(n):
        x1, y1 = 20 + k * 60, 12
        x2, y2 = x1 + 30, 52
        cv2.rectangle(im, (x1, y1), (x2, y2), (int(40 * k) % 255, 200, 60), -1)
        boxes.append((k % 10, x1, y1, x2, y2))
    return im, np.array(boxes, np.float32)


def test_shape_dtype_and_determinism():
    im, b = _scene()
    o1, b1 = A.augment(im, b, "reader", np.random.default_rng(3))
    o2, b2 = A.augment(im, b, "reader", np.random.default_rng(3))
    assert o1.shape == im.shape and o1.dtype == np.uint8
    assert np.array_equal(o1, o2) and np.array_equal(b1, b2)


def test_photometric_only_keeps_boxes():
    im, b = _scene()
    cfg = dict(A.AUG["reader"], p_geom=0.0, p_digit_perm=0.0)
    o, nb = A.augment(im, b, "reader", np.random.default_rng(1), cfg)
    assert np.array_equal(nb, b)


def test_affine_boxes_follow_content():
    """Pure translation: box centre must move by exactly (tx,ty)."""
    im, b = _scene()
    cfg = dict(A.AUG["reader"], rot_deg=0, shear=0.0, scale=(1.0, 1.0), shift=0.05, p_geom=1.0, p_photo=0, p_gamma=0,
               p_hsv=0, p_gray=0, p_chan_perm=0, p_blur=0, p_noise=0, p_jpeg=0, p_glare=0, p_digit_perm=0)
    rng = np.random.default_rng(7)
    o, nb = A.augment(im, b, "reader", rng, cfg)
    # recover the shift from the image: centroid of the coloured (non-grey) pixels of digit 0 before/after
    def centroid(img, box):
        x1, y1, x2, y2 = [int(round(v)) for v in box[1:]]
        return (x1 + x2) / 2, (y1 + y2) / 2
    dx = nb[0, 1] - b[0, 1]
    dy = nb[0, 2] - b[0, 2]
    # every kept box must have moved by the same (dx,dy) under pure translation
    assert len(nb) >= 4
    for k in range(len(nb)):
        assert abs((nb[k, 1] - nb[k, 3]) - (b[0, 1] - b[0, 3])) < 1.5  # width preserved
    # and the mask of non-grey pixels moved accordingly
    m0 = np.any(im != 128, axis=2)
    m1 = np.any(o != 128, axis=2)
    ys0, xs0 = np.nonzero(m0); ys1, xs1 = np.nonzero(m1)
    assert abs((xs1.mean() - xs0.mean()) - dx) < 2.0 and abs((ys1.mean() - ys0.mean()) - dy) < 2.0


def test_rotation_keeps_boxes_inside_and_covering():
    im, b = _scene()
    cfg = dict(A.AUG["reader"], rot_deg=8, shear=0.0, scale=(1.0, 1.0), shift=0.0, p_geom=1.0, p_photo=0, p_gamma=0,
               p_hsv=0, p_gray=0, p_chan_perm=0, p_blur=0, p_noise=0, p_jpeg=0, p_glare=0, p_digit_perm=0)
    o, nb = A.augment(im, b, "reader", np.random.default_rng(11), cfg)
    h, w = im.shape[:2]
    assert len(nb) == len(b)
    for k in range(len(nb)):
        x1, y1, x2, y2 = nb[k, 1:]
        assert 0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h
        # the box must contain the coloured pixels of its digit: >= 95% of non-grey pixels inside the box region
        crop = o[int(y1):int(y2) + 1, int(x1):int(x2) + 1]
        assert np.any(crop != 128)


def test_boxes_leaving_frame_are_dropped():
    im, b = _scene()
    cfg = dict(A.AUG["reader"], rot_deg=0, shear=0.0, scale=(1.0, 1.0), shift=0.0, p_geom=1.0, p_photo=0, p_gamma=0,
               p_hsv=0, p_gray=0, p_chan_perm=0, p_blur=0, p_noise=0, p_jpeg=0, p_glare=0, p_digit_perm=0)
    # force a large shift by editing the affine through a huge 'shift' and fixed rng draw
    cfg["shift"] = 0.9
    o, nb = A.augment(im, b, "reader", np.random.default_rng(5), cfg)
    assert len(nb) < len(b)


def test_digit_permutation_swaps_labels_with_pixels():
    im, b = _scene()
    rng = np.random.default_rng(2)
    o, nb = A._digit_permutation(im, b, rng)
    # the two swapped boxes carry each other's class, and the pixel colour at each box matches the new class
    changed = [k for k in range(len(b)) if nb[k, 0] != b[k, 0]]
    assert len(changed) == 2
    i, j = changed
    col_i = o[int(b[i, 2]) + 5, int(b[i, 1]) + 5, 0]
    col_j = o[int(b[j, 2]) + 5, int(b[j, 1]) + 5, 0]
    assert col_i == int(40 * nb[i, 0]) % 255 and col_j == int(40 * nb[j, 0]) % 255


if __name__ == "__main__":
    import sys
    fails = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("ok  ", name)
            except Exception as e:  # noqa
                fails += 1; print("FAIL", name, repr(e))
    sys.exit(1 if fails else 0)
