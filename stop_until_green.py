"""
stop_until_green.py — Pipeline gate: stop until everything is green.

Runs in sequence:
  1. pre_commit_hook.py  — security + labeling + knowledge classification
  2. pytest -q           — full test suite

Both must pass. If either fails, the process exits non-zero, blocking
whatever called it (a commit, a CI step, an orchestrator hand-off).

Each gate has an independent timeout (default 120s) so a hanging test
cannot freeze the pipeline indefinitely.

Usage:
    python3 stop_until_green.py               # run both gates
    python3 stop_until_green.py --security    # security checks only
    python3 stop_until_green.py --tests       # pytest only
    python3 stop_until_green.py --staged-only # security on staged files only
    python3 stop_until_green.py --timeout 60  # override per-gate timeout (seconds)
"""

import sys
import subprocess
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DEFAULT_TIMEOUT = 120  # seconds per gate


def _run(cmd, label, timeout):
    """Run a command, stream output, return exit code. Blocks on timeout."""
    print(f"\n{'='*64}")
    print(f"  {label}")
    print(f"{'='*64}")
    try:
        result = subprocess.run(cmd, cwd=ROOT, timeout=timeout)
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"\n[TIMEOUT] gate did not finish within {timeout}s — treating as failure.")
        return 1


def gate_security(staged_only=False, timeout=DEFAULT_TIMEOUT):
    cmd = [sys.executable, str(ROOT / "pre_commit_hook.py")]
    if staged_only:
        cmd.append("--staged-only")
    return _run(cmd, "GATE 1 / 2 — security + labeling checks", timeout)


def gate_tests(timeout=DEFAULT_TIMEOUT):
    return _run([sys.executable, "-m", "pytest", "-q"], "GATE 2 / 2 — pytest suite", timeout)


def main():
    parser = argparse.ArgumentParser(
        description="Stop until both security and test gates are green."
    )
    parser.add_argument("--security", action="store_true",
                        help="Run security gate only (skip pytest)")
    parser.add_argument("--tests", action="store_true",
                        help="Run pytest only (skip security gate)")
    parser.add_argument("--staged-only", action="store_true",
                        help="Pass --staged-only to the security check")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"Per-gate timeout in seconds (default: {DEFAULT_TIMEOUT})")
    args = parser.parse_args()

    run_security = not args.tests
    run_tests = not args.security

    results = []

    if run_security:
        results.append(("security", gate_security(staged_only=args.staged_only,
                                                   timeout=args.timeout)))
    if run_tests:
        results.append(("pytest", gate_tests(timeout=args.timeout)))

    print(f"\n{'='*64}")
    all_green = all(code == 0 for _, code in results)
    for label, code in results:
        status = "PASS" if code == 0 else "FAIL"
        print(f"  [{status}] {label}")

    if all_green:
        print("\n  GREEN — pipeline may proceed.")
        print(f"{'='*64}\n")
        sys.exit(0)
    else:
        print("\n  RED — pipeline blocked. Fix the failures above.")
        print(f"{'='*64}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
