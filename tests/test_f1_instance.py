"""
F1 instance regression test. Runs the instance and compares the output
to the baseline that was hand-verified against the original
governance_engine.py during the step-1 migration (np.allclose, exact
match on every channel column). If this ever fails, something changed
behavior — investigate before trusting the new output.
"""

import hashlib
import os
import subprocess
import sys

import numpy as np
import pandas as pd

FACTORY = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BASELINE = os.path.join(os.path.dirname(__file__), "fixtures", "ver_governed_baseline.csv")

# SHA-256 of the hand-verified baseline. If this changes, someone deliberately
# replaced the baseline — the test forces that to be a conscious act, not an
# accident. To update after an intentional baseline change:
#   shasum -a 256 tests/fixtures/ver_governed_baseline.csv
# then paste the new digest here and document why in the commit message.
BASELINE_SHA256 = "19c96196cd8e3e663d44459208f83a8d430706104372ba052631cf41248099fa"


def test_baseline_file_is_unmodified():
    """
    Guard against accidental baseline replacement. If this fails, the baseline
    CSV was changed — verify the new output is correct, then update BASELINE_SHA256
    in this file deliberately and document the reason in the commit message.
    """
    digest = hashlib.sha256(open(BASELINE, "rb").read()).hexdigest()
    assert digest == BASELINE_SHA256, (
        f"Baseline checksum mismatch.\n"
        f"  stored : {BASELINE_SHA256}\n"
        f"  on disk: {digest}\n"
        "If the change is intentional, update BASELINE_SHA256 in this file "
        "and document why in the commit message."
    )


def test_f1_run_produces_output_matching_verified_baseline():
    result = subprocess.run(
        [sys.executable, os.path.join(FACTORY, "instances", "f1", "run.py")],
        cwd=FACTORY, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "THE CORNER" in result.stdout and "THE STRAIGHT" in result.stdout

    new = pd.read_csv(os.path.join(FACTORY, "instances", "f1", "ver_governed.csv"))
    baseline = pd.read_csv(BASELINE)

    assert new.shape == baseline.shape

    for col in ["load", "attention"]:
        assert np.allclose(new[col].to_numpy(), baseline[col].to_numpy(),
                            atol=1e-9, equal_nan=True), f"{col} drifted from baseline"

    for ch in ["Touch", "Sound", "Vision", "Presence", "Voice"]:
        assert (new[ch].astype(str).to_numpy() == baseline[ch].astype(str).to_numpy()).all(), \
            f"{ch} activation drifted from baseline"


def test_f1_visualize_runs_without_error():
    result = subprocess.run(
        [sys.executable, os.path.join(FACTORY, "instances", "f1", "visualize.py")],
        cwd=FACTORY, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert os.path.exists(os.path.join(FACTORY, "instances", "f1", "fig1_track_load.png"))
    assert os.path.exists(os.path.join(FACTORY, "instances", "f1", "fig2_channels.png"))
