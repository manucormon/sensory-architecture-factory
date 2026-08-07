"""
ENMAX instance — perception layer.

HAS_PERCEPTION = False.

The synthetic data generator in data_loader.py produces all fields that
load_model.py and reflex_trigger.py need: active_incidents, queue_depth,
p1_active, crew_available, shift_elapsed_h.

There is no spatial extraction to perform:
  - There is no real incident map to parse for proximity or clustering.
  - There is no real CAD stream to classify incident types from raw text.
  - There is no real crew-location feed to derive response-time estimates.

A real ENMAX instance with live CAD data could expose:
  - incident_cluster_density: MEASURED (geographic clustering of open tickets)
  - crew_eta_min: MEASURED (dispatch system ETA from GPS + routing)
  - incident_escalation_risk: PREDICTED (from historical escalation patterns)
That would require a live CAD integration — the data_loader.py slot is exactly
where that connection would be made.

For now, all fields are DECLARED — passthrough is the honest implementation.
"""

HAS_PERCEPTION = False


def perceive(samples: list) -> list:
    """
    Return samples unchanged. All fields needed by load_model.py and
    reflex_trigger.py are already present in the DECLARED synthetic data.
    """
    return samples   # DECLARED — no spatial extraction performed
