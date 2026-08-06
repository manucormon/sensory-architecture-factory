# Domain Adapter — Contract

To fabricate a new instance of the harness, a domain must supply four
things. This is the interface `core/governance.py` consumes — it knows
nothing else about your domain.

## 1. `data_loader.py`
Read your domain's raw signal (telemetry, sensor feed, video-derived
data, whatever exists) into whatever shape `load_model.py` needs.
F1 reference: `instances/f1/data_loader.py` — reads two CSVs, coerces
types. Yours will look nothing like this; that's expected.

## 2. `load_model.py`
The honest core of the adapter: derive a `load` array (0..1) and its
complement `attention = 1 - load` from your domain's raw signal.
Label explicitly whether each input is REAL (measured), a PROXY
(stands in for something you don't have), or DECLARED (a design
convention) — same discipline as F1's telemetry-as-proxy-for-biometrics
note. Never blur the three.

## 3. `reflex_trigger.py`
Define the one condition that bypasses the budget entirely, if your
domain has one. Not every domain needs this — declare `None` if it
doesn't, rather than forcing a fake trigger to fill the slot.

## 4. `config.py` — tuned, not copied
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

## 5. Two declarations, in `NOTES.md`, before writing any code

**Does this domain have a structured recovery window?**
A phase where load reliably drops and stays down long enough for a
deferred Voice request to resolve. F1 has one (the straight, seconds
long, repeats every lap). Tennis has one, explicit and ruled (20-25s
between points, 90s on changeovers) — some tennis formats even permit
verbal coaching precisely inside this window, matching Voice's role.
Base jumping likely has none — the event is seconds long and may stay
near peak load until landing, which means the deferred queue is close
to useless there and the urgent pulse becomes the dominant mechanism.
If your domain has no recovery window, say so — don't build a queue
that will never resolve.

**Is load single-timescale or does it stack?**
F1's load is a single, fast, moment-to-moment signal. Cycling adds a
second, slow layer on top: hours of accumulated fatigue that changes
what the same instantaneous signal means at hour 5 versus hour 1 of a
stage. If your domain has this, `load_model.py` needs two components,
not one — declare it, don't silently average it away.

## A finding worth re-checking for every new domain
Under F1's tuned costs, a FRESH Voice request (nothing queued) fails
to be admitted even at the most open moment in the whole lap (0.93
attention) — Sound+Vision+Presence consume the budget first by
priority order. That was a real result from testing `govern_hybrid()`,
not a design intent. Cycling suggests the opposite tuning entirely
(Voice cheap and constant, per the directeur sportif pattern). Re-run
this same check for every new instance — don't assume it either opens
or stays closed without testing it.
