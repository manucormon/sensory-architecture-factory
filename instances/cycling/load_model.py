"""
Cycling instance — two-timescale cognitive load model.

Now operating on REAL power-meter data. The two-timescale structure is unchanged
from the DECLARED prototype, but the labeling is updated throughout.

TIMESCALE 1 — instantaneous load (fast, moment-to-moment):
  PROXY: power_w / ftp_w (intensity factor) stands in for cognitive demand.
  power_w is REAL (power meter). ftp_w = 240W is PROXY (95% of best 20-min
  rolling power — industry standard estimate, not a lab test).
  The ratio itself remains a proxy: measured watts do not directly measure
  cognitive bandwidth — they stand in for it by established physiology.

TIMESCALE 2 — accumulated fatigue (slow, stage-long):
  PROXY: a running TSS-inspired index. The component values are REAL (power)
  and PROXY (FTP), so the derived index carries the same PROXY label.
  The shape of the model (cumsum of (power/FTP)^2) is informed by training
  science literature; it remains an approximation, not a lab measurement.

COMBINED load — noisy-OR (unchanged):
  load = 1 - (1 - w_inst * instant) * (1 - w_fat * fatigue)

Returns instant_load, fatigue, load, attention as numpy arrays.
"""

import numpy as np
import pandas as pd
from core.governance import norm


_W_INSTANT = 0.70
_W_FATIGUE = 0.55
_TSS_NORM = 3600 * 1.0 ** 2 / 0.85


def compute_load(df: pd.DataFrame, ftp_w: float) -> tuple:
    """
    Returns (instant_load, fatigue, load, attention) as numpy arrays.

    Args:
        df:    DataFrame from data_loader.load() (after perceive()).
        ftp_w: athlete FTP in watts (PROXY — see data_loader.FTP_W).
    """
    power = df["power_w"].to_numpy(dtype=float)

    # --- Timescale 1: instantaneous ---
    # PROXY: intensity factor (IF = power / FTP) as cognitive demand proxy.
    intensity_factor = np.clip(power / ftp_w, 0, 1.2) / 1.2
    # Causal rolling mean with min_periods=1: no edge artifacts, no jump in
    # behaviour between len=4 and len=5, len(output) always == len(input).
    # Using pandas Series for the rolling window — avoids np.convolve mode="same"
    # which divides boundary values by the full kernel length even with partial overlap.
    import pandas as _pd
    instant_load = (
        _pd.Series(intensity_factor)
        .rolling(window=5, min_periods=1)
        .mean()
        .to_numpy()
    )
    instant_load = np.clip(instant_load, 0, 1)

    # --- Timescale 2: accumulated fatigue ---
    # PROXY: TSS-inspired running sum (power_w = REAL, ftp_w = PROXY → ratio PROXY).
    tss_per_sample = (power / ftp_w) ** 2
    tss_cumulative = np.cumsum(tss_per_sample)
    fatigue = np.clip(tss_cumulative / _TSS_NORM, 0, 1)

    # --- Combined: noisy-OR ---
    load = 1 - (1 - _W_INSTANT * instant_load) * (1 - _W_FATIGUE * fatigue)
    load = np.clip(load, 0, 1)
    attention = 1 - load

    return instant_load, fatigue, load, attention
