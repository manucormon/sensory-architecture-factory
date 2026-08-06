"""
Tennis instance test. The one thing this hypothetical exists to prove:
a voice_requested that's blocked mid-point resolves once the recovery
window opens — unlike F1, where a fresh request stayed blocked even
at the most open moment measured (see
test_governance.py::test_f1_tuned_costs_close_voice_even_at_the_open_straight).
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from instances.tennis.run import (
    samples, active_sets, request_i, resolved_i, attention,
)


def test_voice_request_mid_point_is_not_admitted_immediately():
    assert "Voice" not in active_sets[request_i]
    assert samples[request_i]["phase"] == "point"


def test_voice_request_resolves_once_recovery_window_opens():
    assert resolved_i is not None, "request never resolved — contract failed its own test"
    assert samples[resolved_i]["phase"] in ("between_points", "changeover")
    assert attention[resolved_i] > attention[request_i]


def test_voice_resolves_reasonably_soon_after_the_point_ends():
    # Not an arbitrary number: the point this request was made in should
    # end within a few samples (rally lengths are 4-12s), so resolution
    # should follow shortly, not sit queued for the whole session.
    assert 0 < (resolved_i - request_i) <= 15
