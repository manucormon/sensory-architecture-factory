"""
<DOMAIN> instance — cognitive-load proxy.

Fill in: derive `load` (0..1) and `attention = 1 - load` from this
domain's raw signal. For every input, label it explicitly:
  REAL     — actually measured
  PROXY    — stands in for something you don't have (say for what)
  DECLARED — a design convention, not a measurement
Never blur the three. See CONTRACT.md before writing this.

If load stacks two timescales (e.g. instantaneous demand + accumulated
fatigue, as flagged for cycling), return both components separately —
don't silently average them into one number.
"""

from core.governance import norm  # noqa: F401  (reuse, don't reimplement)


def compute_load(*args, **kwargs):
    raise NotImplementedError("compute_load(): derive load/attention here")
