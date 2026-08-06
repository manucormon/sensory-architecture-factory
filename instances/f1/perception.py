"""
F1 instance — perception layer.

Thin passthrough. The F1 telemetry file already contains
DistanceToDriverAhead, computed by the FIA timing system before this
repo ever sees the data. No tracking was done here — the external
system did it.

This instance never needed a TRACKED field. The timing system delivers
gap-to-rival as a MEASURED quantity directly in the CSV. If a future
F1 instance adds vision-based tracking (e.g. side-mirror camera to
detect rival presence not captured by timing), that field would be
TRACKED and would require a real tracker — not this file.

Perceptual state per sample (all MEASURED):
  gap_m   — DistanceToDriverAhead in metres, as delivered by FIA timing.
             NaN when no rival is within range of the timing system;
             load_model.py already handles this with np.where(np.isfinite).
"""

import pandas as pd


HAS_PERCEPTION = True


def perceive(df: pd.DataFrame) -> pd.DataFrame:
    """
    Return the input DataFrame unchanged — the relevant perceptual field
    (DistanceToDriverAhead) is already present as a MEASURED column.
    This function exists to make the perception contract explicit, not to
    compute anything new.
    """
    # Confirm the MEASURED field is present; fail loudly if the telemetry
    # format changes and the column disappears.
    assert "DistanceToDriverAhead" in df.columns, (
        "perception: expected MEASURED column 'DistanceToDriverAhead' "
        "not found in telemetry DataFrame."
    )
    return df
