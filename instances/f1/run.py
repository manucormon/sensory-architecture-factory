"""
F1 instance — orchestration.
Wires data_loader + load_model + reflex_trigger + config into
core.governance, and reproduces the same console output and
ver_governed.csv as the original governance_engine.py.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np

from core.governance import govern_series
from instances.f1.data_loader import load
from instances.f1.load_model import compute_load
from instances.f1.reflex_trigger import reflex_series
from instances.f1.config import GOVERNED_DRIVER, CHANNELS

ver = load(GOVERNED_DRIVER)
load_arr, attention, decel, gap, corner_load = compute_load(ver)
reflex_flags = reflex_series(decel, gap)

active_sets = govern_series(CHANNELS, attention, reflex_flags)
ver["load"] = load_arr
ver["attention"] = attention
for name, *_ in CHANNELS:
    ver[name] = [name in s for s in active_sets]

# --------------------------------------------------- the two moments
corner_i = int(np.nanargmin(np.where(gap > 0, gap, np.inf)))
straight_mask = (ver["Throttle"] >= 99) & (~ver["Brake"]) & (corner_load < 0.15)
open_i = int(ver.index[straight_mask][np.nanargmax(ver["Speed"][straight_mask])]) \
    if straight_mask.any() else int(np.nanargmax(ver["Speed"].to_numpy()))


def describe(i, label):
    chans = [n for n, *_ in CHANNELS if ver[n].iloc[i]]
    print(f"\n  {label}  (sample {i}, {ver['Distance'].iloc[i]:.0f} m into the lap)")
    print(f"    speed {ver['Speed'].iloc[i]:.0f} km/h | "
          f"brake {'ON' if ver['Brake'].iloc[i] else 'off'} | "
          f"gap to rival {gap[i]:.1f} m")
    print(f"    cognitive load {load_arr[i]:.2f}  ->  attention {attention[i]:.2f}")
    print(f"    channels speaking: {', '.join(chans) if chans else 'SILENCE'}")


def _default_output() -> str:
    return os.path.join(os.path.dirname(__file__), "ver_governed.csv")


def main(output_path=None):
    out = output_path or _default_output()
    print("=" * 64)
    print(f"ATTENTION-GOVERNANCE ENGINE — {GOVERNED_DRIVER}, Abu Dhabi 2021 final lap")
    print("=" * 64)
    print(f"samples: {len(ver)} | lap distance: {ver['Distance'].max():.0f} m | "
          f"load range: {load_arr.min():.2f}-{load_arr.max():.2f}")
    print(f"\nchannel airtime over the lap (share of samples speaking):")
    for name, *_ in CHANNELS:
        print(f"    {name:9s} {ver[name].mean()*100:5.1f}%")

    describe(corner_i, "THE CORNER  (attention near zero - bullet-time moment)")
    describe(open_i,   "THE STRAIGHT (attention open - system opens up)")

    ver.to_csv(out, index=False)
    print(f"\nsaved per-sample decisions -> {out}")
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="F1 governance report")
    parser.add_argument(
        "--output", default=None,
        help="Path for the output CSV (default: instances/f1/ver_governed.csv)"
    )
    args = parser.parse_args()
    main(output_path=args.output)
