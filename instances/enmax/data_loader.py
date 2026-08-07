"""
Cycling instance — data loading.

DECLARED: all data is synthetic, generated to match a realistic ENMAX
dispatcher shift profile. No real CAD (Computer-Aided Dispatch) system
behind this. The structure is informed by:
  - Public ENMAX incident response documentation
  - Calgary major outage patterns (storm season June-September)
  - Emergency dispatch cognitive load literature (Loveday et al., 2018)

Simulates one 12-hour shift (43200 samples at 1Hz) with:

  MORNING RAMP    (h0–h2):   rising incident volume as crews come online
  STORM EVENT     (h2–h5):   severe thunderstorm — multiple simultaneous outages,
                             includes two P1s (gas leak + transformer fire)
  POST-STORM LULL (h5–h7):   incident volume drops sharply as storm clears
  AFTERNOON PEAK  (h7–h10):  second volume peak (commute + industrial shift end)
  LATE-SHIFT WIND (h10–h12): declining volume, high accumulated fatigue

Each sample is a dict with:
  time_s            — elapsed seconds in shift
  active_incidents  — open tickets being managed (DECLARED integer)
  queue_depth       — calls waiting to be dispatched (DECLARED integer)
  p1_active         — bool: life-safety incident in progress (DECLARED)
  crew_available    — fraction of field crews available 0..1 (DECLARED)
  shift_elapsed_h   — hours into the 12h shift (DECLARED)
"""

import math
import random

SHIFT_DURATION_S = 43_200    # 12 hours
_RNG = random.Random(42)     # fixed seed for reproducibility


# Phase definitions: (name, start_h, end_h, base_incidents, base_queue, p1_prob)
_PHASES = [
    ("morning_ramp",    0,   2,  3,  1, 0.00),
    ("storm_event",     2,   5,  9,  4, 0.04),   # P1 probability during storm
    ("post_storm_lull", 5,   7,  2,  0, 0.00),
    ("afternoon_peak",  7,  10,  6,  2, 0.01),
    ("late_shift_wind", 10, 12,  3,  1, 0.00),
]

# Two hard-coded P1 windows (DECLARED: specific incidents the scenario features)
# Gas leak: hour 3.0–3.5 | Transformer fire: hour 4.2–4.6
_P1_WINDOWS = [
    (int(3.0 * 3600), int(3.5 * 3600)),
    (int(4.2 * 3600), int(4.6 * 3600)),
]


def _phase_at(t: int) -> tuple:
    h = t / 3600
    for name, h_start, h_end, base_inc, base_q, p1_prob in _PHASES:
        if h_start <= h < h_end:
            return name, base_inc, base_q, p1_prob
    return _PHASES[-1][0], _PHASES[-1][2], _PHASES[-1][3], _PHASES[-1][5]


def _is_p1(t: int) -> bool:
    for start, end in _P1_WINDOWS:
        if start <= t < end:
            return True
    return False


def load() -> list:
    """
    Return a list of sample dicts for a 12-hour ENMAX dispatcher shift.
    All values are DECLARED — no real CAD system behind this.
    """
    samples = []
    for t in range(SHIFT_DURATION_S):
        phase, base_inc, base_q, p1_prob = _phase_at(t)

        # Add realistic noise around the phase baseline
        noise_inc = _RNG.randint(-1, 2)
        noise_q   = _RNG.randint(-1, 1)
        active_incidents = max(0, base_inc + noise_inc)
        queue_depth      = max(0, base_q + noise_q)

        # P1 from hard-coded windows + rare stochastic P1
        p1_active = _is_p1(t) or (_RNG.random() < p1_prob)

        # Crew availability: high at start, drops during storm
        if phase == "storm_event":
            crew_available = max(0.2, 0.6 - 0.1 * (t / 3600 - 2))
        elif phase == "late_shift_wind":
            crew_available = 0.85
        else:
            crew_available = min(1.0, 0.80 + _RNG.uniform(-0.05, 0.10))

        samples.append({
            "time_s":           t,
            "phase":            phase,
            "active_incidents": active_incidents,
            "queue_depth":      queue_depth,
            "p1_active":        p1_active,
            "crew_available":   round(crew_available, 2),
            "shift_elapsed_h":  round(t / 3600, 3),
        })

    return samples
