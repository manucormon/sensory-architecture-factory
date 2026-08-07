"""
ENMAX instance — two-timescale cognitive load model.

TIMESCALE 1 — instantaneous demand (fast, incident-driven):
  DECLARED: composite of active incident count, queue depth, P1 flag, and
  crew availability. P1 saturates the budget immediately — the dispatcher
  has no spare attention when a life-safety incident is open.

  if p1_active:
      instant_raw = 1.0          # saturated — P1 overrides everything
  else:
      instant_raw = clip(
          0.50 * norm_incidents  # dominant driver of moment-to-moment load
        + 0.35 * norm_queue      # waiting calls add pressure
        + 0.15 * crew_pressure   # low crew availability amplifies demand
      , 0, 1)

  MAX_INCIDENTS = 12 — DECLARED ceiling (above this, load saturates at 1.0)
  MAX_QUEUE     =  6 — DECLARED ceiling for queue depth

TIMESCALE 2 — accumulated shift fatigue (slow, 12h-scale):
  DECLARED: linear model normalized to a 12-hour shift.
  fatigue = shift_elapsed_h / 12.0

  Rationale: for the ENMAX dispatcher, time into the shift is the dominant
  fatigue signal. Unlike a cyclist (where fatigue depends on work performed),
  a dispatcher's fatigue is largely clock-driven — sustained vigilance for
  any shift length degrades attention regardless of quiet or busy periods.
  This is the "vigilance decrement" from sustained attention research.

  Monotonically increasing by design: fatigue never recovers within a shift.
  Post-shift recovery is outside the model scope.

  W_FATIGUE = 0.30: fatigue modulates load but incident pressure dominates.
  A quiet late-shift dispatcher (instant=0.10, fatigue=0.80) reaches
  load ≈ 0.33 — tired but functional. An incident spike overrides fatigue.

COMBINED: noisy-OR
  load = 1 - (1 - W_INST * instant) * (1 - W_FAT * fatigue)

Key design verifications:
  P1 active, h3 (fatigue=0.25):
    load = 1-(1-0.80)(1-0.30*0.25) = 0.815 → attention=0.185 [Voice blocked ✓]
  Storm, no P1, h3 (inst≈0.66, fatigue=0.25):
    load ≈ 0.56 → attention≈0.44 [Voice blocked ✓]
  Post-storm lull, h5 (inst≈0.11, fatigue=0.42):
    load ≈ 0.21 → attention≈0.79 [Voice opens ✓, budget remaining=0.29 > 0.20]

Returns instant_load, fatigue, load, attention as numpy arrays.
"""

import numpy as np

_MAX_INCIDENTS = 12
_MAX_QUEUE     =  6

_W_INSTANT = 0.80   # DECLARED: incident pressure dominates moment-to-moment
_W_FATIGUE = 0.30   # DECLARED: fatigue modulates but does not dominate alone


def compute_load(samples: list) -> tuple:
    """
    Returns (instant_load, fatigue, load, attention) as numpy arrays.
    All four are 0..1, length == len(samples).
    """
    n = len(samples)
    instant_raw = np.zeros(n)
    fatigue      = np.zeros(n)

    for i, s in enumerate(samples):
        # --- Timescale 2: accumulated fatigue (computed first — no dependencies) ---
        # DECLARED: linear vigilance decrement over the shift.
        fatigue[i] = min(s["shift_elapsed_h"] / 12.0, 1.0)

        # --- Timescale 1: instantaneous demand ---
        if s["p1_active"]:
            instant_raw[i] = 1.0   # P1 saturates — life-safety overrides everything
        else:
            norm_inc  = min(s["active_incidents"] / _MAX_INCIDENTS, 1.0)
            norm_q    = min(s["queue_depth"] / _MAX_QUEUE, 1.0)
            crew_pres = 1.0 - s["crew_available"]
            instant_raw[i] = np.clip(
                0.50 * norm_inc + 0.35 * norm_q + 0.15 * crew_pres, 0, 1
            )

    # Smooth instant load over 30s to remove sample-level noise
    instant_load = np.convolve(instant_raw, np.ones(30) / 30, mode="same")
    instant_load = np.clip(instant_load, 0, 1)

    # Combined: noisy-OR
    load = 1 - (1 - _W_INSTANT * instant_load) * (1 - _W_FATIGUE * fatigue)
    load = np.clip(load, 0, 1)
    attention = 1 - load

    return instant_load, fatigue, load, attention
