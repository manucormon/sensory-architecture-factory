"""
Cycling instance — reflex trigger.

HAS_REFLEX = True. The trigger fires on crash_signal — a sudden incident
ahead (peloton crash, obstacle, wheel touch) that requires immediate haptic
warning regardless of cognitive budget.

DECLARED: crash_signal is a synthetic flag in data_loader.py. In a real
system this would come from vision-based incident detection, team radio
crash alerts, or accelerometer data from the rider's bike.

Unlike F1's reflex (braking + proximity, both PROXY from telemetry), this
trigger is a single boolean — simpler because the event type is discrete
(crash or not) rather than a continuous proximity gradient.
"""

import numpy as np

HAS_REFLEX = True


def reflex_series(samples: list) -> np.ndarray:
    """
    Return a boolean array: True at samples where a crash signal is active.
    DECLARED: driven by the synthetic crash_signal field from data_loader.py.
    """
    return np.array([s["crash_signal"] for s in samples], dtype=bool)
