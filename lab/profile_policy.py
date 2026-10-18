"""Conservative output policy, separate from the frozen profile-reader algorithm.

A legal singleton inferred through UNKNOWN segments is only a diagnostic candidate.
Require complete observed coverage after fusion before emitting a conditional value.
This is NOT a guarantee: an incorrectly observed ON/OFF state can still be wrong.
Policy introduced after stress v1 failures; old-data evaluation must be post-hoc.
"""


def require_observed_segments(result):
    out = dict(result)
    states = result.get('states', [])
    valid_shape = bool(states) and all(isinstance(s, list) and len(s) == 7 for s in states)
    total = len(states) * 7 if valid_shape else 0
    observed = sum(s in (0, 1) for cell in states for s in cell) if valid_shape else 0
    out.update(candidate_value=result.get('value', ''), policy='all_segments_observed_v1',
               observed_segments=observed, total_segments=total, production_approved=False)
    if out.get('value') and (not valid_shape or observed != total):
        out.update(value='', status='incomplete_segment_coverage')
    return out
