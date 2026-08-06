"""
Cycling instance — orchestration.

Wires data_loader + load_model + reflex_trigger + config into core.governance.
Reports two moments (unlike F1's corner/straight dichotomy):
  CLIMB PEAK   — highest combined load in the stage (both timescales maxed)
  DESCENT      — most-open moment, primary recovery window for Voice

Also reports how the two timescales diverge: same instantaneous power at
different stage times can produce very different combined load — that
divergence is the whole point of this instance.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np

from core.governance import govern_series, govern_hybrid, VoiceQueue
from instances.cycling.data_loader import load, STAGE_DURATION_S
from instances.cycling.load_model import compute_load
from instances.cycling.reflex_trigger import reflex_series
from instances.cycling.config import CHANNELS, SAMPLE_RATE_HZ

samples = load()
instant_load, fatigue, load_arr, attention = compute_load(samples)
reflex_flags = reflex_series(samples)

active_sets = govern_series(CHANNELS, attention, reflex_flags)

# Annotate samples with governance decisions
for i, s in enumerate(samples):
    s["instant_load"] = instant_load[i]
    s["fatigue"] = fatigue[i]
    s["load"] = load_arr[i]
    s["attention"] = attention[i]
    for name, *_ in CHANNELS:
        s[name] = name in active_sets[i]

# --- Key moments ---
phases = [s["phase"] for s in samples]
climb_i = int(np.argmax(load_arr))
descent_mask = np.array([p == "descent" for p in phases])
descent_i = int(np.argmax(attention * descent_mask)) if descent_mask.any() else int(np.argmax(attention))

# --- Two-timescale divergence demonstration ---
# Find two samples with similar instantaneous load but different fatigue
target_instant = instant_load[climb_i]
similar_instant = np.abs(instant_load - target_instant) < 0.05
early_i = int(np.argmax(similar_instant))  # first occurrence
late_i = len(samples) - 1 - int(np.argmax(similar_instant[::-1]))  # last occurrence


def describe(i, label):
    s = samples[i]
    chans = [n for n, *_ in CHANNELS if s[n]]
    print(f"\n  {label}  (t={s['time_s']}s, phase='{s['phase']}')")
    print(f"    power {s['power_w']:.0f}W  ({s['power_w']/s['ftp_w']*100:.0f}% FTP) | "
          f"gradient {s['gradient_pct']:+.1f}%")
    print(f"    instant load {s['instant_load']:.2f} | "
          f"fatigue {s['fatigue']:.2f} | "
          f"combined load {s['load']:.2f} → attention {s['attention']:.2f}")
    print(f"    channels speaking: {', '.join(chans) if chans else 'SILENCE'}")


if __name__ == "__main__":
    print("=" * 64)
    print("ATTENTION-GOVERNANCE ENGINE — cycling (mountain stage, declared)")
    print("=" * 64)
    print(f"samples: {len(samples)} | duration: {STAGE_DURATION_S}s "
          f"| sample rate: {SAMPLE_RATE_HZ} Hz")
    print(f"load range: {load_arr.min():.2f}–{load_arr.max():.2f}")
    print(f"\nchannel airtime over the stage (share of samples speaking):")
    for name, *_ in CHANNELS:
        airtime = sum(s[name] for s in samples) / len(samples)
        print(f"    {name:9s} {airtime*100:5.1f}%")

    describe(climb_i, "CLIMB PEAK   (both timescales maxed)")
    describe(descent_i, "DESCENT      (primary recovery window — Voice opens here)")

    print(f"\n  TWO-TIMESCALE DIVERGENCE — same instant load, different fatigue:")
    describe(early_i, f"EARLY STAGE  (instant~{instant_load[early_i]:.2f}, fatigue low)")
    describe(late_i,  f"LATE STAGE   (instant~{instant_load[late_i]:.2f}, fatigue high)")

    out_path = os.path.join(os.path.dirname(__file__), "cycling_governed.csv")
    import csv
    keys = list(samples[0].keys())
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(samples)
    print(f"\nsaved per-sample decisions → {out_path}")
