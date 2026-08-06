"""
Core governance tests. Same checks run ad hoc in chat during steps 1-2;
now permanent so `pytest` is one real command, not something to retype.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.governance import govern, govern_hybrid, VoiceQueue

CH = [
    ("Touch", 0, 0.00, ""),
    ("Sound", 1, 0.25, ""),
    ("Vision", 2, 0.40, ""),
    ("Presence", 3, 0.15, ""),
    ("Voice", 4, 0.70, ""),
]


def test_govern_basic_admits_by_priority_until_budget_runs_out():
    active = govern(CH, budget=1.0, reflex_active=False)
    assert active == ["Sound", "Vision", "Presence"]


def test_govern_reflex_bypasses_budget():
    active = govern(CH, budget=0.0, reflex_active=True)
    assert active == ["Touch"]


def test_hybrid_no_request_voice_stays_silent():
    out = govern_hybrid(CH, budget=1.0, reflex_active=False)
    assert "Voice" not in out and "Voice:pulse" not in out


def test_hybrid_urgent_pulse_bypasses_budget():
    out = govern_hybrid(CH, budget=0.0, reflex_active=False,
                         voice_requested=True, risk_present=True)
    assert "Voice:pulse" in out


def test_hybrid_blocked_request_gets_queued_not_lost():
    q = VoiceQueue(expiry_samples=5)
    out = govern_hybrid(CH, budget=0.1, reflex_active=False,
                         voice_requested=True, risk_present=False, queue=q, i=0)
    assert "Voice" not in out
    assert q.waiting == 1


def test_hybrid_pending_request_outranks_fresh_grant_on_reopen():
    q = VoiceQueue(expiry_samples=5)
    govern_hybrid(CH, budget=0.1, reflex_active=False,
                  voice_requested=True, risk_present=False, queue=q, i=0)
    out = govern_hybrid(CH, budget=1.0, reflex_active=False,
                         voice_requested=False, risk_present=False, queue=q, i=1)
    assert "Voice" in out
    assert q.waiting == 0


def test_hybrid_stale_request_expires_instead_of_arriving_late():
    q = VoiceQueue(expiry_samples=2)
    govern_hybrid(CH, budget=0.1, reflex_active=False,
                  voice_requested=True, risk_present=False, queue=q, i=0)
    assert q.waiting == 1
    out = govern_hybrid(CH, budget=1.0, reflex_active=False,
                         voice_requested=False, risk_present=False, queue=q, i=10)
    assert "Voice" not in out
    assert q.waiting == 0


def test_f1_tuned_costs_close_voice_even_at_the_open_straight():
    """
    Documents the real finding from step 2: with F1's tuned costs, a
    FRESH ask (nothing queued) is not admitted even at the straight's
    actual attention level (0.93) — Sound+Vision+Presence eat the
    budget first. Not a bug; a fact about these specific numbers.
    If this ever flips, it means the F1 config changed — worth noticing.
    """
    out = govern_hybrid(CH, budget=0.93, reflex_active=False,
                         voice_requested=True, risk_present=False)
    assert "Voice" not in out
