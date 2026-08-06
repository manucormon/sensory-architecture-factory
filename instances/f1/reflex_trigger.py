"""
F1 instance — reflex trigger.
Mechanical extraction of reflex_trigger() from the original
governance_engine.py. Same thresholds, same logic.
"""

import numpy as np


def reflex_trigger(i, decel, gap):
    """The one signal that must get through even at zero attention."""
    hard_brake = decel[i] > np.nanpercentile(decel[decel > 0], 80) if (decel > 0).any() else False
    wheel_to_wheel = gap[i] < 8
    return bool(hard_brake or wheel_to_wheel)


def reflex_series(decel, gap):
    return [reflex_trigger(i, decel, gap) for i in range(len(decel))]
