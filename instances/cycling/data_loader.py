"""
Cycling instance — data loading.

Source: GoldenCheetah Open Data Project (https://osf.io/6hfpz/, DOI 10.17605/OSF.IO/6HFPZ).
Athlete: anonymised contributor, ride date 2019-12-28, mountain loop.
License: open access for research use, no personally identifiable information.

The raw file (gc_opendata_ride.csv) was cleaned as follows:
  - Gradient computed from a 60-second central-difference window on GPS altitude
    (per-sample 1s diff was too noisy; 60s window gives a stable signal).
  - Gradient clipped to ±20% (physical ceiling for paved mountain roads).
  - Phase derived from gradient: climb (>3%), descent (<-3%), flat (otherwise).
  - All other fields (power_w, hr_bpm, alt_m) passed through unchanged.
  - FTP = 240W — PROXY: 95% of the best 20-minute rolling mean power in this ride.
    Industry standard estimation method. Not a lab test.

Labeling:
  power_w       — REAL: recorded by a power meter on the rider's bike.
  hr_bpm        — REAL: heart-rate monitor (not used by load_model.py today).
  alt_m         — REAL: GPS barometric altitude (raw, 1Hz).
  gradient_pct  — MEASURED: computed by perception.py from GPS altitude.
  phase         — PROXY: threshold-derived from gradient_pct in perception.py.
  ftp_w         — PROXY: 95% of best 20-min rolling power (not a lab test).
"""

import os
import pandas as pd

FTP_W = 240   # PROXY — see module docstring

_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "gc_opendata_ride.csv")


def load() -> pd.DataFrame:
    """
    Return the cleaned ride as a DataFrame.

    Columns: secs, km, power_w, hr_bpm, alt_m, gradient_pct, phase.
    No ftp_w column — callers that need it should use the module constant FTP_W.
    """
    df = pd.read_csv(_DATA_PATH)
    return df
