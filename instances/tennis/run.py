"""
Tennis instance — orchestration.

Deliberately minimal compared to F1's run.py: no visualize.py yet,
because the point of this instance is narrow — test whether
core.governance's deferred queue actually resolves in a domain with a
real recovery window, not build a full reporting suite for a
hypothetical dataset. Scope choice, not an oversight.

The only hand-placed event: ONE voice_requested=True fired mid-point,
late in a rally (point_progress > 0.7), where budget should be too
low to admit it. Everything after that — whether/when it resolves —
comes out of govern_hybrid() and VoiceQueue on their own.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.governance import govern_hybrid, VoiceQueue
from instances.tennis.data_loader import load
from instances.tennis.load_model import compute_load
from instances.tennis.reflex_trigger import reflex_series
from instances.tennis.config import CHANNELS

samples = load()
load_arr, attention = compute_load(samples)
reflex_flags = reflex_series(samples)

request_i = next(i for i, s in enumerate(samples)
                  if s["phase"] == "point" and s["point_progress"] > 0.7)

queue = VoiceQueue(expiry_samples=30)
active_sets = []
for i in range(len(samples)):
    voice_requested = (i == request_i)
    active = govern_hybrid(CHANNELS, attention[i], reflex_flags[i],
                            voice_requested=voice_requested, risk_present=False,
                            queue=queue, i=i)
    active_sets.append(active)

resolved_i = next((i for i in range(request_i, len(samples))
                    if "Voice" in active_sets[i]), None)


def channel_airtime():
    n = len(samples)
    return {name: sum(name in a for a in active_sets) / n
            for name, *_ in CHANNELS}


if __name__ == "__main__":
    print("=" * 64)
    print("ATTENTION-GOVERNANCE ENGINE — tennis (hypothetical, step 4)")
    print("=" * 64)
    print(f"samples: {len(samples)} | points modeled: "
          f"{sum(1 for s in samples if s['phase'] == 'point' and s['point_progress'] == 0)}")

    print("\nchannel airtime over the session (share of samples speaking):")
    for name, share in channel_airtime().items():
        print(f"    {name:9s} {share*100:5.1f}%")

    req = samples[request_i]
    print(f"\n  VOICE REQUESTED  (sample {request_i}, mid-point, "
          f"progress {req['point_progress']:.2f}, attention {attention[request_i]:.2f})")
    print(f"    admitted immediately: {'Voice' in active_sets[request_i]}")

    if resolved_i is not None:
        res = samples[resolved_i]
        print(f"\n  RESOLVED  (sample {resolved_i}, phase '{res['phase']}', "
              f"{resolved_i - request_i} samples later, "
              f"attention {attention[resolved_i]:.2f})")
    else:
        print("\n  NEVER RESOLVED within this session — queue still waiting "
              f"({queue.waiting} pending) or expired unresolved.")
