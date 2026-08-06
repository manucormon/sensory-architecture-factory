"""
F1 instance — cognitive-load proxy.
Mechanical extraction of the load-proxy block from the original
governance_engine.py (lines 40-70). Same math, same values.

HONEST ASSUMPTION (unchanged from the original): we have telemetry but
no biometric data, so "cognitive load" is a PROXY derived from the car
data (cornering force, braking, proximity to the rival) — it stands in
for the watch/biometric signal that would drive the real system.

Exposes decel and gap alongside load/attention because reflex_trigger.py
needs them too (same two signals feed both the load model and the
reflex check, as in the original file).
"""

import numpy as np
import pandas as pd

from core.governance import norm


def compute_load(df):
    v = df["Speed"].to_numpy() / 3.6              # m/s
    t = df["t"].to_numpy()
    x, y = df["X"].to_numpy(), df["Y"].to_numpy()
    dt = np.gradient(t)
    dt[dt == 0] = np.nan

    # lateral acceleration from the trajectory = cornering load
    heading = np.arctan2(np.gradient(y), np.gradient(x))
    yaw_rate = np.abs(np.gradient(np.unwrap(heading)) / dt)
    lateral = np.nan_to_num(v * yaw_rate)

    # braking effort (deceleration when on the brakes)
    decel = np.clip(-np.gradient(v) / dt, 0, None)
    decel = np.nan_to_num(np.where(df["Brake"].to_numpy(), decel, 0.0))

    # proximity to the rival ahead: only true wheel-to-wheel counts as combat load
    gap = df["DistanceToDriverAhead"].to_numpy()
    gap = np.where(np.isfinite(gap), gap, 200.0)
    proximity = np.clip(1 - gap / 20.0, 0, 1)      # ramps under 20 m, maxes wheel-to-wheel

    # noisy-OR: load is high if cornering OR braking OR combat is high (any one
    # extreme taxes the driver). Matches reality better than a weighted average,
    # where no single demand could ever push load to its peak.
    corner_load = norm(lateral)
    brake_load = norm(decel)
    combat_load = proximity
    load_raw = 1 - (1 - 0.85 * corner_load) * (1 - brake_load) * (1 - combat_load)
    load = pd.Series(load_raw).rolling(5, center=True, min_periods=1).mean().to_numpy()
    load = np.clip(load, 0, 1)

    attention = 1 - load                            # available attention budget

    return load, attention, decel, gap, corner_load
