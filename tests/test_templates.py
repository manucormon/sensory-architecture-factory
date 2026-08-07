"""
Template sanity check: the empty domain_adapter templates must import
cleanly (no syntax errors) even though their functions raise
NotImplementedError by design — a broken template blocks every future
instance, not just one.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def test_template_modules_import_cleanly():
    import TEMPLATE_arnes_base.domain_adapter.data_loader  # noqa: F401
    import TEMPLATE_arnes_base.domain_adapter.load_model    # noqa: F401
    import TEMPLATE_arnes_base.domain_adapter.reflex_trigger as rt
    import TEMPLATE_arnes_base.domain_adapter.config as cfg

    assert rt.HAS_REFLEX is None  # must be set explicitly per new instance
    assert cfg.HAS_RECOVERY_WINDOW is None
    assert cfg.HAS_MULTI_TIMESCALE_LOAD is None


def test_template_perception_imports_cleanly():
    import TEMPLATE_arnes_base.domain_adapter.perception as perc

    assert perc.HAS_PERCEPTION is None  # must be declared per new instance


def test_template_perception_raises_not_implemented():
    import TEMPLATE_arnes_base.domain_adapter.perception as perc
    import pytest

    with pytest.raises(NotImplementedError):
        perc.perceive()


def test_f1_perception_is_measured_passthrough():
    """F1 perception must expose HAS_PERCEPTION=True and accept the telemetry DataFrame."""
    import instances.f1.perception as f1p
    import instances.f1.data_loader as f1d

    assert f1p.HAS_PERCEPTION is True
    df = f1d.load("VER")
    result = f1p.perceive(df)
    # Returns the same DataFrame — no new columns added, no rows dropped
    assert result is df or list(result.columns) == list(df.columns)
    assert "DistanceToDriverAhead" in result.columns


def test_tennis_perception_is_declared_passthrough():
    """Tennis perception must expose HAS_PERCEPTION=False and return samples unchanged."""
    import instances.tennis.perception as tp
    import instances.tennis.data_loader as td

    assert tp.HAS_PERCEPTION is False
    samples = td.load()
    result = tp.perceive(samples)
    assert result is samples  # strict identity — nothing was copied or modified


def test_cycling_perception_is_measured():
    """Cycling now uses real GPS data — HAS_PERCEPTION=True (gradient is MEASURED)."""
    import instances.cycling.perception as cp
    import instances.cycling.data_loader as cd

    assert cp.HAS_PERCEPTION is True
    df = cd.load()
    result = cp.perceive(df)
    assert result is df
    assert "gradient_pct" in result.columns
    assert "phase" in result.columns
