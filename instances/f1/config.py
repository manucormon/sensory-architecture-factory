"""
F1 instance — tuned channel config.
Same values as core.channels_schema.DEFAULT_CHANNELS, declared here
explicitly so this instance is self-contained and can diverge later
without touching the core or other instances.
"""

from core.channels_schema import CORE_VERSION

CORE_VERSION_REQUIRED = "1.0"
assert CORE_VERSION == CORE_VERSION_REQUIRED, (
    f"core version mismatch: this instance requires {CORE_VERSION_REQUIRED}, "
    f"core is {CORE_VERSION}. Update the instance or pin to the correct core."
)

# REAL: F1 telemetry at ~10 Hz (one sample per ~100ms positional log entry).
# VoiceQueue expiry_samples should be derived from real time:
#   expiry_samples = SAMPLE_RATE_HZ * expiry_seconds
SAMPLE_RATE_HZ = 10

GOVERNED_DRIVER = "VER"  # Verstappen: the one making the overtake = max pressure

CHANNELS = [
    # name        priority  cost   note
    ("Touch",      0,       0.00, "reflex: braking point / imminent contact"),
    ("Sound",      1,       0.25, "one directional earcon (rival in your zone)"),
    ("Vision",     2,       0.40, "glanceable gap / position / flag"),
    ("Presence",   3,       0.15, "ambient clear-vs-hazard, near-subliminal"),
    ("Voice",      4,       0.70, "deliberative radio / queries — never mid-corner"),
]
