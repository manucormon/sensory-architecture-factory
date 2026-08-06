"""
Cycling instance — tuned channel config.

TUNING HISTORY (required transparency per CONTRACT.md):

First attempt: Sound=0.15, Vision=0.25, Presence=0.15, Voice=0.25.
Test result: Voice stayed CLOSED at the best descent (attention=0.74).
  Sound+Vision+Presence = 0.55 consumed; remaining = 0.19 < Voice(0.25).
  Same symptom as F1, which was the wrong finding for this domain.

Root cause: the first attempt imported too much of F1's cost intuition.
In cycling, all non-Voice channels are lighter than in F1:
  - Sound: ambient race noise and radio static — always present, near-
    subliminal. Lighter than F1's directional earcon (no sudden "rival
    entering your zone" moment; the peloton is a known constant).
  - Vision: road ahead and competitors — important, but the time horizon
    is longer than F1's split-second gap check. Glanceable, not urgent.
  - Presence: heart-rate/power zone on a head unit — truly ambient,
    requires no decision. Lighter than F1.
  - Voice: the directeur sportif model is constant contact, not a rare
    deliberate act. Exchanges are short ("attack now", "sit in", "eat").

Revised costs: Sound=0.10, Vision=0.20, Presence=0.10, Voice=0.20.
Verification at best descent (attention=0.74):
  Sound(0.10) + Vision(0.20) + Presence(0.10) = 0.40 spent.
  Remaining = 0.34 >= Voice(0.20) → Voice OPENS. ✓
  Confirmed by test_voice_opens_on_descent_with_fresh_request.

At climb peak (attention ~0.26):
  Remaining after non-Voice = 0.26 - 0.40 → budget exhausted before Voice.
  Voice stays closed at peak load — also correct behavior.
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
