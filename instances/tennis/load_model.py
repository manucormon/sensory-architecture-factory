"""
Tennis instance — declared load model.

DECLARED, not REAL or PROXY: there is no sensor behind this. Load
rises during a point (illustrative ramp, not measured) and drops
sharply the instant the point ends — the whole premise being tested
is that this domain HAS a real, ruled recovery window (unlike F1's
straight, which is track geometry, not a rule).
"""

import numpy as np


def compute_load(samples):
    load = np.array([
        0.15 + 0.80 * s["point_progress"] if s["in_point"] else 0.05
        for s in samples
    ])
    load = np.clip(load, 0, 1)
    attention = 1 - load
    return load, attention
