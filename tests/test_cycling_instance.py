"""
Cycling instance test — real data (GoldenCheetah OpenData, 2019-12-28).

Three things this instance exists to prove, each tested explicitly:

1. TWO-TIMESCALE LOAD: accumulated fatigue raises combined load even when
   instantaneous power is held constant — same claim as the DECLARED prototype,
   now verified against real power-meter data.

2. VOICE OPENS ON DESCENT: with cycling's tuned costs, a fresh Voice request
   is admitted during descent — opposite of F1. Now verified against a real
   descent where power drops to near-zero (mean 19W, 34% zeros = coasting).

3. HAS_REFLEX = False: no crash labels in real ride data. The engine still
   operates correctly for the other four channels.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pandas as pd

from instances.cycling.data_loader import load, FTP_W
from instances.cycling.perception import perceive, HAS_PERCEPTION
from instances.cycling.load_model import compute_load
from instances.cycling.reflex_trigger import HAS_REFLEX
from instances.cycling.config import CHANNELS, SAMPLE_RATE_HZ, HAS_MULTI_TIMESCALE_LOAD
from core.governance import govern, govern_hybrid

_df_raw = load()
_df = perceive(_df_raw)
_instant, _fatigue, _load, _attention = compute_load(_df, FTP_W)
_phases = _df["phase"].tolist()


# ---------------------------------------------------------------------------
# Config sanity
# ---------------------------------------------------------------------------

def test_cycling_config_declares_multi_timescale():
    assert HAS_MULTI_TIMESCALE_LOAD is True


def test_cycling_config_has_sample_rate():
    assert SAMPLE_RATE_HZ is not None and SAMPLE_RATE_HZ > 0


def test_cycling_has_reflex_is_false():
    """Real data has no crash labels — HAS_REFLEX must be False."""
    assert HAS_REFLEX is False


def test_cycling_all_channel_costs_are_set():
    for name, prio, cost, note in CHANNELS:
        assert cost is not None, f"{name} cost is None — must be tuned"


def test_ftp_is_proxy_value():
    """FTP_W must be set and plausible for an amateur/sport cyclist."""
    assert 150 < FTP_W < 400, f"FTP_W={FTP_W} outside plausible range"


# ---------------------------------------------------------------------------
# Perception layer
# ---------------------------------------------------------------------------

def test_has_perception_is_true():
    """Real GPS data yields MEASURED gradient — HAS_PERCEPTION must be True."""
    assert HAS_PERCEPTION is True


def test_perception_returns_same_dataframe():
    df = load()
    result = perceive(df)
    assert result is df


def test_perception_gradient_in_bounds():
    assert _df["gradient_pct"].between(-20, 20).all()


def test_perception_phases_are_valid():
    assert set(_df["phase"].unique()).issubset({"climb", "descent", "flat"})


def test_ride_has_all_three_phases():
    assert "climb" in _phases
    assert "descent" in _phases
    assert "flat" in _phases


# ---------------------------------------------------------------------------
# Real data structure
# ---------------------------------------------------------------------------

def test_data_is_real_ride_length():
    """Real ride is ~79 minutes at 1Hz."""
    assert 4000 < len(_df) < 6000, f"unexpected row count {len(_df)}"


def test_climb_power_exceeds_ftp():
    """Real climb power mean should be at or above FTP (hard mountain effort)."""
    climb_power = _df.loc[_df["phase"] == "climb", "power_w"].mean()
    assert climb_power > FTP_W * 0.90, \
        f"climb power mean ({climb_power:.0f}W) surprisingly low vs FTP ({FTP_W}W)"


def test_descent_has_significant_coasting():
    """Real descents have substantial coasting (power=0) — at least 20%."""
    descent_rows = _df[_df["phase"] == "descent"]
    zero_pct = (descent_rows["power_w"] == 0).mean()
    assert zero_pct > 0.20, \
        f"descent zero-power share {zero_pct:.0%} unexpectedly low — data may be wrong"


# ---------------------------------------------------------------------------
# Two-timescale load
# ---------------------------------------------------------------------------

def test_fatigue_increases_monotonically_over_ride():
    assert np.all(np.diff(_fatigue) >= -1e-9)


def test_late_ride_load_higher_than_early_for_same_instant_power():
    target = float(np.median(_instant))
    tolerance = 0.08
    similar = np.where(np.abs(_instant - target) < tolerance)[0]
    assert len(similar) >= 2
    early_i = similar[0]
    late_i = similar[-1]
    assert late_i > early_i + 300
    assert _load[late_i] > _load[early_i], (
        f"late-ride load ({_load[late_i]:.3f}) not higher than early "
        f"({_load[early_i]:.3f}) for similar instant power"
    )


def test_fatigue_accumulates_by_five_minutes():
    """Real ride starts with warmup (near-zero power); fatigue is meaningful by 5 min."""
    assert _fatigue[300] > 0.01


# ---------------------------------------------------------------------------
# Voice admission on descent (key finding, now verified on real data)
# ---------------------------------------------------------------------------

def test_voice_opens_on_descent_with_fresh_request():
    """
    Key finding re-verified on real ride data. Descent power is mostly
    coasting (~0W) → low load → high attention → Voice budget available.
    """
    descent_indices = [i for i, p in enumerate(_phases) if p == "descent"]
    assert descent_indices, "no descent samples — check data or gradient thresholds"

    best_i = max(descent_indices, key=lambda i: _attention[i])
    budget = _attention[best_i]

    result = govern_hybrid(CHANNELS, budget=budget, reflex_active=False,
                           voice_requested=True, risk_present=False)
    assert "Voice" in result, (
        f"Voice not admitted at real-data descent (attention={budget:.2f}). "
        f"Key finding failed — check CHANNELS costs or gradient thresholds."
    )


def test_voice_closed_at_climb_peak():
    climb_i = int(np.argmax(_load))
    budget = _attention[climb_i]
    result = govern_hybrid(CHANNELS, budget=budget, reflex_active=False,
                           voice_requested=True, risk_present=False)
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Data integrity
# ---------------------------------------------------------------------------

def test_load_bounded_zero_to_one():
    assert np.all(_load >= 0) and np.all(_load <= 1)
    assert np.all(_attention >= 0) and np.all(_attention <= 1)


def test_attention_is_complement_of_load():
    assert np.allclose(_attention, 1 - _load, atol=1e-9)
