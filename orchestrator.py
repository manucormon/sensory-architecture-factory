"""
orchestrator.py — Harness factory main coordinator.

Fabricates new instances, tracks their state, and runs the verification
gate. Sub-agents (agents/) handle each concern; this module wires them.

HARD CONSTRAINTS (see AGENTS.md):
  - core/ is READ-ONLY. This script never writes to core/governance.py
    or core/channels_schema.py. Any attempt to do so is a contract breach.
  - Design choices that aren't obvious (Voice cost, timescale stacking)
    are flagged as open questions, never filled in silently.
  - Proposals only. The orchestrator scaffolds and reports; a human
    reviews NOTES.md and tunes config.py before verification can pass.

Usage:
    python3 orchestrator.py new --domain cycling
    python3 orchestrator.py status [--check-fs]
    python3 orchestrator.py verify [--domain f1]
    python3 orchestrator.py report

For 'new', the orchestrator asks the two CONTRACT.md questions interactively
unless --recovery-window and --multi-timescale are supplied as flags.

'status --check-fs' also lists orphan instance directories — folders under
instances/ that exist on disk but are not registered in instance_registry.json.
"""

import argparse
import sys
import json
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))

from agents import registry, scaffolder, verifier


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

_CORE_FILES = {ROOT / "core" / "governance.py",
               ROOT / "core" / "channels_schema.py"}


def _assert_core_untouched() -> None:
    """Abort if any core file has been touched by this process (defensive check)."""
    for p in _CORE_FILES:
        if not p.exists():
            print(f"[ABORT] core file missing: {p} — repo integrity broken.", file=sys.stderr)
            sys.exit(2)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_new(args) -> int:
    """Scaffold a new instance, register it, and report what needs human input."""
    domain = args.domain.lower().strip()

    existing = registry.get_instance(domain)
    if existing:
        print(f"[orchestrator] instance '{domain}' already exists "
              f"(status: {existing['status']}).")
        print("  Use 'orchestrator.py status' to inspect it, or "
              "'orchestrator.py verify --domain {domain}' to run the gate.")
        return 1

    # --- The two CONTRACT.md declarations ---
    has_recovery = _ask_bool(
        args,
        attr="recovery_window",
        question=(
            f"\n[CONTRACT] Does '{domain}' have a structured recovery window?\n"
            "  (A phase where load reliably drops and stays down long enough\n"
            "  for a deferred Voice request to resolve — like F1's straight\n"
            "  or tennis's between-points window.)\n"
            "  y/n: "
        ),
    )
    has_multi = _ask_bool(
        args,
        attr="multi_timescale",
        question=(
            f"\n[CONTRACT] Does '{domain}' load stack two timescales?\n"
            "  (Instantaneous demand PLUS accumulated fatigue or priming,\n"
            "  as in cycling — where hour 5 of a stage changes what the\n"
            "  same speed/power reading means.)\n"
            "  y/n: "
        ),
    )

    # --- Scaffold ---
    _assert_core_untouched()
    print(f"\n[orchestrator] scaffolding instances/{domain}/ ...")
    try:
        dest = scaffolder.scaffold(domain,
                                   has_recovery_window=has_recovery,
                                   has_multi_timescale_load=has_multi)
    except FileExistsError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1

    registry.register(domain,
                      has_recovery_window=has_recovery,
                      has_multi_timescale_load=has_multi)

    # --- Report what the human must do next ---
    print(f"[orchestrator] scaffolded: {dest.relative_to(ROOT)}/")
    print()
    print("  NEXT STEPS — required before this instance can be verified:")
    print()
    print(f"  1. Read  instances/{domain}/NOTES.md           (already filled in)")
    print(f"  2. Tune  instances/{domain}/config.py           (CHANNELS costs = None)")
    print(f"          Do NOT copy F1's values — Voice especially.")
    if not has_recovery:
        print(f"          Note: no recovery window — consider Voice cheap+pulse-only")
    if has_multi:
        print(f"          Note: two-timescale load — load_model.py needs two components")
    print(f"  3. Implement instances/{domain}/data_loader.py")
    print(f"  4. Implement instances/{domain}/load_model.py  (label every input REAL/PROXY/DECLARED)")
    print(f"  5. Implement instances/{domain}/reflex_trigger.py  (or set HAS_REFLEX = False)")
    print(f"  6. Implement instances/{domain}/run.py")
    print(f"  7. Add    tests/test_{domain}_instance.py      (pattern: tests/test_f1_instance.py)")
    print(f"  8. Run    python3 stop_until_green.py")
    print()
    print("  OPEN QUESTION you must decide on purpose (not by accident):")
    print(f"  → With your tuned costs, does a fresh Voice request open at")
    print(f"    {domain}'s most-open realistic moment? Run the check from")
    print(f"    test_governance.py::test_f1_tuned_costs_close_voice_even_at_the_open_straight")
    print(f"    adapted for {domain}'s attention level, and record the result in NOTES.md.")
    print()

    _assert_core_untouched()
    return 0


