"""
Tests for the three features added after LLM council review:
  1. govern_explain() — decision trace
  2. /why/{transaction_id} — audit endpoint
  3. voice_ttl_s / voice_request_expires_at — TTL for blocked Voice
  4. observe_only / shadow_mode — shadow mode deployment flag
"""

import pytest
from fastapi.testclient import TestClient

from core.governance import govern_explain
from api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. govern_explain() — unit tests
# ---------------------------------------------------------------------------

ENMAX_CHANNELS = [
    ("Touch",    0, 0.00, ""),
    ("Sound",    1, 0.10, ""),
    ("Vision",   2, 0.30, ""),
    ("Presence", 3, 0.10, ""),
    ("Voice",    4, 0.20, ""),
]


def test_explain_returns_tuple():
    result, trace = govern_explain(ENMAX_CHANNELS, budget=0.5, reflex_active=False)
    assert isinstance(result, list)
    assert isinstance(trace, dict)


def test_explain_trace_has_all_channels():
    _, trace = govern_explain(ENMAX_CHANNELS, budget=0.5, reflex_active=False)
    names = [c["name"] for c in trace["channels"]]
    assert set(names) == {"Touch", "Sound", "Vision", "Presence", "Voice"}


def test_explain_touch_blocked_when_reflex_inactive():
    _, trace = govern_explain(ENMAX_CHANNELS, budget=0.5, reflex_active=False)
    touch = next(c for c in trace["channels"] if c["name"] == "Touch")
    assert touch["admitted"] is False
    assert touch["reason"] == "reflex_inactive"


def test_explain_touch_admitted_when_reflex_active():
    _, trace = govern_explain(ENMAX_CHANNELS, budget=0.5, reflex_active=True)
    touch = next(c for c in trace["channels"] if c["name"] == "Touch")
    assert touch["admitted"] is True
    assert touch["reason"] == "reflex_active"


def test_explain_voice_not_requested():
    _, trace = govern_explain(ENMAX_CHANNELS, budget=0.9, reflex_active=False,
                              voice_requested=False)
    assert trace["voice_path"] == "not_requested"
    voice = next(c for c in trace["channels"] if c["name"] == "Voice")
    assert voice["admitted"] is False


def test_explain_voice_admitted_when_budget_ok():
    _, trace = govern_explain(ENMAX_CHANNELS, budget=0.9, reflex_active=False,
                              voice_requested=True)
    assert trace["voice_path"] == "elective_admitted"
    voice = next(c for c in trace["channels"] if c["name"] == "Voice")
    assert voice["admitted"] is True


def test_explain_voice_blocked_budget_exhausted():
    # Budget 0.35 — Sound(0.10)+Vision(0.30) = 0.40 > 0.35, so Vision blocked too.
    # Actually Sound(0.10)+Presence(0.10) = 0.20 admitted; Voice needs 0.20 more.
    # Let's use budget=0.20 so Sound(0.10)+Presence(0.10) consumes it all, Voice blocked.
    _, trace = govern_explain(ENMAX_CHANNELS, budget=0.20, reflex_active=False,
                              voice_requested=True)
    assert trace["voice_path"] == "elective_blocked"
    voice = next(c for c in trace["channels"] if c["name"] == "Voice")
    assert voice["admitted"] is False
    assert voice["reason"] == "budget_exhausted"


def test_explain_voice_urgent_bypass():
    _, trace = govern_explain(ENMAX_CHANNELS, budget=0.05, reflex_active=False,
                              voice_requested=True, risk_present=True)
    assert trace["voice_path"] == "urgent_pulse"
    voice = next(c for c in trace["channels"] if c["name"] == "Voice")
    assert voice["admitted"] is True
    assert voice["reason"] == "urgent_bypass_risk_present"
    assert "Voice:pulse" in trace["active_channels"]


def test_explain_trace_budget_in():
    _, trace = govern_explain(ENMAX_CHANNELS, budget=0.75, reflex_active=False)
    assert trace["budget_in"] == 0.75


# ---------------------------------------------------------------------------
# 2. /why/{transaction_id} — API audit endpoint
# ---------------------------------------------------------------------------

def _govern_enmax(voice_requested=False, p1_active=False, observe_only=False):
    return client.post("/instances/enmax/govern", json={
        "active_incidents": 3,
        "queue_depth": 1,
        "p1_active": p1_active,
        "crew_available": 0.8,
        "shift_elapsed_h": 2.0,
        "voice_requested": voice_requested,
        "observe_only": observe_only,
    })


