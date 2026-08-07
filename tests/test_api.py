"""
API test suite — uses FastAPI's TestClient (no real server needed).

Tests cover: health, instance discovery, generic govern, ENMAX domain govern,
cycling domain govern, observer endpoint, and error cases.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

_ENMAX_CHANNELS = [
    {"name": "Touch",    "priority": 0, "cost": 0.00, "note": "reflex"},
    {"name": "Sound",    "priority": 1, "cost": 0.10, "note": "radio"},
    {"name": "Vision",   "priority": 2, "cost": 0.30, "note": "map"},
    {"name": "Presence", "priority": 3, "cost": 0.10, "note": "queue"},
    {"name": "Voice",    "priority": 4, "cost": 0.20, "note": "supervisor"},
]


# ---------------------------------------------------------------------------
# Health + discovery
# ---------------------------------------------------------------------------

def test_health_returns_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "core_version" in r.json()


def test_list_instances_returns_known_domains():
    r = client.get("/instances")
    assert r.status_code == 200
    domains = [i["domain"] for i in r.json()["instances"]]
    assert "f1" in domains
    assert "cycling" in domains
    assert "enmax" in domains


def test_get_instance_f1():
    r = client.get("/instances/f1")
    assert r.status_code == 200
    assert r.json()["status"] == "verified"


def test_get_instance_not_found():
    r = client.get("/instances/nonexistent")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Generic govern
# ---------------------------------------------------------------------------

def test_govern_generic_opens_voice_at_high_attention():
    r = client.post("/govern", json={
        "channels": _ENMAX_CHANNELS,
        "budget": 0.85,
        "reflex_active": False,
        "voice_requested": True,
    })
    assert r.status_code == 200
    body = r.json()
    assert "Voice" in body["active_channels"]
    assert body["budget_remaining"] >= 0


def test_govern_generic_blocks_voice_at_low_attention():
    r = client.post("/govern", json={
        "channels": _ENMAX_CHANNELS,
        "budget": 0.15,
        "reflex_active": False,
        "voice_requested": True,
    })
    assert r.status_code == 200
    assert "Voice" not in r.json()["active_channels"]


def test_govern_generic_reflex_fires_at_zero_budget():
    r = client.post("/govern", json={
        "channels": _ENMAX_CHANNELS,
        "budget": 0.0,
        "reflex_active": True,
    })
    assert r.status_code == 200
    assert "Touch" in r.json()["active_channels"]


def test_govern_generic_budget_validation():
    """Budget must be 0..1."""
    r = client.post("/govern", json={
        "channels": _ENMAX_CHANNELS,
        "budget": 1.5,
    })
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# ENMAX domain govern
# ---------------------------------------------------------------------------

def test_enmax_govern_p1_fires_touch_blocks_voice():
    """During a P1, Touch must fire and Voice must be blocked."""
    r = client.post("/instances/enmax/govern", json={
        "active_incidents": 8,
        "queue_depth": 3,
        "p1_active": True,
        "crew_available": 0.5,
        "shift_elapsed_h": 3.0,
        "voice_requested": True,
        "data_provenance": "DECLARED",
    })
    assert r.status_code == 200
    body = r.json()
    assert "Touch" in body["active_channels"]
    assert "Voice" not in body["active_channels"]
    assert body["reflex_fired"] is True


def test_enmax_govern_lull_opens_voice():
    """During a lull, Voice must open for supervisor contact."""
    r = client.post("/instances/enmax/govern", json={
        "active_incidents": 1,
        "queue_depth": 0,
        "p1_active": False,
        "crew_available": 0.90,
        "shift_elapsed_h": 5.5,
        "voice_requested": True,
        "data_provenance": "DECLARED",
    })
    assert r.status_code == 200
    body = r.json()
    assert "Voice" in body["active_channels"]
    assert body["reflex_fired"] is False


def test_enmax_govern_response_has_provenance():
    r = client.post("/instances/enmax/govern", json={
        "active_incidents": 3,
        "queue_depth": 1,
        "p1_active": False,
        "crew_available": 0.80,
        "shift_elapsed_h": 2.0,
        "data_provenance": "REAL",
    })
    assert r.status_code == 200
    assert r.json()["data_provenance"] == "REAL"


def test_enmax_govern_load_in_bounds():
    r = client.post("/instances/enmax/govern", json={
        "active_incidents": 5,
        "queue_depth": 2,
        "p1_active": False,
        "crew_available": 0.70,
        "shift_elapsed_h": 6.0,
        "data_provenance": "DECLARED",
    })
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["load"] <= 1.0
    assert 0.0 <= body["budget"] <= 1.0


# ---------------------------------------------------------------------------
# Cycling domain govern
# ---------------------------------------------------------------------------

def test_cycling_govern_descent_opens_voice():
    r = client.post("/instances/cycling/govern", json={
        "power_w": 20.0,
        "ftp_w": 240.0,
        "gradient_pct": -8.0,
        "phase": "descent",
        "shift_elapsed_s": 2400.0,
        "voice_requested": True,
        "data_provenance": "REAL",
    })
    assert r.status_code == 200
    assert "Voice" in r.json()["active_channels"]


def test_cycling_govern_climb_blocks_voice():
    r = client.post("/instances/cycling/govern", json={
        "power_w": 280.0,
        "ftp_w": 240.0,
        "gradient_pct": 9.0,
        "phase": "climb",
        "shift_elapsed_s": 1200.0,
        "voice_requested": True,
        "data_provenance": "REAL",
    })
    assert r.status_code == 200
    assert "Voice" not in r.json()["active_channels"]


# ---------------------------------------------------------------------------
# Observer endpoint
# ---------------------------------------------------------------------------

def test_observe_detects_sustained_high_load():
    """900 seconds above 0.80 must trigger SUSTAINED_HIGH_LOAD."""
    load = [0.85] * 1000
    attn = [0.15] * 1000
    r = client.post("/observe", json={
        "load": load,
        "attention": attn,
        "sample_rate_hz": 1,
        "sustained_load_threshold": 0.80,
        "sustained_load_window_s": 900,
    })
    assert r.status_code == 200
    body = r.json()
    types = [a["alert_type"] for a in body["alerts"]]
    assert "SUSTAINED_HIGH_LOAD" in types


def test_observe_empty_arrays_no_alerts():
    r = client.post("/observe", json={
        "load": [0.30] * 100,
        "attention": [0.70] * 100,
    })
    assert r.status_code == 200
    assert r.json()["total_alerts"] == 0


def test_observe_mismatched_array_lengths_rejected():
    r = client.post("/observe", json={
        "load": [0.5] * 10,
        "attention": [0.5] * 20,
    })
    assert r.status_code == 422
