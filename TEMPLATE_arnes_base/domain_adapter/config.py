"""
<DOMAIN> instance — tuned channel config.

Do NOT copy F1's values without checking they fit. See CONTRACT.md —
Voice in particular has already shown opposite tunings across domains
(expensive and rare in F1, cheap and constant in cycling).
"""

from core.channels_schema import CORE_VERSION

CORE_VERSION_REQUIRED = "1.0"
assert CORE_VERSION == CORE_VERSION_REQUIRED, (
    f"core version mismatch: this instance requires {CORE_VERSION_REQUIRED}, "
    f"core is {CORE_VERSION}. Update the instance or pin to the correct core."
)

# TODO: set the actual sample rate for this domain.
# This determines what expiry_samples means in real time:
#   expiry_samples = SAMPLE_RATE_HZ * expiry_seconds
# F1 ~10 Hz, tennis ~1 Hz, cycling varies by sensor.
SAMPLE_RATE_HZ = None  # declare before building run.py

CHANNELS = [
    # name        priority  cost   note
    ("Touch",      0,       None, "TODO: tune for this domain, or omit if no reflex"),
    ("Sound",      1,       None, "TODO"),
    ("Vision",     2,       None, "TODO"),
    ("Presence",   3,       None, "TODO"),
    ("Voice",      4,       None, "TODO"),
]

HAS_RECOVERY_WINDOW = None  # True/False — declare before tuning costs, see CONTRACT.md
HAS_MULTI_TIMESCALE_LOAD = None  # True/False — see CONTRACT.md
