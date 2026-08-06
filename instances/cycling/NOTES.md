# NOTES — cycling instance

Status: SCAFFOLDED. Not yet implemented or verified. Do not present as a
real product capability until status reaches 'verified' in instance_registry.json.

## Contract declarations (required before writing code — CONTRACT.md §5)

**HAS_RECOVERY_WINDOW = True.**
True — describe the recovery window here (ruled or geographic?).

**HAS_MULTI_TIMESCALE_LOAD = True.**
True — load stacks two timescales (instantaneous + accumulated). load_model.py must return both components separately.

## Labeling discipline

Every number feeding the governance decision in load_model.py must be labeled:
  REAL     — actually measured
  PROXY    — stands in for something you don't have (say for what)
  DECLARED — a design convention, not a measurement

## Checklist before calling this instance done

See TEMPLATE_arnes_base/verification/checklist.md. In particular:
- Tune CHANNELS costs in config.py for THIS domain (do not copy F1's numbers unchecked).
- Run the Voice-admission check: does a fresh Voice request open at this domain's
  most-open realistic moment? Know the answer before shipping.
- Add tests/test_cycling_instance.py and verify against a stored baseline.
- Run: python3 stop_until_green.py
