"""
Cycling instance — orchestration.

Data source: GoldenCheetah Open Data Project, ride 2019-12-28.
power_w = REAL | gradient_pct = MEASURED | phase = PROXY | FTP = PROXY
HAS_REFLEX = False (no crash labels in real ride data).

Reports two moments:
  CLIMB PEAK   — highest combined load (both timescales maxed)
  DESCENT      — most-open moment, primary recovery window for Voice

Also demonstrates two-timescale divergence with real data: same instantaneous
power at different stage times produces different combined load.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np

from core.governance import govern_series
from instances.cycling.data_loader import load, FTP_W
from instances.cycling.perception import perceive
from instances.cycling.load_model import compute_load
from instances.cycling.config import CHANNELS, SAMPLE_RATE_HZ

df_raw = load()
df = perceive(df_raw)

instant_load, fatigue, load_arr, attention = compute_load(df, FTP_W)
phases = df["phase"].tolist()

reflex_flags = np.zeros(len(df), dtype=bool)   # HAS_REFLEX = False
active_sets = govern_series(CHANNELS, attention, reflex_flags)

# --- Key moments ---
climb_i = int(np.argmax(load_arr))
descent_mask = np.array([p == "descent" for p in phases])
descent_i = int(np.argmax(attention * descent_mask)) if descent_mask.any() \
    else int(np.argmax(attention))

# Two-timescale divergence: find early and late samples with similar instant load
target_instant = float(instant_load[climb_i])
similar = np.abs(instant_load - target_instant) < 0.05
early_i = int(np.argmax(similar))
late_i = len(df) - 1 - int(np.argmax(similar[::-1]))


def describe(i, label):
    chans = [n for n, *_ in CHANNELS if n in active_sets[i]]
    print(f"\n  {label}  (t={int(df['secs'].iloc[i])}s, phase='{df['phase'].iloc[i]}')")
    print(f"    power {df['power_w'].iloc[i]:.0f}W  ({df['power_w'].iloc[i]/FTP_W*100:.0f}% FTP) | "
          f"gradient {df['gradient_pct'].iloc[i]:+.1f}%")
    print(f"    instant load {instant_load[i]:.2f} | "
          f"fatigue {fatigue[i]:.2f} | "
          f"combined load {load_arr[i]:.2f} → attention {attention[i]:.2f}")
    print(f"    channels speaking: {', '.join(chans) if chans else 'SILENCE'}")


if __name__ == "__main__":
    print("=" * 64)
    print("ATTENTION-GOVERNANCE ENGINE — cycling (real ride, GC OpenData)")
    print("=" * 64)
    print(f"samples: {len(df)} | duration: {int(df['secs'].max()/60)} min "
          f"| rate: {SAMPLE_RATE_HZ} Hz | FTP: {FTP_W}W (PROXY)")
    print(f"load range: {load_arr.min():.2f}–{load_arr.max():.2f}")

    phase_dist = {p: phases.count(p) for p in ['climb', 'descent', 'flat']}
    print(f"phase distribution: " +
          " | ".join(f"{p}={n}s ({n/len(df)*100:.0f}%)" for p, n in phase_dist.items()))

    print(f"\nchannel airtime over the ride (share of samples speaking):")
    for name, *_ in CHANNELS:
        airtime = sum(1 for s in active_sets if name in s) / len(df)
        print(f"    {name:9s} {airtime*100:5.1f}%")

    describe(climb_i, "CLIMB PEAK   (both timescales maxed)")
    describe(descent_i, "DESCENT      (primary recovery window — Voice opens here)")

    print(f"\n  TWO-TIMESCALE DIVERGENCE — same instant load, different fatigue:")
    describe(early_i, f"EARLY RIDE   (instant~{instant_load[early_i]:.2f}, fatigue low)")
    describe(late_i,  f"LATE RIDE    (instant~{instant_load[late_i]:.2f}, fatigue high)")

    out_path = os.path.join(os.path.dirname(__file__), "cycling_governed.csv")
    df_out = df.copy()
    df_out["instant_load"] = instant_load
    df_out["fatigue"] = fatigue
    df_out["load"] = load_arr
    df_out["attention"] = attention
    for name, *_ in CHANNELS:
        df_out[name] = [name in s for s in active_sets]
    df_out.to_csv(out_path, index=False)
    print(f"\nsaved per-sample decisions → {out_path}")
