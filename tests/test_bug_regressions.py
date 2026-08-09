"""
Regression tests for 7 concrete bugs fixed in August 2026.
Each test is named after the bug it prevents from recurring.

These tests are narrow and targeted — they prove the specific failure
mode cannot reappear, not that the feature works in general.
"""

import random
import sys
import numpy as np
import pandas as pd
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from core.governance import govern_explain, VoiceQueue
from agents.observer import Observer
from agents.scaffolder import scaffold, teardown
from instances.cycling.load_model import compute_load as cycling_load
from instances.enmax.data_loader import load as enmax_load


# ---------------------------------------------------------------------------
# BUG 1 — Cycling load model: convolve edge artifacts on batches 2-4 samples
# ---------------------------------------------------------------------------

def test_cycling_load_batch_2_returns_two_outputs():
    """Batch of 2 must return arrays of length 2 — no divide-by-5 edge artifact."""
    df = pd.DataFrame([
        {"power_w": 200.0, "gradient_pct": 3.0, "phase": "climb"},
        {"power_w": 250.0, "gradient_pct": 3.0, "phase": "climb"},
    ])
    instant, fatigue, load, attention = cycling_load(df, ftp_w=250.0)
    assert len(instant) == 2
    assert len(load) == 2
    assert all(0 <= v <= 1 for v in instant), "Instant load out of [0,1] on batch of 2"


def test_cycling_load_batch_4_returns_four_outputs():
    """Batch of 4 must return arrays of length 4."""
    df = pd.DataFrame([
        {"power_w": 200.0, "gradient_pct": 0.0, "phase": "flat"}
        for _ in range(4)
    ])
    instant, fatigue, load, attention = cycling_load(df, ftp_w=250.0)
    assert len(instant) == 4


def test_cycling_load_no_jump_between_4_and_5():
    """No discontinuous jump in instant_load when going from 4→5 samples."""
    row = {"power_w": 200.0, "gradient_pct": 0.0, "phase": "flat"}
    df4 = pd.DataFrame([row] * 4)
    df5 = pd.DataFrame([row] * 5)
    i4, *_ = cycling_load(df4, ftp_w=250.0)
    i5, *_ = cycling_load(df5, ftp_w=250.0)
    # At steady state (all same power) the last value of 4-sample and
    # 5-sample should agree to 3 decimal places.
    assert abs(float(i4[-1]) - float(i5[-1])) < 1e-3, (
        f"Discontinuity between len-4 ({i4[-1]:.4f}) and len-5 ({i5[-1]:.4f})"
    )


# ---------------------------------------------------------------------------
# BUG 2 — govern_explain(): budget_remaining wrong when Voice admitted
# ---------------------------------------------------------------------------

def test_govern_explain_budget_remaining_after_voice_admission():
    """budget_remaining must subtract Voice cost when Voice is admitted."""
    channels = [
        ("Touch",    10, 0.00, "reflex"),
        ("Sound",     8, 0.15, "audio"),
        ("Voice",     1, 0.20, "query"),
    ]
    # High budget → Sound and Voice should both be admitted
    active, trace = govern_explain(
        channels, budget=0.90, reflex_active=False,
        voice_requested=True,
    )
    if "Voice" in active:
        # budget_remaining must account for Voice cost
        assert trace["budget_remaining"] <= 0.90 - 0.20 + 1e-9, (
            f"Voice cost not subtracted from budget_remaining: {trace['budget_remaining']}"
        )


# ---------------------------------------------------------------------------
# BUG 3 — Observer: FATIGUE_CEILING fires one sample early
# ---------------------------------------------------------------------------

def test_observer_fatigue_ceiling_fires_at_correct_sample():
    """Alert sample_index must be the FIRST sample at or above the ceiling."""
    n = 20
    # fatigue crosses 0.50 at index 10 (0.0*10 + 0.05*10 = 0.5)
    fatigue = np.array([0.04 * i for i in range(n)], dtype=float)
    # find where it first crosses 0.50
    expected = next(i for i in range(n) if fatigue[i] >= 0.50)

    load      = np.ones(n) * 0.4
    attention = np.ones(n) * 0.6
    obs = Observer(fatigue_ceiling=0.50)
    alerts = obs.scan(load, attention, fatigue=fatigue)
    fat_alerts = [a for a in alerts if a.alert_type == "FATIGUE_CEILING"]

    assert len(fat_alerts) == 1
    assert fat_alerts[0].sample_index == expected, (
        f"Expected alert at sample {expected}, got {fat_alerts[0].sample_index}"
    )
    assert fat_alerts[0].fatigue >= 0.50, "Alert fired before fatigue reached ceiling"


def test_observer_zero_window_raises():
    """window_s=0 must raise ValueError, not produce index -1."""
    with pytest.raises(ValueError, match="window_s"):
        Observer(sustained_load_window_s=0)
    with pytest.raises(ValueError, match="window_s"):
        Observer(attention_floor_window_s=0.0)
    with pytest.raises(ValueError, match="window_s"):
        Observer(recovery_window_s=0)


# ---------------------------------------------------------------------------
# BUG 4 — ENMAX data_loader: not reproducible on second call in same process
# ---------------------------------------------------------------------------

def test_enmax_load_reproducible_on_second_call():
    """Two calls to load() in the same process must return identical results."""
    s1 = enmax_load()
    s2 = enmax_load()
    assert len(s1) == len(s2)
    for a, b in zip(s1[:100], s2[:100]):   # compare first 100 samples
        assert a == b, f"Call 2 differs from call 1 at t={a['time_s']}: {a} vs {b}"


def test_enmax_load_different_seeds_differ():
    """Different seeds must produce different sequences."""
    s42 = enmax_load(seed=42)
    s99 = enmax_load(seed=99)
    first_diff = next(
        (i for i, (a, b) in enumerate(zip(s42, s99)) if a != b), None
    )
    assert first_diff is not None, "Different seeds produced identical output"


# ---------------------------------------------------------------------------
# BUG 6 — Scaffolder: domain name path traversal vulnerability
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("evil", ["../evil", "../../etc/passwd", "/absolute", "a/b"])
def test_scaffolder_rejects_path_traversal(evil):
    """Dangerous domain names must raise ValueError, not create files."""
    with pytest.raises(ValueError):
        scaffold(evil, has_recovery_window=True, has_multi_timescale_load=True)


def test_scaffolder_accepts_valid_domain():
    """A valid domain name scaffolds and tears down cleanly."""
    domain = "_test_regression_tmp"
    try:
        scaffold(domain, has_recovery_window=True, has_multi_timescale_load=True)
    finally:
        teardown(domain)


# ---------------------------------------------------------------------------
# BUG 5 — orchestrator verify --domain skips security (tested via verifier import)
# BUG 7 — cycling API endpoint fatigue must come from client, not fabricated
# These require the full API stack; covered in test_api.py integration tests.
# ---------------------------------------------------------------------------
