"""
F1 instance — data loading.
Mechanical extraction of load() from the original governance_engine.py.
"""

import os
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")


def load(code):
    df = pd.read_csv(os.path.join(DATA_DIR, f"abudhabi2021_{code}_lastlap.csv"))
    df["t"] = pd.to_timedelta(df["Time"]).dt.total_seconds()
    df["Brake"] = df["Brake"].astype(str).str.lower().eq("true")
    for c in ["Speed", "Throttle", "RPM", "nGear", "Distance",
              "DistanceToDriverAhead", "X", "Y"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
