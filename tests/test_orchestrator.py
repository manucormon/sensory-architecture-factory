"""
Orchestrator and sub-agent tests.

Covers: registry CRUD, scaffolder output, verifier parsing, and the
end-to-end 'new' command. Tests that touch the filesystem use a
temporary registry file and a throwaway domain name so they never
corrupt the real registry or leave ghost instance directories.
"""

import json
import sys
import os
import tempfile
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

import agents.registry as reg_module
from agents.registry import (
    load, save, register, get_instance,
    update_status, update_field, summary_table, find_orphans,
)
from agents.scaffolder import scaffold, teardown
from agents.verifier import _parse, _timeout_result, VerificationResult


# ---------------------------------------------------------------------------
# Helpers — swap the registry path for a temp file during tests
# ---------------------------------------------------------------------------

REAL_REGISTRY = reg_module.REGISTRY_PATH
_TEST_DOMAIN = "_test_orchestra_tmp"


def _make_temp_registry(tmp_dir):
    """Copy the real registry into tmp_dir and redirect the module to it."""
    src = REAL_REGISTRY
    dest = Path(tmp_dir) / "instance_registry.json"
    shutil.copy(src, dest)
    reg_module.REGISTRY_PATH = dest
    return dest


def _restore_registry():
    reg_module.REGISTRY_PATH = REAL_REGISTRY


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

def test_registry_loads_known_instances():
    instances = load()["instances"]
    assert "f1" in instances
    assert "tennis" in instances


def test_registry_f1_is_verified():
    entry = get_instance("f1")
    assert entry["status"] == "verified"


def test_registry_get_missing_returns_none():
    assert get_instance("__nonexistent__") is None


def test_registry_register_and_read(tmp_path):
    _make_temp_registry(tmp_path)
    try:
        register(_TEST_DOMAIN,
                 has_recovery_window=True,
                 has_multi_timescale_load=False)
        entry = get_instance(_TEST_DOMAIN)
        assert entry is not None
        assert entry["status"] == "scaffolded"
        assert entry["has_recovery_window"] is True
        assert entry["has_multi_timescale_load"] is False
        # All channel costs start as None
        assert all(v is None for v in entry["channel_costs"].values())
    finally:
        _restore_registry()


def test_registry_register_duplicate_raises(tmp_path):
    _make_temp_registry(tmp_path)
    try:
        register(_TEST_DOMAIN, has_recovery_window=False, has_multi_timescale_load=False)
        try:
            register(_TEST_DOMAIN, has_recovery_window=False, has_multi_timescale_load=False)
            assert False, "expected ValueError"
        except ValueError:
            pass
    finally:
        _restore_registry()


def test_registry_update_status(tmp_path):
    _make_temp_registry(tmp_path)
    try:
        register(_TEST_DOMAIN, has_recovery_window=True, has_multi_timescale_load=True)
        update_status(_TEST_DOMAIN, "in_progress")
        assert get_instance(_TEST_DOMAIN)["status"] == "in_progress"
    finally:
        _restore_registry()


def test_registry_invalid_status_raises(tmp_path):
    _make_temp_registry(tmp_path)
    try:
        register(_TEST_DOMAIN, has_recovery_window=False, has_multi_timescale_load=False)
        try:
            update_status(_TEST_DOMAIN, "made_up_status")
            assert False, "expected ValueError"
        except ValueError:
            pass
    finally:
        _restore_registry()


def test_registry_atomic_write_leaves_no_temp_files(tmp_path):
    _make_temp_registry(tmp_path)
    try:
        register(_TEST_DOMAIN, has_recovery_window=True, has_multi_timescale_load=False)
        temp_files = list(tmp_path.glob(".registry_tmp_*"))
        assert not temp_files, f"atomic write left temp files: {temp_files}"
    finally:
        _restore_registry()


def test_registry_find_orphans_detects_unregistered_dir(tmp_path):
    _make_temp_registry(tmp_path)
    # Temporarily point INSTANCES_DIR to a fake dir with an unregistered folder
    import agents.registry as rm
    original_instances = rm.INSTANCES_DIR
    fake_instances = tmp_path / "instances"
    fake_instances.mkdir()
    (fake_instances / "f1").mkdir()      # registered
    (fake_instances / "ghost").mkdir()   # NOT in registry
    rm.INSTANCES_DIR = fake_instances
    try:
        orphans = find_orphans()
        assert "ghost" in orphans
        assert "f1" not in orphans
    finally:
        rm.INSTANCES_DIR = original_instances
        _restore_registry()


def test_registry_summary_table_includes_all_instances():
    table = summary_table()
    assert "f1" in table
    assert "tennis" in table


# ---------------------------------------------------------------------------
# Scaffolder tests
# ---------------------------------------------------------------------------

def test_scaffolder_creates_expected_files():
    try:
        dest = scaffold(_TEST_DOMAIN,
                        has_recovery_window=True,
                        has_multi_timescale_load=False)
        expected = ["data_loader.py", "perception.py", "load_model.py",
                    "reflex_trigger.py", "config.py", "run.py", "NOTES.md"]
        for f in expected:
            assert (dest / f).exists(), f"missing: {f}"
        assert (dest / "data").is_dir()
    finally:
        teardown(_TEST_DOMAIN)


