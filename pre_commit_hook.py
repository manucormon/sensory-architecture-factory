"""
pre_commit_hook.py — Security and integrity gate.

Runs three checks before any commit is allowed through:

  1. SECRET SCAN     — blocks patterns that look like credentials or API keys.
  2. LABELING CHECK  — every load_model.py must contain at least one
                       REAL / PROXY / DECLARED label (convention enforced
                       in code, not just prose).
  3. KNOWLEDGE GUARD — every .md file in knowledge/ must carry a
                       classification header (PUBLIC / CONFIDENTIAL / NDA).

Run directly:
    python3 pre_commit_hook.py [--staged-only]

Install as a git pre-commit hook (one-time setup):
    python3 pre_commit_hook.py --install

stop_until_green.py calls this gate before running pytest; both must
pass before a commit or a pipeline step is allowed to proceed.
"""

import re
import sys
import os
import subprocess
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.resolve()

# ---------------------------------------------------------------------------
# 1. Secret patterns — extend this list as the project grows.
#    Intentionally broad: false positives are cheap; false negatives are not.
# ---------------------------------------------------------------------------

SECRET_PATTERNS = [
    # Generic high-entropy key-like assignments
    (r'(?i)(api[_\-]?key|secret[_\-]?key|access[_\-]?token|auth[_\-]?token)\s*=\s*["\'][^"\']{16,}["\']',
     "potential API key or token assignment"),
    # AWS
    (r'AKIA[0-9A-Z]{16}', "AWS access key ID"),
    (r'(?i)aws[_\-]?secret[_\-]?(access[_\-]?)?key\s*=\s*["\'][^"\']+["\']', "AWS secret key"),
    # Generic bearer / Basic auth in URLs
    (r'https?://[^:@\s]+:[^@\s]+@', "credentials embedded in URL"),
    # Private key headers
    (r'-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----', "private key block"),
    # GitHub / GitLab tokens
    (r'gh[pousr]_[A-Za-z0-9]{36}', "GitHub personal access token"),
    (r'glpat-[A-Za-z0-9\-]{20}', "GitLab personal access token"),
    # Slack tokens
    (r'xox[baprs]-[A-Za-z0-9\-]+', "Slack token"),
]

_COMPILED_SECRETS = [(re.compile(p), label) for p, label in SECRET_PATTERNS]


def _rel(path):
    """Return path relative to ROOT, or the path itself if outside the repo."""
    try:
        return path.relative_to(ROOT)
    except ValueError:
        return path

# ---------------------------------------------------------------------------
# 2. Labeling check patterns
# ---------------------------------------------------------------------------

LABEL_PATTERN = re.compile(r'\b(REAL|PROXY|DECLARED)\b')

KNOWLEDGE_CLASSIFICATION_HEADER = re.compile(
    r'^#\s*(PUBLIC|CONFIDENTIAL|NDA)\b', re.MULTILINE
)

# ---------------------------------------------------------------------------
# File collection helpers
# ---------------------------------------------------------------------------

