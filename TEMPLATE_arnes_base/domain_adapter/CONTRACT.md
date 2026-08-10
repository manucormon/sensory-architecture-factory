# Domain Adapter — Contract

To fabricate a new instance of the harness, a domain must supply four
things. This is the interface `core/governance.py` consumes — it knows
nothing else about your domain.

## 1. `data_loader.py`
Read your domain's raw signal (telemetry, sensor feed, video-derived
data, whatever exists) into whatever shape `load_model.py` needs.
F1 test reference: `instances/f1/data_loader.py` — reads one redistributable
DECLARED synthetic fixture and coerces its types. A production adapter must
load its own legally usable domain source; the fixture is not real telemetry.

## 2. `perception.py`
Sits between `data_loader.py` and `load_model.py` in the pipeline. Its
job is narrow: extract the spatial/relational state that load_model.py
needs — positions, distances, or trajectories of whatever objects matter
in this domain — without doing any load arithmetic itself.

Every field in the perceptual state must carry one of three labels:

  **MEASURED** — the value arrived pre-computed from an external system;
  nobody in this repo tracked anything. This label is appropriate only when
  the external system and its provenance are actually available. The bundled
  F1 fixture is synthetic, so its `DistanceToDriverAhead` is DECLARED and must
  not be cited as a MEASURED reference.

  **TRACKED** — the value was actively computed here, from raw sensor or
  video input, by code in this repo. As of this writing, no instance in
  the factory has a TRACKED field — building a real tracker is a
  separate, larger project. If your domain genuinely needs tracking,
  say so in NOTES.md and leave the field as a stub rather than faking
  MEASURED confidence for something you actually derived.

  **PREDICTED** — the value is extrapolated forward from tracked or
  measured state: where will the object be in N frames, not where is it
  now. Explicitly optional — most instances will not have this, and
  that is fine. Do not add prediction to fill a slot; add it only if
  the domain's load model or reflex trigger actually depends on it.

Do not blur MEASURED and TRACKED. They carry different confidence and
different failure modes: a MEASURED field fails when the external system
fails; a TRACKED field fails when the tracking algorithm fails. A
governance engine that treats them as equivalent is making a silent
confidence claim it has no right to make.

Not every domain has meaningful spatial state to extract. If yours
doesn't, `perception.py` may be a thin passthrough that returns the
raw samples unchanged — declare that plainly in the docstring rather
than inventing structure to fill the slot.

F1 test reference: `instances/f1/perception.py` — a thin passthrough that
reads synthetic `DistanceToDriverAhead` (DECLARED) from the fixture DataFrame.
No tracking, no prediction.

## 3. `load_model.py`
The honest core of the adapter: derive a `load` array (0..1) and its
complement `attention = 1 - load` from your domain's raw signal.
Label explicitly whether each input is REAL (measured), a PROXY
(stands in for something you don't have), or DECLARED (a design
convention). The bundled F1 scenario is DECLARED synthetic data and its load
model is a PROXY for cognitive demand. Never blur the three.

## 4. `reflex_trigger.py`
Define the one condition that bypasses the budget entirely, if your
domain has one. Not every domain needs this — declare `None` if it
doesn't, rather than forcing a fake trigger to fill the slot.

## 5. `config.py` — tuned, not copied
```python
CHANNELS = [
    # name, priority, cost, note — TUNE THESE. Do not reuse F1's
    # values unless you've checked they actually fit this domain.
    ("Touch",    0, ?, "..."),
    ("Sound",    1, ?, "..."),
    ("Vision",   2, ?, "..."),
    ("Presence", 3, ?, "..."),
    ("Voice",    4, ?, "..."),
]
```
Copying F1's numbers here is the single most likely way to quietly
smuggle F1's assumptions into a domain where they don't hold — see
the Voice-cost finding below.

## 6. Two declarations, in `NOTES.md`, before writing any code

**Does this domain have a structured recovery window?**
A phase where load reliably drops and stays down long enough for a
deferred Voice request to resolve. The synthetic F1 scenario declares one
(the straight, seconds long, repeats every lap). Tennis has one, explicit and ruled (20-25s
between points, 90s on changeovers) — some tennis formats even permit
verbal coaching precisely inside this window, matching Voice's role.
Base jumping likely has none — the event is seconds long and may stay
near peak load until landing, which means the deferred queue is close
to useless there and the urgent pulse becomes the dominant mechanism.
If your domain has no recovery window, say so — don't build a queue
that will never resolve.

**Is load single-timescale or does it stack?**
The synthetic F1 model declares a single, fast, moment-to-moment signal. Cycling adds a
second, slow layer on top: hours of accumulated fatigue that changes
what the same instantaneous signal means at hour 5 versus hour 1 of a
stage. If your domain has this, `load_model.py` needs two components,
not one — declare it, don't silently average it away.

## 7. Latency budget (Guardrail 8)

Every domain adapter must declare two latency figures in `NOTES.md`:

**`latency_ms`** — the maximum acceptable round-trip from signal
acquisition to governance decision, in milliseconds. Set this to match
your domain's reaction-time constraint, not to whatever the harness
happens to achieve today.  F1's tight real-time constraint (one lap ≈
90 s, intervention window ≈ seconds) requires low latency_ms; a 12-hour
dispatcher shift can tolerate higher values.  If you don't know the
right number, write your best guess and flag it as `DECLARED`.

**`dt_ahead`** — the planning lookahead: how many seconds in the future
the plan signal targets.  The cycling instance uses `dt_ahead = 30 s`
(next climb segment); F1 uses `dt_ahead = 0` (immediate guidance).
An adapter that leaves `dt_ahead` unstated is implicitly assuming
instant-only mode — make that assumption explicit rather than silent.

Governance output that exceeds `latency_ms` should be logged and
flagged, not silently dropped. Document what happens to a late decision
in your domain: is it discarded, queued, or still delivered?

## A finding worth re-checking for every new domain
Under the DECLARED synthetic F1 model's tuned costs, a FRESH Voice request (nothing queued) fails
to be admitted even at the most open moment in the whole lap (0.93
attention) — Sound+Vision+Presence consume the budget first by
priority order. That was a real result from testing `govern_hybrid()`,
not a design intent. Cycling suggests the opposite tuning entirely
(Voice cheap and constant, per the directeur sportif pattern). Re-run
this same check for every new instance — don't assume it either opens
or stays closed without testing it.
