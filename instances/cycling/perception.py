"""
Cycling instance — perception layer.

HAS_PERCEPTION = True. This instance performs real perceptual extraction:
gradient and phase are computed from raw GPS altitude data by data_loader.py's
cleaning pipeline. The resulting fields are attached to every row.

Why True here but False for tennis/synthetic cycling:
  - The source is a real power-meter ride with GPS altitude (REAL).
  - gradient_pct is derived from that signal via a 60s central-difference
    window — it is a MEASURED quantity: computed here from raw sensor input.
  - phase is PROXY: a label derived from gradient_pct via fixed thresholds.
    The thresholds are a design choice, not a measurement.

Fields exposed:
  gradient_pct  MEASURED — computed from GPS altitude in data_loader cleaning
  phase         PROXY    — threshold-derived from gradient_pct (>3%=climb, <-3%=descent)

These fields are already present in the DataFrame returned by data_loader.load().
perceive() validates that they exist and returns the DataFrame unchanged — the
perceptual work happened at cleaning time, not at runtime. This is correct:
the FIA timing system pre-computed DistanceToDriverAhead for F1; the cleaning
pipeline pre-computed gradient_pct and phase here.
"""

import pandas as pd

HAS_PERCEPTION = True   # gradient_pct = MEASURED, phase = PROXY


def perceive(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validate and pass through the ride DataFrame.

    The perceptual fields (gradient_pct, phase) were computed during data
    cleaning; this function asserts they are present and well-formed.
    Returns the same DataFrame — no new columns added.
    """
    assert "gradient_pct" in df.columns, \
        "gradient_pct missing — was the ride pre-processed by the cleaning pipeline?"
    assert "phase" in df.columns, \
        "phase missing — was the ride pre-processed by the cleaning pipeline?"
    assert set(df["phase"].unique()).issubset({"climb", "descent", "flat"}), \
        f"unexpected phase values: {df['phase'].unique()}"
    assert df["gradient_pct"].between(-20, 20).all(), \
        "gradient_pct out of ±20% bounds — check cleaning pipeline clip"
    return df
