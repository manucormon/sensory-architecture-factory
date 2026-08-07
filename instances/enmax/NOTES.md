# NOTES — ENMAX instance

Status: SCAFFOLDED+IMPLEMENTED. Not yet formally verified. Do not present as a
real product capability until status reaches 'verified' in instance_registry.json.

## Contract declarations (CONTRACT.md §5)

**HAS_RECOVERY_WINDOW = True.**
Both ruled and event-based. Ruled: shift handoff at 8h is a hard break.
Event-based: storm clearance causes sharp incident volume drop — natural
lull before the next event cluster. Dispatcher in the lull has cognitive
budget. This is the primary window for supervisor Voice contact.

**HAS_MULTI_TIMESCALE_LOAD = True.**
Timescale 1 (instant): active incident count + queue depth + P1 flag.
Timescale 2 (accumulated): 12-hour shift fatigue, amplified by storm
intensity. Same incident count at hour 10 produces higher combined load
than at hour 2 — the two-timescale divergence is real and consequential
for dispatcher wellbeing and decision quality.

## Labeling discipline

All data is DECLARED — synthetic, generated to match realistic ENMAX shift
patterns. No real CAD (Computer-Aided Dispatch) data behind this.

Data upgrade path: `data_loader.py` is the slot where a real CAD integration
(or MCP connection to ENMAX's dispatch system) would plug in. When that
happens, labels will upgrade to REAL/PROXY as appropriate.

## Key findings to verify before shipping

- Voice opens during post-storm lull (attention should be > 0.55): ✓ (verify)
- Touch fires during all P1 windows regardless of load: ✓ (verify)
- Two-timescale divergence: same incident count, higher load late in shift: ✓ (verify)
- Observer agent fires SUSTAINED_HIGH_LOAD during storm event: ✓ (verify)
- Observer agent fires RECOVERY_DETECTED after storm clears: ✓ (verify)

## Observer integration

This instance is the first to wire the observer agent (agents/observer.py).
run.py passes the full shift arrays to Observer.scan() after governance.
The observer's output is what a supervisor dashboard or on-call system would
receive — not the channel decisions (those are private to the dispatcher),
but the load telemetry (load/attention/fatigue over time).

## Data upgrade path

When ENMAX integrates real CAD data:
1. Replace data_loader.py with a CAD stream reader.
2. Update perception.py: HAS_PERCEPTION = True, extract incident_cluster_density
   (MEASURED from geo-clustering) and crew_eta_min (MEASURED from routing).
3. Re-label: active_incidents = REAL, queue_depth = REAL, p1_active = REAL.
4. Re-verify channel costs against real incident distributions.
5. Update instance_registry.json: status → 'verified', data_provenance → 'REAL'.
"""
