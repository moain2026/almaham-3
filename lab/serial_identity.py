"""No-training identity reader; barcode payloads are NOT consumption readings.

Optional dependency: zxing-cpp==2.3.0 (Apache-2.0 reader). A decoder verifies the
symbol, not ownership, field semantics or authenticity. Auto-fill requires an
exact, unique registry match; leading zeros are preserved. No fuzzy correction.
"""
import re

import cv2
import numpy as np


SERIAL = re.compile(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,63}\Z')


def resolve_identity(payloads, registry):
    """Registry maps literal barcode payloads to authoritative meter IDs.

    Multiple different payloads in the crop are ambiguous even if only one is in
    the registry: selecting a neighbour's meter would be worse than abstaining.
    A newly installed/unknown meter needs explicit onboarding, not auto-creation.
    """
    texts = sorted(set(payloads))
    out = {'serial': '', 'meter_id': None, 'status': 'no_barcode', 'payloads': texts}
    if not texts:
        return out
    if len(texts) > 1:
        out['status'] = 'multiple_barcodes'
    elif not SERIAL.fullmatch(texts[0]):
        out['status'] = 'unsupported_payload'
    elif texts[0] not in registry:
        out['status'] = 'unregistered_serial'
    else:
        out.update(serial=texts[0], meter_id=registry[texts[0]], status='registry_match')
    return out


def read_identity(bgr, registry):
    """Read valid symbols with checksum/ECC checking delegated to ZXing-C++."""
    if (not isinstance(bgr, np.ndarray) or bgr.dtype != np.uint8
            or bgr.ndim != 3 or bgr.shape[2] != 3 or min(bgr.shape[:2]) < 8):
        raise ValueError('expected uint8 BGR image at least 8x8')
    try:
        import zxingcpp
    except ImportError as exc:
        raise RuntimeError('optional barcode experiment needs zxing-cpp==2.3.0') from exc
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    # v2.3 has no try_invert keyword; explicit inversion is deterministic.
    decoded = [b for image in (gray, 255 - gray)
               for b in zxingcpp.read_barcodes(image, try_rotate=True, try_downscale=True)]
    return resolve_identity([b.text for b in decoded if b.valid], registry)
