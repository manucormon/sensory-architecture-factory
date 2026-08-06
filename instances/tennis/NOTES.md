# NOTES — tennis instance (hypothetical, step 4)

Status: HYPOTHETICAL. No real telemetry, no real biometrics. This
instance exists to test whether the domain_adapter contract actually
generalizes to a domain shaped very differently from F1 — specifically
to stress-test the deferred-queue mechanism from step 2, which almost
never engages under F1's tuned costs. Do not present this as a real
product capability; it's an architecture test.

## Contract declarations (required before writing code)

**HAS_RECOVERY_WINDOW = True.**
Unlike F1's straight (a track-geography accident, however reliable),
tennis has a RULED recovery window: ~20-25s between points (shot
clock) and ~90s at every changeover (odd games). Some formats
explicitly permit verbal coaching inside exactly this window — the
sport already treats it as the place where the query channel belongs.
This is the domain chosen specifically because it should make the
queue from core/governance.py resolve in practice, unlike F1.

**HAS_MULTI_TIMESCALE_LOAD = False, deliberately, for this version.**
A real multi-hour match has an accumulated-fatigue dimension (closer
to cycling than to F1). This hypothetical isolates ONE new variable
at a time — the recovery-window question — and declares fatigue out
of scope here on purpose, not by oversight. A fuller tennis instance
would need to revisit this.

## Labeling discipline

Every number in load_model.py/data_loader.py here is DECLARED —
invented for illustration, informed by real published match structure
(point/changeover timing) but not measured from any real player. This
is the opposite labeling from F1, where load itself was a PROXY for
real telemetry. Neither is fabricated-and-hidden; both are labeled.
