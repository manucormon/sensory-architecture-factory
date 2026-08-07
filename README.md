# Sensory Architecture Factory

An attention-governance engine for humans under pressure. Decides which of five
sensory channels (Touch / Sound / Vision / Presence / Voice) should reach a person
at any given moment, given their current cognitive load.

Built as a proving ground for high-stakes human factors: motorsport telemetry today,
risk-critical professional environments tomorrow.

---

## What it does

A governance core (`core/`) applies a priority + cost model to five channels.
Each domain — F1, cycling, tennis — is a fabricated instance (`instances/`) that
plugs real or synthetic data into the core. The factory scaffolds new instances,
verifies them, and tracks their status.

```
core/             govern(), govern_series(), govern_hybrid(), VoiceQueue
instances/        one fabricated instance per domain
agents/           orchestration sub-agents (registry, scaffolder, verifier)
TEMPLATE_arnes_base/  empty scaffold + contract spec for new instances
tests/            pytest suite (68 tests, all passing)
```

---

## Fabricating a new instance

```bash
python3 orchestrator.py new --domain <name>
```

The orchestrator asks two contract questions, scaffolds `instances/<name>/`, and
registers the instance. Then fill in the five implementation files, tune channel
costs, add tests, and run the gate:

```bash
python3 stop_until_green.py
```

Full spec: [`TEMPLATE_arnes_base/domain_adapter/CONTRACT.md`](TEMPLATE_arnes_base/domain_adapter/CONTRACT.md)

---

## Current instances

| Domain   | Status      | Data provenance | Voice opens? |
|----------|-------------|-----------------|--------------|
| F1       | verified    | PROXY (telemetry) | No — budget consumed by other channels |
| Cycling  | verified    | DECLARED (synthetic) | Yes — on descent |
| Tennis   | hypothetical | DECLARED (synthetic) | Yes |

---

## Running the test suite

```bash
pytest -q
```

Or scoped to one instance:

```bash
python3 orchestrator.py verify --domain cycling
```

---

## Non-negotiable rules

- Every load input is labeled **REAL / PROXY / DECLARED** — never blur the three.
- Every perception field is labeled **MEASURED / TRACKED / PREDICTED**.
- Mechanical changes are verified numerically against a pinned baseline (SHA-256).
- Channel costs are a design decision per domain — never copy another domain's numbers unchecked.
- Code, comments, and filenames are in English.

---

## Pipeline gate (pre-commit hook)

```bash
python3 pre_commit_hook.py --install
```

Three checks: secret scan (8 patterns), labeling discipline, knowledge/ classification
headers. Blocks the commit if any check fails.

---

For full architecture details, read [`AGENTS.md`](AGENTS.md).
