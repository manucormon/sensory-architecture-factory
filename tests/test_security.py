"""
Security gate tests — verify pre_commit_hook.py catches real violations
and passes clean files.
"""

import sys
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from pre_commit_hook import (
    check_secrets,
    check_labeling,
    check_knowledge_classification,
)


def _tmp_file(content, suffix=".py"):
    """Write content to a temp file; caller owns cleanup."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=suffix,
                                    delete=False, encoding="utf-8")
    f.write(content)
    f.close()
    return Path(f.name)


# ---------------------------------------------------------------------------
# Check 1 — secrets
# ---------------------------------------------------------------------------

def test_secret_scan_catches_api_key():
    p = _tmp_file('API_KEY = "sk-abcdefghijklmnopqrstuvwx"\n')  # noqa: secret-test
    try:
        hits = check_secrets([p])
        assert hits, "expected a secret hit, got none"
    finally:
        p.unlink()


def test_secret_scan_catches_private_key_header():
    p = _tmp_file("-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n")  # noqa: secret-test
    try:
        hits = check_secrets([p])
        assert hits
    finally:
        p.unlink()


def test_secret_scan_passes_clean_file():
    p = _tmp_file('BUDGET = 0.93\nCOST = 0.25\n')
    try:
        hits = check_secrets([p])
        assert not hits, f"false positive: {hits}"
    finally:
        p.unlink()


# ---------------------------------------------------------------------------
# Check 2 — REAL / PROXY / DECLARED labeling in load_model.py
# ---------------------------------------------------------------------------

def test_labeling_catches_unlabeled_load_model():
    # Simulate a file inside instances/ with no label
    with tempfile.TemporaryDirectory() as d:
        fake_instances = Path(d) / "instances" / "demo"
        fake_instances.mkdir(parents=True)
        p = fake_instances / "load_model.py"
        p.write_text("def compute_load(df):\n    return df['x'] * 0.5\n")
        findings = check_labeling([p])
        assert findings, "expected unlabeled finding"


def test_labeling_passes_labeled_load_model():
    with tempfile.TemporaryDirectory() as d:
        fake_instances = Path(d) / "instances" / "demo"
        fake_instances.mkdir(parents=True)
        p = fake_instances / "load_model.py"
        p.write_text("# PROXY: speed as load stand-in\ndef compute_load(df):\n    return df['x']\n")
        findings = check_labeling([p])
        assert not findings, f"false positive: {findings}"


def test_labeling_ignores_non_instance_load_model():
    # A load_model.py at the root is not an instance file — should not be checked
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "load_model.py"
        p.write_text("def compute_load(): pass\n")
        findings = check_labeling([p])
        assert not findings


# ---------------------------------------------------------------------------
# Check 3 — knowledge/ classification headers
# ---------------------------------------------------------------------------

def test_knowledge_guard_catches_unclassified_md():
    with tempfile.TemporaryDirectory() as d:
        kdir = Path(d) / "knowledge"
        kdir.mkdir()
        p = kdir / "notes.md"
        p.write_text("# Some notes\nThis document has no classification.\n")
        findings = check_knowledge_classification([p])
        assert findings, "expected unclassified finding"


def test_knowledge_guard_passes_classified_md():
    with tempfile.TemporaryDirectory() as d:
        kdir = Path(d) / "knowledge"
        kdir.mkdir()
        p = kdir / "notes.md"
        p.write_text("# CONFIDENTIAL\n\nSome notes here.\n")
        findings = check_knowledge_classification([p])
        assert not findings


def test_knowledge_guard_accepts_all_three_classifications():
    for classification in ("PUBLIC", "CONFIDENTIAL", "NDA"):
        with tempfile.TemporaryDirectory() as d:
            kdir = Path(d) / "knowledge"
            kdir.mkdir()
            p = kdir / "doc.md"
            p.write_text(f"# {classification}\n\nContent.\n")
            findings = check_knowledge_classification([p])
            assert not findings, f"false positive for {classification}"


def test_knowledge_guard_ignores_files_outside_knowledge():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "README.md"
        p.write_text("# README\nNo classification needed here.\n")
        findings = check_knowledge_classification([p])
        assert not findings


# ---------------------------------------------------------------------------
# Integrity: both existing load_model.py files in this repo pass labeling
# ---------------------------------------------------------------------------

def test_existing_load_models_are_labeled():
    load_models = list((ROOT / "instances").rglob("load_model.py"))
    assert load_models, "no load_model.py found in instances/ — check repo structure"
    findings = check_labeling(load_models)
    assert not findings, f"existing load_model files missing labels: {findings}"