def test_scaffolder_notes_contains_declarations():
    try:
        dest = scaffold(_TEST_DOMAIN,
                        has_recovery_window=False,
                        has_multi_timescale_load=True)
        notes = (dest / "NOTES.md").read_text()
        assert "HAS_RECOVERY_WINDOW = False" in notes
        assert "HAS_MULTI_TIMESCALE_LOAD = True" in notes
    finally:
        teardown(_TEST_DOMAIN)


def test_scaffolder_load_model_carries_declared_label():
    """The labeling check in pre_commit_hook.py must pass for a fresh scaffold."""
    try:
        dest = scaffold(_TEST_DOMAIN,
                        has_recovery_window=True,
                        has_multi_timescale_load=False)
        text = (dest / "load_model.py").read_text()
        assert "DECLARED" in text or "REAL" in text or "PROXY" in text
    finally:
        teardown(_TEST_DOMAIN)


def test_scaffolder_perception_stub_is_unset():
    """Scaffolded perception.py must have HAS_PERCEPTION=None (not yet declared)."""
    try:
        dest = scaffold(_TEST_DOMAIN,
                        has_recovery_window=True,
                        has_multi_timescale_load=False)
        text = (dest / "perception.py").read_text()
        assert "HAS_PERCEPTION = None" in text
        assert "NotImplementedError" in text
    finally:
        teardown(_TEST_DOMAIN)


def test_scaffolder_raises_if_domain_already_exists():
    try:
        scaffold(_TEST_DOMAIN, has_recovery_window=True, has_multi_timescale_load=False)
        try:
            scaffold(_TEST_DOMAIN, has_recovery_window=True, has_multi_timescale_load=False)
            assert False, "expected FileExistsError"
        except FileExistsError:
            pass
    finally:
        teardown(_TEST_DOMAIN)


def test_scaffolder_never_touches_core():
    """core/ must be unmodified before and after scaffolding."""
    core_gov = ROOT / "core" / "governance.py"
    mtime_before = core_gov.stat().st_mtime
    try:
        scaffold(_TEST_DOMAIN, has_recovery_window=True, has_multi_timescale_load=False)
    finally:
        teardown(_TEST_DOMAIN)
    mtime_after = core_gov.stat().st_mtime
    assert mtime_before == mtime_after, "scaffolder modified core/governance.py — contract breach"


# ---------------------------------------------------------------------------
# Verifier tests
# ---------------------------------------------------------------------------

MOCK_GREEN_OUTPUT = """\
[pre-commit] scanning full repo (35 files)
[OK] CHECK 1 — no secrets detected
[OK] CHECK 2 — labeling present in 2 load_model file(s)
[OK] CHECK 3 — no knowledge/ .md files to check
[pre-commit] all checks passed — gate open.
..............
14 passed in 1.14s
  [PASS] security
  [PASS] pytest
  VERDE — pipeline may proceed.
"""

MOCK_RED_OUTPUT = """\
[BLOCKED] CHECK 2 — load_model.py files missing REAL/PROXY/DECLARED label:
  instances/cycling/load_model.py
[pre-commit] GATE CLOSED
FAILED tests/test_cycling_instance.py::test_voice_resolves
1 failed, 13 passed in 2.01s
  ROJO — pipeline blocked.
"""


def test_verifier_parses_green_output():
    result = _parse(MOCK_GREEN_OUTPUT, returncode=0)
    assert result.all_green
    assert not result.timed_out
    assert result.test_count == 14
    assert result.failed_tests == []
    assert result.security_findings == []


def test_verifier_parses_red_output():
    result = _parse(MOCK_RED_OUTPUT, returncode=1)
    assert not result.all_green
    assert not result.timed_out
    assert "tests/test_cycling_instance.py::test_voice_resolves" in result.failed_tests
    assert any("CHECK 2" in f for f in result.security_findings)


def test_verifier_timeout_result_is_not_green():
    result = _timeout_result()
    assert not result.all_green
    assert result.timed_out
    assert "TIMEOUT" in result.summary()


def test_verifier_summary_mentions_status():
    green = _parse(MOCK_GREEN_OUTPUT, 0)
    assert "GREEN" in green.summary()
    red = _parse(MOCK_RED_OUTPUT, 1)
    assert "RED" in red.summary()


# ---------------------------------------------------------------------------
# Orchestrator CLI integration test
# ---------------------------------------------------------------------------

def test_orchestrator_status_check_fs_exits_zero():
    result = subprocess.run(
        [sys.executable, str(ROOT / "orchestrator.py"), "status", "--check-fs"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_orchestrator_status_exits_zero():
    result = subprocess.run(
        [sys.executable, str(ROOT / "orchestrator.py"), "status"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "f1" in result.stdout
    assert "tennis" in result.stdout


def test_orchestrator_report_exits_zero():
    result = subprocess.run(
        [sys.executable, str(ROOT / "orchestrator.py"), "report"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "F1" in result.stdout or "f1" in result.stdout


def test_orchestrator_verify_scoped_to_f1_passes():
    # Use --domain f1 to avoid launching a full nested pytest suite inside pytest
    result = subprocess.run(
        [sys.executable, str(ROOT / "orchestrator.py"), "verify", "--domain", "f1"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "GREEN" in result.stdout
