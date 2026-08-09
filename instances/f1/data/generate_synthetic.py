"""
Generate synthetic F1 lap data for testing — DECLARED.

All values are invented to exercise 5 governance scenarios:
  1. Long straight (low load, channels open)
  2. High-speed corner (high lateral load, channels narrow)
  3. Heavy braking zone (decel spike)
  4. Wheel-to-wheel combat (gap < 5 m, reflex Touch fires)
  5. Recovery (load drops, Voice reopens)

Run this script to regenerate the CSV:
  python3 instances/f1/data/generate_synthetic.py

Output: instances/f1/data/synthetic_lap.csv
Columns match the real data layout so data_loader.py works unchanged.
DATA_LABEL: DECLARED — no real F1 telemetry used.
"""

import csv
import math
import os

OUT = os.path.join(os.path.dirname(__file__), "synthetic_lap.csv")

# --- lap geometry: an oval approximation (straight + corner × 2) -----------
# 200 samples, 1 sample per ~0.25s → ~50s lap (short for testing)
SAMPLES = 200
DT = 0.25  # seconds per sample

# Phases (sample ranges):
# 0-49    long straight (Throttle 100%, low load)
# 50-99   high-speed corner (lateral G, high load)
# 100-124 braking zone (Brake=True, decel spike)
# 125-149 combat (gap to rival < 5m, reflex should fire)
# 150-199 recovery / second straight

rows = []
t = 0.0
distance = 0.0

# Simple oval: straight on Y axis, corners at top/bottom
# We trace it parametrically to give X/Y coords
total_angle = 0.0

for i in range(SAMPLES):
    phase = (
        "straight1"  if i < 50   else
        "corner"     if i < 100  else
        "braking"    if i < 125  else
        "combat"     if i < 150  else
        "straight2"
    )

    if phase == "straight1":
        speed_kmh = 300.0
        throttle  = 100.0
        brake     = False
        rpm       = 12000
        gear      = 8
        gap       = 200.0   # no rival visible
        # straight: move in +Y direction
        x = 0.0
        y = float(i * 8)
        z = 0.0
    elif phase == "corner":
        # decreasing speed, curving left
        frac = (i - 50) / 50.0
        speed_kmh = 300.0 - frac * 150.0   # 300 → 150
        throttle  = max(20.0, 100.0 - frac * 80.0)
        brake     = False
        rpm       = int(12000 - frac * 4000)
        gear      = max(4, 8 - int(frac * 4))
        gap       = 200.0
        angle     = math.radians(frac * 180)   # sweeps 0 → π
        r         = 80.0
        x         = r * math.sin(angle)
        y         = 400.0 + r * math.cos(angle)
        z         = 0.0
    elif phase == "braking":
        frac = (i - 100) / 25.0
        speed_kmh = 150.0 - frac * 100.0
        throttle  = 0.0
        brake     = True
        rpm       = int(8000 - frac * 2000)
        gear      = max(2, 4 - int(frac * 2))
        gap       = 200.0
        x         = 0.0
        y         = 800.0 - float((i - 100) * 3)
        z         = 0.0
    elif phase == "combat":
        speed_kmh = 50.0 + (i - 125) * 2.0   # slowly accelerating out of chicane
        throttle  = 60.0
        brake     = False
        rpm       = 7000
        gear      = 3
        gap       = max(1.0, 10.0 - (i - 125) * 0.3)  # rival closes in then passes
        x         = 0.0
        y         = 730.0 + float((i - 125) * 4)
        z         = 0.0
    else:  # straight2
        speed_kmh = 50.0 + (i - 150) * 5.0
        speed_kmh = min(speed_kmh, 300.0)
        throttle  = 100.0
        brake     = False
        rpm       = min(12000, 7000 + (i - 150) * 200)
        gear      = min(8, 3 + (i - 150) // 10)
        gap       = 200.0
        x         = 0.0
        y         = 830.0 + float((i - 150) * 8)
        z         = 0.0

    distance += speed_kmh / 3.6 * DT

    rows.append({
        "Date":                  "2021-12-12 14:32:12.000",
        "SessionTime":           f"0 days 02:31:{t:06.3f}",
        "DriverAhead":           "" if gap > 50 else "HAM",
        "DistanceToDriverAhead": round(gap, 3),
        "Time":                  f"0 days 00:00:{t:09.6f}",
        "RPM":                   rpm,
        "Speed":                 round(speed_kmh, 4),
        "nGear":                 gear,
        "Throttle":              round(throttle, 1),
        "Brake":                 brake,
        "DRS":                   1 if phase in ("straight1", "straight2") else 0,
        "Source":                "declared",
        "Distance":              round(distance, 4),
        "RelativeDistance":      round(distance / 5200, 8),
        "Status":                "OnTrack",
        "X":                     round(x, 6),
        "Y":                     round(y, 6),
        "Z":                     round(z, 6),
    })

    t += DT

with open(OUT, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)

print(f"Written {len(rows)} samples → {OUT}")
print("DATA_LABEL: DECLARED — no real F1 telemetry.")
