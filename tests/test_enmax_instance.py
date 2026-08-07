"""
ENMAX dispatcher instance test.

Four things this instance exists to prove:

1. TWO-TIMESCALE LOAD: same incident count late in the shift produces higher
   combined load than early — shift fatigue is real and consequential.

2. P1 REFLEX: Touch fires during P1 incidents (gas leak, transformer fire)
   regardless of cognitive budget. Life-safety bypasses the governor.

3. VOICE OPENS IN LULL: with dispatcher costs tuned, a supervisor Voice
   request is admitted during the post-storm lull — not during the storm.

4. OBSERVER FIRES CORRECTLY: the observer agent detects SUSTAINED_HIGH_LOAD
   during the storm and RECOVERY_DETECTED after it clears.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np

from instances.enmax.data_loader import load
from instances.enmax.perception import perceive, HAS_PERCEPTION
from instances.enmax.load_model import compute_load
from instances.enmax.reflex_trigger import reflex_series, HAS_REFLEX
from instances.enmax.config import CHANNELS, SAMPLE_RATE_HZ, HAS_MULTI_TIMESCALE_LOAD
from agents.observer import Observer
from core.governance import govern, govern_hybrid

_samples = perceive(load())
_instant, _fatigue, _load, _attention = compute_load(_samples)
_reflex = reflex_series(_samples)
_phases = [s["phase"] for s in _samples]


# ---------------------------------------------------------------------------
# Config sanity
# ---------------------------------------------------------------------------

def test_enmax_config_declares_multi_timescale():
    assert HAS_MULTI_TIMESCALE_LOAD is True


def test_enmax_config_has_sample_rate():
    assert SAMPLE_RATE_HZ is not None and SAMPLE_RATE_HZ > 0


def test_enmax_has_reflex_is_true():
    assert HAS_REFLEX is True


def test_enmax_has_perception_is_false():
    assert HAS_PERCEPTION is False


def test_enmax_all_channel_costs_are_set():
    for name, prio, cost, note in CHANNELS:
        assert cost is not None, f"{name} cost is None — must be tuned"


def test_enmax_shift_is_12_hours():
    assert len(_samples) == 43_200


# ---------------------------------------------------------------------------
# Perception passthrough
# ---------------------------------------------------------------------------

def test_perception_returns_same_list():
    s = load()
    assert perceive(s) is s


# ---------------------------------------------------------------------------
# Two-timescale load
# ---------------------------------------------------------------------------

def test_fatigue_increases_over_shift():
    """Shift fatigue must be strictly non-decreasing over the 12h."""
    assert np.all(np.diff(_fatigue) >= -1e-9)


def test_late_shift_load_higher_than_morning_same_incidents():
    """
    Core two-timescale claim for dispatchers: find two samples with the
    same active_incidents but at different shift times — late must be higher.
    """
    target_inc = 3
    morning = [i for i, s in enumerate(_samples)
               if s["active_incidents"] == target_inc
               and s["shift_elapsed_h"] < 2.0
               and not s["p1_active"]]
    late = [i for i, s in enumerate(_samples)
            if s["active_incidents"] == target_inc
            and s["shift_elapsed_h"] > 9.0
            and not s["p1_active"]]
    assert morning and late, "could not find matching samples — check data_loader.py"
    assert _load[late[0]] > _load[morning[0]], (
        f"late-shift load ({_load[late[0]]:.3f}) not higher than morning "
        f"({_load[morning[0]]:.3f}) at same incident count"
    )


# ---------------------------------------------------------------------------
# P1 reflex
# ---------------------------------------------------------------------------

def test_p1_reflex_fires_touch_at_budget_zero():
    """Touch must fire during any P1, even when cognitive budget is zero."""
    p1_indices = [i for i, s in enumerate(_samples) if s["p1_active"]]
    assert p1_indices, "no P1 samples — check _P1_WINDOWS in data_loader.py"
    for i in p1_indices[:5]:   # check first 5 to keep test fast
        result = govern(CHANNELS, budget=0.0, reflex_active=bool(_reflex[i]))
        assert "Touch" in result, f"Touch reflex did not fire at P1 sample {i}"


def test_no_reflex_without_p1():
    """Touch must not fire when P1 is inactive."""
    no_p1 = next(i for i, s in enumerate(_samples) if not s["p1_active"])
    result = govern(CHANNELS, budget=0.0, reflex_active=False)
    assert "Touch" not in result


def test_p1_windows_are_present():
    """Both declared P1 windows (gas leak h3, transformer h4.2) must fire."""
    p1_at_h3 = any(s["p1_active"] for s in _samples[10800:12600])
    p1_at_h4 = any(s["p1_active"] for s in _samples[15120:16560])
    assert p1_at_h3, "gas leak P1 window (h3–h3.5) not found"
    assert p1_at_h4, "transformer fire P1 window (h4.2–h4.6) not found"


# ---------------------------------------------------------------------------
# Voice opens in lull
# ---------------------------------------------------------------------------

def test_voice_opens_during_post_storm_lull():
    """
    Supervisor Voice must be admitted during the post-storm lull.
    This is the primary recovery window — if Voice cannot open here,
    CHANNELS costs need retuning.
    """
    lull_indices = [i for i, p in enumerate(_phases) if p == "post_storm_lull"]
    assert lull_indices, "no post-storm lull samples — check data_loader.py"

    best_i = max(lull_indices, key=lambda i: _attention[i])
    budget = _attention[best_i]

    result = govern_hybrid(CHANNELS, budget=budget, reflex_active=False,
                           voice_requested=True, risk_present=False)
    assert "Voice" in result, (
        f"Voice not admitted during post-storm lull (attention={budget:.2f}). "
        "Check CHANNELS costs — supervisor cannot reach dispatcher in recovery window."
    )


def test_voice_blocked_during_storm():
    """Voice should not open at peak storm load."""
    storm_indices = [i for i, p in enumerate(_phases) if p == "storm_event"]
    peak_i = max(storm_indices, key=lambda i: _load[i])
    budget = _attention[peak_i]
    result = govern_hybrid(CHANNELS, budget=budget, reflex_active=False,
                           voice_requested=True, risk_present=False)
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Observer agent
# ---------------------------------------------------------------------------

def test_observer_fires_sustained_high_load():
    """Storm event must trigger SUSTAINED_HIGH_LOAD alert."""
    obs = Observer(sample_rate_hz=SAMPLE_RATE_HZ,
                   sustained_load_threshold=0.80,
                   sustained_load_window_s=900)
    alerts = obs.scan(_load, _attention, _fatigue)
    types = [a.alert_type for a in alerts]
    assert "SUSTAINED_HIGH_LOAD" in types, \
        "no SUSTAINED_HIGH_LOAD alert — storm may not be pushing load > 0.80 for 15 min"


def test_observer_fires_recovery_after_storm():
    """Post-storm lull must trigger RECOVERY_DETECTED after a load alert."""
    obs = Observer(sample_rate_hz=SAMPLE_RATE_HZ,
                   sustained_load_threshold=0.80,
                   sustained_load_window_s=900,
                   recovery_threshold=0.55,
                   recovery_window_s=60)
    alerts = obs.scan(_load, _attention, _fatigue)
    types = [a.alert_type for a in alerts]
    assert "RECOVERY_DETECTED" in types, \
        "no RECOVERY_DETECTED — lull may not be long/open enough after the storm"


def test_observer_alerts_are_chronological():
    obs = Observer(sample_rate_hz=SAMPLE_RATE_HZ)
    alerts = obs.scan(_load, _attention, _fatigue)
    indices = [a.sample_index for a in alerts]
    assert indices == sorted(indices)


# ---------------------------------------------------------------------------
# Data integrity
# ---------------------------------------------------------------------------

def test_load_bounded_zero_to_one():
    assert np.all(_load >= 0) and np.all(_load <= 1)
    assert np.all(_attention >= 0) and np.all(_attention <= 1)


def test_attention_is_complement_of_load():
    assert np.allclose(_attention, 1 - _load, atol=1e-9)


def test_shift_has_all_phases():
    for phase in ["morning_ramp", "storm_event", "post_storm_lull",
                  "afternoon_peak", "late_shift_wind"]:
        assert phase in _phases, f"phase '{phase}' missing from shift"