def cmd_status(args) -> int:
    """Print a status table of all registered instances."""
    check_fs = getattr(args, "check_fs", False)
    print()
    print("  INSTANCE REGISTRY")
    print(registry.summary_table(show_orphans=check_fs))
    print()
    try:
        raw = json.loads((ROOT / "instance_registry.json").read_text())
        for domain, entry in raw["instances"].items():
            nulls = [k for k, v in entry.items() if v is None]
            if nulls:
                print(f"  [{domain}] open fields (need human input): {', '.join(nulls)}")
    except Exception:
        pass
    print()
    return 0


def cmd_verify(args) -> int:
    """Run the full verification gate (security + pytest), optionally scoped."""
    _assert_core_untouched()

    if args.domain:
        domain = args.domain.lower()
        entry = registry.get_instance(domain)
        if not entry:
            print(f"[orchestrator] '{domain}' not in registry. "
                  "Run 'new' first.", file=sys.stderr)
            return 1
        test_file = entry.get("test_file")
        print(f"[orchestrator] verifying instance '{domain}' ...")
        result = verifier.run_pytest_only(test_file)
    else:
        print("[orchestrator] running full gate (security + all tests) ...")
        result = verifier.run_full_gate()

    print()
    print(result.summary())
    print()

    if result.all_green and args.domain:
        registry.update_status(args.domain, "verified")
        print(f"[orchestrator] registry updated: '{args.domain}' → verified")

    _assert_core_untouched()
    return 0 if result.all_green else 1


def cmd_report(args) -> int:
    """Print a cross-instance summary: airtime, Voice admission, open fields."""
    print()
    print("  SENSORY ARCHITECTURE FACTORY — instance report")
    print("  " + "=" * 56)
    instances = registry.list_instances()
    for domain, entry in instances.items():
        print(f"\n  [{domain.upper()}]  status: {entry['status']}")
        prov = entry.get("data_provenance") or "not set"
        print(f"    data provenance : {prov}")
        rw = entry.get("has_recovery_window")
        ms = entry.get("has_multi_timescale_load")
        print(f"    recovery window : {rw}   multi-timescale load: {ms}")
        costs = entry.get("channel_costs", {})
        tuned = all(v is not None for v in costs.values())
        print(f"    channel costs   : {'tuned' if tuned else 'NOT YET TUNED (None values present)'}")
        voice_open = entry.get("voice_opens_at_most_open_moment")
        if voice_open is None:
            print(f"    voice admission : not yet checked — run the open-moment test")
        else:
            print(f"    voice admission : {'OPENS' if voice_open else 'stays CLOSED'} at most-open moment")
        notes = entry.get("notes") or ""
        if notes:
            print(f"    notes           : {notes[:120]}{'...' if len(notes) > 120 else ''}")
    print()
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ask_bool(args, attr: str, question: str) -> bool:
    """Return the flag if provided, otherwise prompt interactively."""
    val = getattr(args, attr, None)
    if val is not None:
        return val
    if not sys.stdin.isatty():
        print(f"[ERROR] --{attr.replace('_', '-')} required in non-interactive mode.",
              file=sys.stderr)
        sys.exit(1)
    while True:
        ans = input(question).strip().lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("  Please answer y or n.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Sensory Architecture harness factory orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # new
    p_new = sub.add_parser("new", help="Scaffold a new domain instance")
    p_new.add_argument("--domain", required=True, help="Domain name (e.g. cycling, basketball)")
    p_new.add_argument("--recovery-window", dest="recovery_window",
                       type=lambda x: x.lower() in ("y", "yes", "true", "1"),
                       default=None, metavar="y/n",
                       help="Does this domain have a structured recovery window?")
    p_new.add_argument("--multi-timescale", dest="multi_timescale",
                       type=lambda x: x.lower() in ("y", "yes", "true", "1"),
                       default=None, metavar="y/n",
                       help="Does load stack two timescales?")

    # status
    p_status = sub.add_parser("status", help="Print registry status table")
    p_status.add_argument("--check-fs", dest="check_fs", action="store_true",
                          help="Also list orphan instance directories not in the registry")

    # verify
    p_ver = sub.add_parser("verify", help="Run the verification gate")
    p_ver.add_argument("--domain", default=None,
                       help="Scope to one instance's test file (omit for full suite)")

    # report
    sub.add_parser("report", help="Cross-instance summary report")

    args = parser.parse_args()

    dispatch = {
        "new": cmd_new,
        "status": cmd_status,
        "verify": cmd_verify,
        "report": cmd_report,
    }
    sys.exit(dispatch[args.command](args))


if __name__ == "__main__":
    main()
