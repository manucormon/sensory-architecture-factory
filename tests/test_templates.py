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
