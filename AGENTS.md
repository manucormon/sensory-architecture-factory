# AGENTS.md — Sensory Architecture Factory

Read this first, before anything else in this repo. Full detail lives
in TEMPLATE_arnes_base/domain_adapter/CONTRACT.md — this file is the
short version, kept under 200 lines on purpose.

## What this is

A factory for attention-governance instances ("harnesses"). `core/`
is the mold — domain-agnostic, decides which of five sensory channels
(Touch/Sound/Vision/Presence/Voice) reach a human under load. Each
domain (F1, and whatever comes next) is one fabricated piece under
`instances/`, built by filling in the contract in `domain_adapter/`.

## Repo map

```
core/governance.py          govern(), govern_hybrid(), VoiceQueue — never edit
                             per-instance; changes here affect every piece.
core/channels_schema.py     the 5-channel taxonomy + CORE_VERSION — declared
                             convention. Instances pin CORE_VERSION_REQUIRED in
                             their config.py to catch breaking changes early.

instances/<domain>/         one fabricated piece per domain.
  data_loader.py             reads this domain's raw signal.
  load_model.py               derives load (0..1) from it — label every
                               input REAL / PROXY / DECLARED.
  reflex_trigger.py           the budget-bypass condition, or none.
  config.py                   THIS domain's tuned CHANNELS + SAMPLE_RATE_HZ
                               + CORE_VERSION_REQUIRED — never copy another
                               instance's numbers unchecked.
  run.py / visualize.py       orchestration + reporting, instance-specific.

TEMPLATE_arnes_base/        empty scaffold for a new instance.
  domain_adapter/CONTRACT.md  the full interface spec — read before
                               writing any code for a new domain.
  verification/checklist.md   what "done" means for a new instance.

orchestrator.py             factory coordinator — 4 commands:
                             new / status [--check-fs] / verify / report
agents/
  registry.py               instance registry CRUD (atomic writes)
  scaffolder.py             creates instances/<domain>/ from template
  verifier.py               runs the gate, returns structured result
instance_registry.json      source of truth: status, provenance, open fields.

pre_commit_hook.py          3 checks: secret scan, labeling, knowledge headers.
stop_until_green.py         pipeline gate: security + pytest, with timeouts.
                             Install as git hook: python3 pre_commit_hook.py --install

tests/                      pytest suite.
  fixtures/ver_governed_baseline.csv  hand-verified F1 baseline (SHA-256 pinned
                             in test_f1_instance.py — update deliberately).
knowledge/                  reference lineage (Norman, Baumrind, James, RPD...).
                             Every .md here requires a classification header:
                             # PUBLIC, # CONFIDENTIAL, or # NDA.
```

## Fabricating a new instance

Use the orchestrator — it handles steps 1-3 and tracks state:

```
python3 orchestrator.py new --domain <name>
```

The orchestrator asks the two CONTRACT.md questions, scaffolds
`instances/<name>/`, and registers the instance. Then, manually:

4. Tune `config.py`: set CHANNELS costs, SAMPLE_RATE_HZ, confirm
   CORE_VERSION_REQUIRED. Do not reuse F1's costs without checking —
   Voice alone has shown opposite tunings across domains.
5. Implement `data_loader.py`, `load_model.py` (label every input
   REAL / PROXY / DECLARED), `reflex_trigger.py`, `run.py`.
6. Add `tests/test_<domain>_instance.py` (pattern: test_f1_instance.py).
7. Run `python3 stop_until_green.py`. Don't call it done until it passes.

## Non-negotiable rules

- Never invent a metric or fact. Label every load input REAL, PROXY,
  or DECLARED — never blur the three.
- Mechanical migrations must be verified numerically against a stored
  baseline (np.allclose), never eyeballed. The baseline's SHA-256 is
  pinned in the test — update it deliberately if behavior must change.
- A new instance's CHANNELS costs are a design decision to justify,
  not a default to inherit.
- SAMPLE_RATE_HZ must be declared in every config.py. VoiceQueue
  expiry should be expressed in seconds and converted at runtime:
    expiry_samples = SAMPLE_RATE_HZ * expiry_seconds
- Conversation with the user is in Spanish; code, comments, and
  deliverables are in English.

## Periodic review protocol

No automatic trigger — an agent does not wake itself. The protocol
runs when a human requests a "validity review" (or a real scheduler
invokes it — infrastructure not yet built). Hybrid by design: the
agent runs the review, but any actual change to core/ or a config.py
is proposed, reviewed, and verified by a human before it's applied.
An agent silently rewriting its own governance core is the same class
of failure as the OpenAI/Hugging Face incident studied in this project.

When triggered, the agent must:
1. Search for substantially more capable AI models or tools since the
   last review (search, don't assume).
2. Re-check whether the five-channel taxonomy and each instance's tuned
   costs still hold against `knowledge/academic_lineage.md`, or whether
   new research questions them.
3. Run `pytest -q`. A regression here matters regardless of what
   triggered the review.
4. Check whether anything labeled DECLARED in a NOTES.md could now be
   upgraded to REAL/PROXY (real data appeared), or downgraded.
5. Write findings to `knowledge/review_<date>.md`. Never edit core/ or
   a config.py as part of this step — a finding is a recommendation,
   not a self-applied change.

## Verification commands

Run before ending any session that touched core/, an instance, or a template:

```
python3 stop_until_green.py
```

Or scoped to a specific instance:

```
python3 orchestrator.py verify --domain f1
```

If core/governance.py changed, tests/test_governance.py must still pass
unmodified. If an instance's run.py changed, its test must still pass
against its pinned baseline — if behavior was meant to change, update
the baseline deliberately and document it in the commit message.

## Conversational mode

When asked to add a new instance or extend core/, follow the order
above: read CONTRACT.md, declare the two open questions, tune before
building, verify before calling it done. When a design choice isn't
obvious (like Voice's cost or SAMPLE_RATE_HZ), say so explicitly and
ask rather than picking a value quietly.
