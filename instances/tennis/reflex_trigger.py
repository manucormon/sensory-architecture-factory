"""
Tennis instance — reflex trigger.

The serve, and an occasional mid-rally smash/volley: ball arriving
faster than deliberate reasoning allows, needs a reflex return
regardless of the attention budget — same role Touch plays in F1's
hard-braking/wheel-to-wheel moments.
"""

HAS_REFLEX = True


def reflex_series(samples):
    return [s["reflex_event"] for s in samples]
