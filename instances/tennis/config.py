"""
Tennis instance — tuned channel config.

Voice is tuned cheap on purpose (0.20, vs F1's 0.70) — this domain's
own rules place coaching inside the recovery window, not in
competition with play. The test this instance exists to run: does
Voice actually open once budget reopens between points, unlike F1
where it stayed closed even at the most open moment measured?
"""

from core.channels_schema import CORE_VERSION

CORE_VERSION_REQUIRED = "1.0"
assert CORE_VERSION == CORE_VERSION_REQUIRED, (
    f"core version mismatch: this instance requires {CORE_VERSION_REQUIRED}, "
    f"core is {CORE_VERSION}. Update the instance or pin to the correct core."
)

# DECLARED: synthetic data, one sample per modeled event (~1s intervals).
# In a real tennis implementation, derive from actual sensor/video frame rate.
SAMPLE_RATE_HZ = 1

CHANNELS = [
    # name        priority  cost   note
    ("Touch",      0,       0.00, "reflex: serve / mid-rally smash reaction"),
    ("Sound",      1,       0.20, "ball impact, umpire call, crowd swell"),
    ("Vision",     2,       0.35, "ball trajectory, opponent position"),
    ("Presence",   3,       0.15, "ambient score / momentum awareness"),
    ("Voice",      4,       0.20, "coaching — cheap by design, belongs in the recovery window"),
]

HAS_RECOVERY_WINDOW = True
HAS_MULTI_TIMESCALE_LOAD = False