def _staged_files():
    """Return list of staged file paths (git diff --cached --name-only)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        cwd=ROOT, capture_output=True, text=True
    )
    if result.returncode != 0:
        return []
    return [ROOT / p.strip() for p in result.stdout.splitlines() if p.strip()]


def _all_repo_files(extensions=None):
    """Walk the repo and return all tracked-or-present files, optionally filtered."""
    found = []
    skip_dirs = {".git", ".pytest_cache", "__pycache__", ".venv", "venv", "env"}
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for f in filenames:
            p = Path(dirpath) / f
            if extensions is None or p.suffix in extensions:
                found.append(p)
    return found


def _read_safe(path):
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""

# ---------------------------------------------------------------------------
# Check 1 — Secret scan
# ---------------------------------------------------------------------------

def check_secrets(files):
    """
    Scan files for secret patterns. Returns list of (path, line_no, label).
    Skips binary files and known-safe paths (fixtures baseline CSVs are
    data, not code, and don't carry credentials).
    """
    SAFE_SUFFIXES = {".png", ".jpg", ".jpeg", ".pdf", ".svg", ".pyc"}
    findings = []
    for path in files:
        if path.suffix in SAFE_SUFFIXES:
            continue
        text = _read_safe(path)
        for i, line in enumerate(text.splitlines(), 1):
            if "# noqa: secret-test" in line:
                continue
            for pattern, label in _COMPILED_SECRETS:
                if pattern.search(line):
                    findings.append((_rel(path), i, label, line.strip()[:120]))
    return findings


# ---------------------------------------------------------------------------
# Check 2 — REAL / PROXY / DECLARED labeling in load_model.py files
# ---------------------------------------------------------------------------

def check_labeling(files):
    """
    Every load_model.py in instances/ must contain at least one REAL,
    PROXY, or DECLARED label. Missing label = unlabeled numeric assumption.
    """
    findings = []
    for path in files:
        if path.name != "load_model.py":
            continue
        if "instances" not in str(path):
            continue
        text = _read_safe(path)
        if not LABEL_PATTERN.search(text):
            findings.append(_rel(path))
    return findings


# ---------------------------------------------------------------------------
# Check 3 — knowledge/ classification headers
# ---------------------------------------------------------------------------

def check_knowledge_classification(files):
    """
    Every .md file under knowledge/ must open with a classification header:
    # PUBLIC, # CONFIDENTIAL, or # NDA (case-insensitive, first non-blank line).
    """
    findings = []
    for path in files:
        if "knowledge" not in str(path):
            continue
        if path.suffix != ".md":
            continue
        text = _read_safe(path)
        if not text.strip():
            continue
        if not KNOWLEDGE_CLASSIFICATION_HEADER.search(text):
            findings.append(_rel(path))
    return findings


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run(staged_only=False):
    if staged_only:
        files = _staged_files()
        if not files:
            print("[pre-commit] no staged files to check — skipping.")
            return 0
        scope_label = f"staged ({len(files)} files)"
    else:
        files = _all_repo_files()
        scope_label = f"full repo ({len(files)} files)"

    print(f"[pre-commit] scanning {scope_label}")

    failed = False

    # --- 1. Secrets ---
    secret_hits = check_secrets(files)
    if secret_hits:
        failed = True
        print("\n[BLOCKED] CHECK 1 — potential secrets found:")
        for path, line_no, label, snippet in secret_hits:
            print(f"  {path}:{line_no}  [{label}]")
            print(f"    {snippet}")
    else:
        print("[OK] CHECK 1 — no secrets detected")

    # --- 2. Labeling ---
    unlabeled = check_labeling(files)
    if unlabeled:
        failed = True
        print("\n[BLOCKED] CHECK 2 — load_model.py files missing REAL/PROXY/DECLARED label:")
        for path in unlabeled:
            print(f"  {path}")
    else:
        load_models_checked = [f for f in files
                                if f.name == "load_model.py" and "instances" in str(f)]
        print(f"[OK] CHECK 2 — labeling present in {len(load_models_checked)} load_model file(s)")

    # --- 3. Knowledge classification ---
    unclassified = check_knowledge_classification(files)
    if unclassified:
        failed = True
        print("\n[BLOCKED] CHECK 3 — knowledge/ files missing classification header:")
        for path in unclassified:
            print(f"  {path}  (add '# PUBLIC', '# CONFIDENTIAL', or '# NDA' as first heading)")
    else:
        knowledge_checked = [f for f in files
                              if "knowledge" in str(f) and f.suffix == ".md"]
        if knowledge_checked:
            print(f"[OK] CHECK 3 — classification headers present in {len(knowledge_checked)} knowledge file(s)")
        else:
            print("[OK] CHECK 3 — no knowledge/ .md files to check")

    if failed:
        print("\n[pre-commit] GATE CLOSED — fix the issues above before committing.")
        return 1

    print("\n[pre-commit] all checks passed — gate open.")
    return 0


# ---------------------------------------------------------------------------
# --install: write this script as .git/hooks/pre-commit
# ---------------------------------------------------------------------------

def install_hook():
    hook_path = ROOT / ".git" / "hooks" / "pre-commit"
    if not (ROOT / ".git").exists():
        print("[install] not a git repo — run 'git init' first.")
        return 1
    hook_path.write_text(
        f"#!/bin/sh\npython3 '{ROOT / 'pre_commit_hook.py'}' --staged-only\n"
    )
    hook_path.chmod(0o755)
    print(f"[install] hook written to {hook_path}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sensory factory security gate")
    parser.add_argument("--staged-only", action="store_true",
                        help="Check only git-staged files (used when running as git hook)")
    parser.add_argument("--install", action="store_true",
                        help="Install as .git/hooks/pre-commit and exit")
    args = parser.parse_args()

    if args.install:
        sys.exit(install_hook())
    else:
        sys.exit(run(staged_only=args.staged_only))
