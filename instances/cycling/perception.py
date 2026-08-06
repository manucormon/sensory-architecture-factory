"""
Cycling instance — perception layer.

Thin passthrough. The synthetic data generator in data_loader.py produces
phase, power_w, gradient_pct, and crash_signal directly. These are all
load_model.py and reflex_trigger.py need, and all are DECLARED — no real
sensor, no real peloton, no real road.

No MEASURED, TRACKED, or PREDICTED fields exist in this instance:
  - There is no external positioning system (no GPS stream, no race
    transponder delivering gap-to-rivals pre-computed).
  - There is no tracking algorithm — rival positions, peloton density,
    and crash detection are all DECLARED synthetic flags.
  - There is no trajectory prediction.

A real cycling instance with live race data could expose:
  - gap_to_rival_m: MEASURED (race transponder system, like FIA timing)
  - peloton_density: MEASURED (from race broadcast tracking, if available)
  - rival_attack_predicted: PREDICTED (from a power-spike tracker)
That would require a real data source and, for PREDICTED, a real model.
Neither exists here.
"""

HAS_PERCEPTION = False  # no spatial extraction needed — passthrough


def perceive(samples: list) -> list:
    """
    Return samples unchanged. All fields needed by load_model.py and
    reflex_trigger.py are already present in the DECLARED synthetic data.
    """
    return samples
