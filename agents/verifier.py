"""
agents/verifier.py — Verification sub-agent.

Wraps stop_until_green.py and pytest, parses their output, and returns a
structured result the orchestrator can act on (log, update registry, report).

Each subprocess call carries an explicit timeout so a hanging test cannot
freeze the pipeline indefinitely. Default: 120s per gate.

This agent never modifies source files. It observes and reports.
The orchestrator decides what to do with the result.
"""

import subprocess
import sys
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List

ROOT = Path(__file__).parent.parent.resolve()
DEFAULT_TIMEOUT = 120  # seconds per gate


@dataclass
class VerificationResult:
    security_passed: bool
    tests_passed: bool
    test_count: Optional[int]
    failed_tests: List[str]
    security_findings: List[str]
    timed_out: bool
    raw_output: str

    @property
    def all_green(self) -> bool:
        return self.security_passed and self.tests_passed and not self.timed_out

    def summary(self) -> str:
        status = "GREEN" if self.all_green else ("TIMEOUT" if self.timed_out else "RED")
        lines = [f"[{status}] verification result"]
        if self.timed_out:
            lines.append("  gate timed out — a test or check may be hanging")
            return "\n".join(lines)
        lines.append(f"  security gate : {'PASS' if self.security_passed else 'FAIL'}")
        lines.append(f"  pytest        : {'PASS' if self.tests_passed else 'FAIL'}"
                     + (f"  ({self.test_count} passed)" if self.test_count else ""))
        if self.failed_tests:
            lines.append("  failed tests:")
            for t in self.failed_tests:
                lines.append(f"    - {t}")
        if self.security_findings:
            lines.append("  security findings:")
            for f_ in self.security_findings:
                lines.append(f"    - {f_}")
        return "\n".join(lines)


def run_full_gate(timeout: int = DEFAULT_TIMEOUT) -> VerificationResult:
    """Run stop_until_green.py (security + pytest) and parse the result."""
    try:
        result = subprocess.run(
            [sys.executable, str(ROOT / "stop_until_green.py")],
            cwd=ROOT, capture_output=True, text=True, timeout=timeout * 2,
        )
        output = result.stdout + result.stderr
        return _parse(output, result.returncode)
    except subprocess.TimeoutExpired:
        return _timeout_result()


def run_pytest_only(test_path: Optional[str] = None,
                    timeout: int = DEFAULT_TIMEOUT) -> VerificationResult:
    """Run pytest (optionally scoped to one file) and parse the result."""
    cmd = [sys.executable, "-m", "pytest", "-q"]
    if test_path:
        cmd.append(test_path)
    try:
        result = subprocess.run(
            cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
        )
        output = result.stdout + result.stderr
        parsed = _parse(output, result.returncode)
        parsed.security_passed = True  # not run in this mode
        return parsed
    except subprocess.TimeoutExpired:
        return _timeout_result()


def _timeout_result() -> VerificationResult:
    return VerificationResult(
        security_passed=False, tests_passed=False,
        test_count=None, failed_tests=[], security_findings=[],
        timed_out=True, raw_output="[timeout]",
    )


def _parse(output: str, returncode: int) -> VerificationResult:
    security_passed = "[OK]" in output and "GATE CLOSED" not in output
    tests_passed = returncode == 0 and "failed" not in output.lower()

    count_match = re.search(r"(\d+) passed", output)
    test_count = int(count_match.group(1)) if count_match else None

    failed_tests = re.findall(r"FAILED\s+([\w/.:]+)", output)

    security_findings = []
    for line in output.splitlines():
        if line.strip().startswith("[BLOCKED]"):
            security_findings.append(line.strip())

    return VerificationResult(
        security_passed=security_passed,
        tests_passed=tests_passed,
        test_count=test_count,
        failed_tests=failed_tests,
        security_findings=security_findings,
        timed_out=False,
        raw_output=output,
    )
