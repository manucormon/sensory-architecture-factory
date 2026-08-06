"""
agents/registry.py — Instance registry reader/writer.

Single source of truth for what instances exist, their verification status,
and the design decisions recorded per CONTRACT.md. The orchestrator delegates
all registry I/O here so the logic is testable in isolation.

Design constraints:
  - Never touches core/ or instance code files — registry I/O only.
  - Writes are atomic (temp file + rename) to prevent corruption from
    concurrent orchestrator calls or interrupted writes.
"""

import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Optional, List

ROOT = Path(__file__).parent.parent.resolve()
REGISTRY_PATH = ROOT / "instance_registry.json"
INSTANCES_DIR = ROOT / "instances"

VALID_STATUSES = {"scaffolded", "in_progress", "verified", "hypothetical", "deprecated"}


# ---------------------------------------------------------------------------
# Core I/O — atomic write
# ---------------------------------------------------------------------------

def load() -> dict:
    """Return the full registry dict. Raises if the file is missing or malformed."""
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Registry not found: {REGISTRY_PATH}")
    with REGISTRY_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def save(registry: dict) -> None:
    """
    Write registry atomically: write to a temp file in the same directory,
    then rename over the target. On POSIX, rename is atomic — a concurrent
    reader always sees either the old file or the new one, never a partial write.
    """
    target = REGISTRY_PATH
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=target.parent, prefix=".registry_tmp_", suffix=".json"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(registry, f, indent=2)
            f.write("\n")
        os.replace(tmp_path, target)  # atomic on POSIX
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def get_instance(domain: str) -> Optional[dict]:
    """Return the registry entry for domain, or None if it doesn't exist."""
    return load()["instances"].get(domain)


def list_instances() -> dict:
    return load()["instances"]


def find_orphans() -> List[str]:
    """
    Return domain names that exist as directories under instances/ but are
    not registered in the registry. These were likely created by hand without
    going through orchestrator.py new.
    """
    if not INSTANCES_DIR.exists():
        return []
    registered = set(load()["instances"].keys())
    on_disk = {
        d.name for d in INSTANCES_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    }
    return sorted(on_disk - registered)


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def register(domain: str, *, has_recovery_window: bool,
             has_multi_timescale_load: bool) -> None:
    """
    Add a new scaffolded instance to the registry. Raises if domain already
    exists — use update_field() to change an existing entry.
    """
    registry = load()
    if domain in registry["instances"]:
        raise ValueError(f"Instance '{domain}' already in registry. "
                         "Use update_field() to modify it.")
    registry["instances"][domain] = {
        "status": "scaffolded",
        "governed_subject": None,
        "data_provenance": None,
        "has_recovery_window": has_recovery_window,
        "has_multi_timescale_load": has_multi_timescale_load,
        "has_reflex": None,
        "channel_costs": {
            "Touch": None, "Sound": None, "Vision": None,
            "Presence": None, "Voice": None,
        },
        "voice_opens_at_most_open_moment": None,
        "test_file": f"tests/test_{domain}_instance.py",
        "baseline_csv": None,
        "last_verified": None,
        "notes": "Scaffolded — not yet implemented or verified.",
    }
    save(registry)


def update_field(domain: str, field: str, value) -> None:
    """Update a single field on an existing instance entry."""
    registry = load()
    if domain not in registry["instances"]:
        raise KeyError(f"Instance '{domain}' not in registry.")
    registry["instances"][domain][field] = value
    save(registry)


def update_status(domain: str, status: str) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Valid: {VALID_STATUSES}")
    update_field(domain, "status", status)
    update_field(domain, "last_verified",
                 str(date.today()) if status == "verified" else None)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def summary_table(show_orphans: bool = False) -> str:
    """Return a human-readable status table for all instances."""
    instances = list_instances()
    lines = []
    if not instances:
        lines.append("  (no instances registered)")
    else:
        col_w = max(len(d) for d in instances) + 2
        lines.append(f"  {'DOMAIN':<{col_w}} {'STATUS':<14} {'PROVENANCE':<10} {'VERIFIED'}")
        lines.append("  " + "-" * 60)
        for domain, entry in instances.items():
            prov = (entry.get("data_provenance") or "?").split()[0]
            verified = entry.get("last_verified") or "—"
            lines.append(f"  {domain:<{col_w}} {entry['status']:<14} {prov:<10} {verified}")

    if show_orphans:
        orphans = find_orphans()
        if orphans:
            lines.append("")
            lines.append("  ORPHANS (on disk but not in registry — run 'orchestrator.py new' or investigate):")
            for o in orphans:
                lines.append(f"    instances/{o}/")
        else:
            lines.append("  (no orphan instance directories found)")

    return "\n".join(lines)
