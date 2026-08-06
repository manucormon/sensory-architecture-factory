"""
<DOMAIN> instance — perception layer.

Sits between data_loader.py and load_model.py. Its job is narrow:
extract the spatial/relational state that load_model.py needs —
positions, distances, or trajectories of whatever objects matter in
this domain.

Every field in the returned perceptual state must be labeled:
  MEASURED  — arrived pre-computed from an external system (e.g. FIA
              timing, Hawkeye, an existing sensor pipeline). Nobody in
              this repo tracked anything; the external system did.
  TRACKED   — actively computed here from raw sensor or video input.
              Not present in any instance as of this writing — building
              a real tracker is a separate, larger project.
  PREDICTED — extrapolated forward from tracked/measured state.
              Explicitly optional; omit if load_model.py doesn't use it.

Do NOT blur MEASURED and TRACKED. They carry different confidence and
different failure modes. See CONTRACT.md §2 for the full explanation.

If this domain has no meaningful spatial state to extract, this file
may be a thin passthrough — declare that plainly here rather than
inventing structure to fill the slot.

Delete this docstring block when done and replace with domain-specific
documentation.
"""

HAS_PERCEPTION = None  # set True (spatial state extracted) or False (passthrough)


def perceive(*args, **kwargs):
    raise NotImplementedError(
        "perceive(): extract the perceptual state for this domain, "
        "or set HAS_PERCEPTION = False and return the raw samples unchanged."
    )
