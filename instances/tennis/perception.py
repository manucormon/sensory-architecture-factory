"""
Tennis instance — perception layer.

Thin passthrough. The synthetic data generator in data_loader.py already
IS the perception for this hypothetical instance — it produces
point_progress and phase directly, which is all load_model.py and
reflex_trigger.py consume.

Consistent with NOTES.md's DECLARED framing: there is no real match, no
real ball, no real court to track. Inventing a tracking layer for data
that was declared rather than measured would be a confidence mismatch —
labeling TRACKED something that came from a random number generator.

This instance has no TRACKED or PREDICTED fields, and no MEASURED ones
either (there is no external system; the generator is the source). The
perceptual state is the sample dict produced by data_loader.py as-is.

If a future tennis instance uses real Hawkeye ball-tracking data, that
instance's perception.py would expose ball_x, ball_y, ball_z as
MEASURED (Hawkeye computes them) and could add a PREDICTED trajectory
if the load model needed it. That is not this instance.
"""

HAS_PERCEPTION = False  # no spatial extraction needed — passthrough


def perceive(samples: list) -> list:
    """
    Return samples unchanged. The DECLARED synthetic data already contains
    all fields load_model.py needs; no spatial extraction is performed.
    """
    return samples
