"""
Cycling instance — tuned channel config.

Data provenance (v2 — real data):
  Source: GoldenCheetah OpenData, ride 2019-12-28, mountain loop.
  power_w = REAL (power meter). FTP = 240W = PROXY (95% best 20-min rolling).
  gradient_pct = MEASURED (GPS altitude, 60s window). phase = PROXY (gradient threshold).
  HAS_REFLEX = False: no crash label exists in real ride data.

TUNING HISTORY (required transparency per CONTRACT.md):

DECLARED prototype (v1):
  First attempt: Sound=0.15, Vision=0.25, Presence=0.15, Voice=0.25.
  Test result: Voice stayed CLOSED at the best descent (attention=0.74).
    Sound+Vision+Presence = 0.55; remaining = 0.19 < Voice(0.25). Wrong.

  Root cause: imported too much of F1's cost intuition.
  Revised costs: Sound=0.10, Vision=0.20, Presence=0.10, Voice=0.20.
  Verification at best descent (attention=0.74):
    Sound+Vision+Presence = 0.40; remaining = 0.34 >= Voice(0.20) → OPENS ✓

Real data (v2) — costs UNCHANGED, re-verified against real ride:
  Descent power mean = 19W (mostly coasting) → attention is very high on descents.
  Voice-opens-on-descent re-confirmed with real attention values.
  Climb power mean = 260W (108% FTP) → budget exhausted on all climbs ✓
"""

from core.channels_schema import CORE_VERSION

CORE_VERSION_REQUIRED = "1.0"
assert CORE_VERSION == CORE_VERSION_REQUIRED, (
    f"core version mismatch: this instance requires {CORE_VERSION_REQUIRED}, "
    f"core is {CORE_VERSION}."
)

# PROXY: power meter at 1 Hz is the standard for cycling telemetry.
# expiry_samples = SAMPLE_RATE_HZ * expiry_seconds
SAMPLE_RATE_HZ = 1

HAS_RECOVERY_WINDOW = True       # descents and flat sections — geographic, not ruled
HAS_MULTI_TIMESCALE_LOAD = True  # instantaneous power + accumulated stage fatigue

CHANNELS = [
    # name        priority  cost   note
    ("Touch",      0,       0.00, "reflex: crash ahead / sudden wheel touch"),
    ("Sound",      1,       0.10, "ambient race noise + radio static — near-subliminal"),
    ("Vision",     2,       0.20, "road ahead, competitor position — longer horizon than F1"),
    ("Presence",   3,       0.10, "heart-rate/power zone on head unit — truly ambient"),
    ("Voice",      4,       0.20, "directeur sportif — constant contact, short exchanges"),
]
