"""
ENMAX instance — orchestration.

Wires data_loader + perception + load_model + reflex_trigger + observer
into core.governance. Reports four moments:

  STORM PEAK     — highest combined load during the storm event
  P1 ACTIVE      — first sample with P1 reflex firing
  POST-STORM LULL — most-open moment (Voice opens here)
  LATE SHIFT     — same incident count as morning, but fatigue is high
                   (demonstrates two-timescale divergence in a real context)

Also runs the observer agent over the full shift to show what a supervisor
system would receive.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import numpy as np

from core.governance import govern_series, govern_hybrid
from instances.enmax.data_loader import load, SHIFT_DURATION_S
from instances.enmax.perception import perceive
from instances.enmax.load_model import compute_load
from instances.enmax.reflex_trigger import reflex_series, HAS_REFLEX
from instances.enmax.config import CHANNELS, SAMPLE_RATE_HZ
from agents.observer import Observer

samples = load()
samples = perceive(samples)

instant_load, fatigue, load_arr, attention = compute_load(samples)
reflex_flags = reflex_series(samples)
active_sets = govern_series(CHANNELS, attention, reflex_flags)

phases = [s["phase"] for s in samples]


def _phase_mask(name):
    return np.array([p == name for p in phases])


# Key moments
storm_i   = int(np.argmax(load_arr * _phase_mask("storm_event")))
lull_i    = int(np.argmax(attention * _phase_mask("post_storm_lull")))
p1_i      = int(np.argmax(reflex_flags))
# Two-timescale: find morning and late-shift samples with similar incident count
target_inc = samples[storm_i // 3]["active_incidents"]  # early-shift moderate load
similar = [i for i, s in enumerate(samples)
           if abs(s["active_incidents"] - target_inc) <= 1
           and s["phase"] != "storm_event"]
early_i = similar[0] if similar else 0
late_i  = similar[-1] if similar else len(samples) - 1


def describe(i, label):
    s = samples[i]
    chans = [n for n, *_ in CHANNELS if n in active_sets[i]]
    print(f"\n  {label}")
    print(f"    t={s['time_s']//3600:.0f}h{(s['time_s']%3600)//60:02d}m | "
          f"phase={s['phase']}")
    print(f"    incidents={s['active_incidents']} | queue={s['queue_depth']} | "
          f"P1={'YES' if s['p1_active'] else 'no'} | "
          f"crew_avail={s['crew_available']:.0%}")
    print(f"    instant={instant_load[i]:.2f} | "
          f"fatigue={fatigue[i]:.2f} | "
          f"load={load_arr[i]:.2f} → attention={attention[i]:.2f}")
    print(f"    channels speaking: {', '.join(chans) if chans else 'SILENCE'}")


if __name__ == "__main__":
    print("=" * 64)
    print("ATTENTION-GOVERNANCE ENGINE — ENMAX dispatcher (12h shift)")
    print("=" * 64)
    print(f"samples: {len(samples)} | shift: {SHIFT_DURATION_S//3600}h "
          f"| rate: {SAMPLE_RATE_HZ} Hz | HAS_REFLEX: {HAS_REFLEX}")
    print(f"load range: {load_arr.min():.2f}–{load_arr.max():.2f}")

    print(f"\nchannel airtime over the shift (share of samples speaking):")
    for name, *_ in CHANNELS:
        airtime = sum(1 for s in active_sets if name in s) / len(samples)
        print(f"    {name:9s} {airtime*100:5.1f}%")

    describe(storm_i, "STORM PEAK  (maximum cognitive load — Voice blocked)")
    describe(p1_i,    "P1 ACTIVE   (Touch fires regardless of budget)")
    describe(lull_i,  "POST-STORM LULL (Voice opens — supervisor coaching arrives here)")
    describe(early_i, f"EARLY SHIFT  (same incidents, low fatigue)")
    describe(late_i,  f"LATE SHIFT   (same incidents, fatigue={fatigue[late_i]:.2f})")

    print("\n" + "=" * 64)
    print("OBSERVER AGENT — what a supervisor system receives this shift")
    print("=" * 64)
    obs = Observer(
        sample_rate_hz=SAMPLE_RATE_HZ,
        sustained_load_threshold=0.80,
        sustained_load_window_s=900,
        fatigue_ceiling=0.70,
        attention_floor=0.15,
        attention_floor_window_s=300,
    )
    alerts = obs.scan(load_arr, attention, fatigue)
    print(f"\nTotal alerts fired: {len(alerts)}")
    by_type = {}
    for a in alerts:
        by_type.setdefault(a.alert_type, 0)
        by_type[a.alert_type] += 1
    for t, c in by_type.items():
        print(f"  {t}: {c}")
