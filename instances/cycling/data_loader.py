"""
Cycling instance — data loading.

DECLARED: all data is synthetic, generated to match realistic mountain-stage
power profiles. No real athlete sensor is behind this. The structure is
informed by published stage power data and training science literature, but
every number is invented for illustration — same labeling discipline as the
tennis instance.

Models a 3600-sample (1 hour at 1 Hz) segment of a mountain stage with
three phases, each repeated to fill the stage:
  climb    — sustained high power, high gradient
  descent  — low power, low cognitive demand, primary recovery window
  flat     — moderate power, peloton dynamics, tactical decisions

Each sample is a dict with:
  time_s         — elapsed seconds in the stage
  phase          — 'climb' | 'descent' | 'flat'
  power_w        — current power output (watts), DECLARED
  ftp_w          — functional threshold power (watts), DECLARED constant
  gradient_pct   — road gradient (%), DECLARED
  crash_signal   — bool, simulated crash-ahead event (DECLARED)
"""

import math

FTP_W = 280           # DECLARED: typical pro cyclist FTP
STAGE_DURATION_S = 3600

# Phase definitions: (name, duration_s, base_power_pct_ftp, gradient_pct)
# Power varies sinusoidally around the base to simulate effort variation.
PHASE_PROFILE = [
    ("climb",   900, 0.92, 7.5),
    ("descent", 300, 0.35, -5.0),
    ("flat",    600, 0.72, 1.0),
    ("climb",   900, 0.95, 8.5),
    ("descent", 300, 0.30, -6.0),
    ("flat",    600, 0.68, 0.5),
]
_TOTAL_CYCLE = sum(d for _, d, _, _ in PHASE_PROFILE)

# DECLARED: one simulated crash signal — a peloton incident at ~45 min
_CRASH_SAMPLES = set(range(2700, 2703))


def _phase_at(t: int) -> tuple:
    """Return (phase_name, power_pct_ftp, gradient_pct) for second t."""
    pos = t % _TOTAL_CYCLE
    cursor = 0
    for name, duration, pwr_pct, grad in PHASE_PROFILE:
        if pos < cursor + duration:
            progress = (pos - cursor) / duration
            variation = 0.05 * math.sin(2 * math.pi * progress * 3)
            return name, pwr_pct + variation, grad
        cursor += duration
    return PHASE_PROFILE[-1][0], PHASE_PROFILE[-1][2], PHASE_PROFILE[-1][3]


def load() -> list:
    """
    Return a list of sample dicts for a synthetic mountain-stage hour.
    All values are DECLARED — no real sensor behind this.
    """
    samples = []
    for t in range(STAGE_DURATION_S):
        phase, pwr_pct, grad = _phase_at(t)
        power_w = max(50, FTP_W * pwr_pct)
        samples.append({
            "time_s": t,
            "phase": phase,
            "power_w": round(power_w, 1),
            "ftp_w": FTP_W,
            "gradient_pct": grad,
            "crash_signal": t in _CRASH_SAMPLES,
        })
    return samples
