"""
Cycling instance — two-timescale cognitive load model.

This is the genuinely new contribution of this instance: load stacks two
timescales, unlike F1 (single fast signal) and tennis (single declared signal).

TIMESCALE 1 — instantaneous load (fast, moment-to-moment):
  PROXY: power_w / ftp_w (intensity factor) stands in for cognitive demand.
  Rationale: high power output correlates with reduced cognitive bandwidth —
  the same proxy logic as F1's telemetry-for-biometrics, but for cycling.
  A rider at 110% FTP is in oxygen debt and has less bandwidth for tactical
  decisions; at 40% FTP on a descent, bandwidth is nearly fully available.

TIMESCALE 2 — accumulated fatigue (slow, stage-long):
  DECLARED: a running TSS-inspired index — time spent above threshold,
  weighted by intensity squared. No real lactate or biometric measurement
  behind this; it's a design convention informed by training science.
  Normalized to the expected fatigue at the end of a 1-hour stage at FTP.
  At hour 5 of a real stage, this component alone would be near 1.0 —
  which is why multi-hour races change the meaning of the same power output.

COMBINED load — noisy-OR:
  load = 1 - (1 - w_inst * instant) * (1 - w_fat * fatigue)
  Either extreme instant demand OR high accumulated fatigue can push load
  to its peak. A rider at 70% FTP late in a stage can have the same total
  load as a rider at 100% FTP fresh — two different paths to the same
  cognitive state.

Returns instant_load, fatigue, load, attention as numpy arrays.
"""

import numpy as np
from core.governance import norm


# Weighting between the two timescales — DECLARED design choice.
# A small change here has large effects on when Voice opens; see NOTES.md.
_W_INSTANT = 0.70   # instantaneous demand dominates in the short term
_W_FATIGUE = 0.55   # fatigue can push load significantly even at low instant demand

# TSS normalization constant: expected fatigue index after 1 hour at FTP.
# At exactly FTP (IF=1.0) for 3600s: TSS = 100 (by definition in training science).
# We normalize so that 1 hour at FTP = fatigue ~0.85 (not 1.0, to leave headroom).
_TSS_NORM = 3600 * 1.0 ** 2 / 0.85


def compute_load(samples: list) -> tuple:
    """
    Returns (instant_load, fatigue, load, attention) as numpy arrays.
    All four are 0..1, length == len(samples).
    """
    power = np.array([s["power_w"] for s in samples], dtype=float)
    ftp = np.array([s["ftp_w"] for s in samples], dtype=float)

    # --- Timescale 1: instantaneous ---
    # PROXY: intensity factor (IF = power / FTP) as cognitive demand proxy.
    # Clipped at 1.2 (120% FTP is near-maximal effort, full cognitive load).
    intensity_factor = np.clip(power / ftp, 0, 1.2) / 1.2
    # Smooth over a 5-second window to avoid sample-to-sample noise.
    instant_load = np.convolve(intensity_factor, np.ones(5) / 5, mode="same")
    instant_load = np.clip(instant_load, 0, 1)

    # --- Timescale 2: accumulated fatigue ---
    # DECLARED: TSS-inspired running sum, normalized to 1-hour-at-FTP = 0.85.
    # Each second contributes (power/ftp)^2 to the running total.
    tss_per_sample = (power / ftp) ** 2
    tss_cumulative = np.cumsum(tss_per_sample)
    fatigue = np.clip(tss_cumulative / _TSS_NORM, 0, 1)

    # --- Combined: noisy-OR across both timescales ---
    load = 1 - (1 - _W_INSTANT * instant_load) * (1 - _W_FATIGUE * fatigue)
    load = np.clip(load, 0, 1)
    attention = 1 - load

    return instant_load, fatigue, load, attention
