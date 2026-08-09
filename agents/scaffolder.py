"""
agents/scaffolder.py — New-instance scaffolding sub-agent.

Given a domain name and the two CONTRACT.md declarations, creates the
instances/<domain>/ directory structure by copying and specializing the
template. Generates files that:

  - Pass the labeling check (every load_model.py carries a DECLARED label).
  - Raise NotImplementedError for unimplemented functions — so a test added
    before implementation fails explicitly, not silently.
  - Mark all CHANNELS costs as None — config.py is flagged as needing tuning
    before stop_until_green.py can pass an instance test that calls govern().
  - Include a NOTES.md with the two declarations already filled in.

What this agent does NOT do:
  - Write any code in core/ (read-only by design).
  - Tune CHANNELS costs (design decision requiring domain knowledge).
  - Generate a test file (the contract says the human adds that after tuning).
  - Call stop_until_green.py (the orchestrator does that after scaffolding).
"""

import shutil
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
TEMPLATE_DIR = ROOT / "TEMPLATE_arnes_base" / "domain_adapter"
INSTANCES_DIR = ROOT / "instances"

# Files copied verbatim from the template (domain name substituted in docstrings)
TEMPLATE_FILES = ["data_loader.py", "load_model.py", "reflex_trigger.py", "config.py",
                  "perception.py"]


import re as _re

_SAFE_DOMAIN = _re.compile(r'^[a-z_][a-z0-9_]{0,63}$')


def scaffold(domain: str, *, has_recovery_window: bool,
             has_multi_timescale_load: bool) -> Path:
    """
    Create instances/<domain>/ from the template.

    Returns the path to the new instance directory.
    Raises ValueError if domain contains path-traversal characters.
    Raises FileExistsError if the directory already exists — the orchestrator
    checks the registry first, but this is the filesystem safety net.
    """
    if not _SAFE_DOMAIN.match(domain):
        raise ValueError(
            f"Invalid domain name '{domain}'. "
            "Use lowercase letters, digits, and underscores only (start with a letter)."
        )
    dest = INSTANCES_DIR / domain
    # Paranoia check: ensure resolved path stays under INSTANCES_DIR.
    if not str(dest.resolve()).startswith(str(INSTANCES_DIR.resolve())):
        raise ValueError(f"Domain name '{domain}' escapes the instances directory.")
    if dest.exists():
        raise FileExistsError(
            f"instances/{domain}/ already exists. "
            "Delete it manually if you want to re-scaffold."
        )
    dest.mkdir(parents=True)
    (dest / "data").mkdir()

    for fname in TEMPLATE_FILES:
        src = TEMPLATE_DIR / fname
        text = src.read_text(encoding="utf-8")
        text = text.replace("<DOMAIN>", domain.upper())
        (dest / fname).write_text(text, encoding="utf-8")

    _write_notes(dest, domain,
                 has_recovery_window=has_recovery_window,
                 has_multi_timescale_load=has_multi_timescale_load)
    _write_run_stub(dest, domain)

    return dest


def _write_notes(dest: Path, domain: str, *,
                 has_recovery_window: bool, has_multi_timescale_load: bool) -> None:
    recovery_text = (
        "True — describe the recovery window here (ruled or geographic?)."
        if has_recovery_window else
        "False — no reliable recovery window. The deferred queue may rarely resolve; "
        "the urgent pulse (Voice:pulse) becomes the dominant Voice mechanism."
    )
    timescale_text = (
        "True — load stacks two timescales (instantaneous + accumulated). "
        "load_model.py must return both components separately."
        if has_multi_timescale_load else
        "False — single-timescale load. One component in load_model.py is enough."
    )
    notes = f"""\
# NOTES — {domain} instance

Status: SCAFFOLDED. Not yet implemented or verified. Do not present as a
real product capability until status reaches 'verified' in instance_registry.json.

## Contract declarations (required before writing code — CONTRACT.md §5)

**HAS_RECOVERY_WINDOW = {has_recovery_window}.**
{recovery_text}

**HAS_MULTI_TIMESCALE_LOAD = {has_multi_timescale_load}.**
{timescale_text}

## Labeling discipline

Every number feeding the governance decision in load_model.py must be labeled:
  REAL     — actually measured
  PROXY    — stands in for something you don't have (say for what)
  DECLARED — a design convention, not a measurement

## Checklist before calling this instance done

See TEMPLATE_arnes_base/verification/checklist.md. In particular:
- Tune CHANNELS costs in config.py for THIS domain (do not copy F1's numbers unchecked).
- Implement perception.py: label every returned field MEASURED / TRACKED / PREDICTED.
  A thin passthrough (return input unchanged) is fine if there is no spatial state.
  Set HAS_PERCEPTION = True (real extraction) or False (passthrough/DECLARED).
- Run the Voice-admission check: does a fresh Voice request open at this domain's
  most-open realistic moment? Know the answer before shipping.
- Add tests/test_{domain}_instance.py and verify against a stored baseline.
- Run: python3 stop_until_green.py
"""
    (dest / "NOTES.md").write_text(notes, encoding="utf-8")


def _write_run_stub(dest: Path, domain: str) -> None:
    stub = f'''\
"""
{domain} instance — orchestration stub.

Fill in: wire data_loader + load_model + reflex_trigger + config into
core.governance, then produce output (console + CSV). See instances/f1/run.py
for the reference pattern.

Until this is implemented, importing this module will succeed but running it
will raise NotImplementedError from the unimplemented sub-modules.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

# TODO: implement the four imports below and wire them together.
# from core.governance import govern_series
# from instances.{domain}.data_loader import load
# from instances.{domain}.load_model import compute_load
# from instances.{domain}.reflex_trigger import reflex_series, HAS_REFLEX
# from instances.{domain}.config import CHANNELS

if __name__ == "__main__":
    raise NotImplementedError(
        "run.py: wire data_loader + load_model + reflex_trigger + config, "
        "then remove this raise. See instances/f1/run.py for the pattern."
    )
'''
    (dest / "run.py").write_text(stub, encoding="utf-8")


def teardown(domain: str) -> None:
    """Remove instances/<domain>/ entirely. Used in tests only."""
    dest = INSTANCES_DIR / domain
    if dest.exists():
        shutil.rmtree(dest)