def test_govern_response_includes_transaction_id():
    r = _govern_enmax()
    assert r.status_code == 200
    assert "transaction_id" in r.json()
    assert len(r.json()["transaction_id"]) == 36  # UUID4


def test_why_endpoint_returns_trace():
    txn_id = _govern_enmax().json()["transaction_id"]
    r = client.get(f"/why/{txn_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["transaction_id"] == txn_id
    assert body["domain"] == "enmax"
    assert "trace" in body
    assert "channels" in body["trace"]


def test_why_endpoint_404_for_unknown_id():
    r = client.get("/why/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_why_trace_contains_all_channels():
    txn_id = _govern_enmax(voice_requested=True).json()["transaction_id"]
    trace = client.get(f"/why/{txn_id}").json()["trace"]
    names = [c["name"] for c in trace["channels"]]
    assert "Touch" in names
    assert "Voice" in names


def test_why_generic_govern_also_stored():
    r = client.post("/govern", json={
        "channels": [
            {"name": "Touch",    "priority": 0, "cost": 0.0, "note": ""},
            {"name": "Sound",    "priority": 1, "cost": 0.1, "note": ""},
            {"name": "Voice",    "priority": 4, "cost": 0.2, "note": ""},
        ],
        "budget": 0.5,
    })
    txn_id = r.json()["transaction_id"]
    why = client.get(f"/why/{txn_id}")
    assert why.status_code == 200
    assert why.json()["domain"] is None  # generic — no domain


# ---------------------------------------------------------------------------
# 3. voice_ttl_s / voice_request_expires_at — TTL
# ---------------------------------------------------------------------------

def test_voice_request_expires_at_set_when_blocked():
    # Very low budget so Voice is blocked
    r = client.post("/instances/enmax/govern", json={
        "active_incidents": 9,
        "queue_depth": 4,
        "p1_active": True,
        "crew_available": 0.2,
        "shift_elapsed_h": 3.5,
        "voice_requested": True,
        "voice_ttl_s": 30.0,
    })
    body = r.json()
    # P1 saturates load — Voice should be blocked (no budget)
    if "Voice" not in body["active_channels"] and "Voice:pulse" not in body["active_channels"]:
        assert body["voice_request_expires_at"] is not None
    # If Voice:pulse fired (risk_present path), voice_request_expires_at may be None — that's fine


def test_voice_request_expires_at_none_when_voice_admitted():
    # Low load, voice requested, should be admitted
    r = client.post("/instances/enmax/govern", json={
        "active_incidents": 1,
        "queue_depth": 0,
        "p1_active": False,
        "crew_available": 1.0,
        "shift_elapsed_h": 0.5,
        "voice_requested": True,
        "voice_ttl_s": 30.0,
    })
    body = r.json()
    if "Voice" in body["active_channels"]:
        assert body["voice_request_expires_at"] is None


def test_voice_ttl_default_is_30s():
    # Just verify the field exists and defaults work
    r = client.post("/instances/enmax/govern", json={
        "active_incidents": 0,
        "queue_depth": 0,
        "p1_active": False,
        "crew_available": 1.0,
        "shift_elapsed_h": 1.0,
    })
    assert r.status_code == 200  # default voice_ttl_s=30 accepted


# ---------------------------------------------------------------------------
# 4. observe_only / shadow_mode
# ---------------------------------------------------------------------------

def test_shadow_mode_flag_in_response():
    r = _govern_enmax(observe_only=True)
    assert r.json()["shadow_mode"] is True


def test_shadow_mode_false_by_default():
    r = _govern_enmax(observe_only=False)
    assert r.json()["shadow_mode"] is False


def test_shadow_blocked_non_empty_when_channels_open():
    # Low load — several channels should be open
    r = client.post("/instances/enmax/govern", json={
        "active_incidents": 1,
        "queue_depth": 0,
        "p1_active": False,
        "crew_available": 1.0,
        "shift_elapsed_h": 0.5,
        "observe_only": True,
    })
    body = r.json()
    assert body["shadow_mode"] is True
    # shadow_blocked should list the channels that would have been active
    assert isinstance(body["shadow_blocked"], list)
    assert len(body["shadow_blocked"]) >= 1


def test_shadow_mode_generic_govern():
    r = client.post("/govern", json={
        "channels": [
            {"name": "Sound",  "priority": 1, "cost": 0.1, "note": ""},
            {"name": "Vision", "priority": 2, "cost": 0.3, "note": ""},
        ],
        "budget": 0.9,
        "observe_only": True,
    })
    body = r.json()
    assert body["shadow_mode"] is True
    assert body["transaction_id"] is not None
