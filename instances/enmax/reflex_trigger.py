"""
ENMAX instance — reflex trigger.

HAS_REFLEX = True. The P1 flag fires Touch regardless of cognitive budget.

P1 incidents (life-safety): gas leak, transformer fire, person trapped in
electrical hazard, structural collapse near energized equipment. These require
immediate dispatcher attention — no queueing, no budget check.

DECLARED: p1_active is a synthetic flag set by data_loader.py. In a real
ENMAX CAD system this would come from:
  - Automatic incident classification (gas leak keyword in caller transcript)
  - Field crew P1 escalation via radio
  - Integration with Calgary 911 dispatch (shared incidents)

Unlike cycling's crash_signal (single boolean, discrete event), p1_active
can remain True for the duration of the incident (minutes to hours). Touch
fires at every sample where p1_active is True — the dispatcher must stay
aware of the P1 throughout, not just at the moment it opens.
"""

import numpy as np

HAS_REFLEX = True


def reflex_series(samples: list) -> np.ndarray:
    """
    Return a boolean array: True at every sample where a P1 incident is active.
    DECLARED: driven by the synthetic p1_active field from data_loader.py.
    """
    return np.array([s["p1_active"] for s in samples], dtype=bool)
