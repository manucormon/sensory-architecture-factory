"""
Sensory Architecture — Channel Taxonomy

DECLARED CONVENTION, not a verified universal law: the bet this project
makes is that any human operating under load has these same five
channels available (Touch/Sound/Vision/Presence/Voice), regardless of
domain. What changes per domain is the tuned cost/priority — that
belongs in each instance's config.py, not here.

DEFAULT_CHANNELS below are the F1-tuned values, kept here only as a
sensible starting point to copy and retune for a new instance — not
as a universal constant. A new domain adapter should define its own
CHANNELS in its own config.py.

CORE_VERSION is the contract version for core/governance.py. Each
instance's config.py declares CORE_VERSION_REQUIRED = "X.Y" so that
a future breaking change to govern()'s signature is caught at import
time, not silently at runtime. Increment the minor version for
backwards-compatible additions; increment the major version for any
change that breaks existing instance adapters.
"""

CORE_VERSION = "1.0"

# name, priority (0 = admitted first), cost (0..1 attention consumed), note
DEFAULT_CHANNELS = [
    ("Touch",      0, 0.00, "reflex — bypasses the budget when triggered"),
    ("Sound",      1, 0.25, "directional, brief"),
    ("Vision",     2, 0.40, "glanceable, requires a look"),
    ("Presence",   3, 0.15, "ambient, near-subliminal"),
    ("Voice",      4, 0.70, "deliberative — most expensive, last admitted"),
]
