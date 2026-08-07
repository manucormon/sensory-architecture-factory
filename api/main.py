"""
api/main.py — Sensory Architecture Factory HTTP API.

Exposes the governance engine as a REST API. Two integration modes:

  GENERIC  POST /govern
    Caller computes the attention budget externally and sends it.
    Good for systems that already have a load model and want only the
    channel arbitration logic.

  DOMAIN   POST /instances/{domain}/govern
    Caller sends raw domain metrics (incidents, power, etc.).
    Server runs perception + load_model + governance.
    Good for a CAD system, a cycling computer, or any sensor stream
    that does not want to know the governance model internals.

Security note: this server has NO authentication. Before exposing to a
real network, add OAuth2/API key middleware. The factory is designed for
internal use or behind an API gateway. Do not run publicly without auth.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uuid
import numpy as np
from collections import OrderedDict
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from core.channels_schema import CORE_VERSION
from core.governance import govern, govern_hybrid, govern_explain

from instances.enmax.load_model import compute_load as enmax_load
from instances.enmax.config import CHANNELS as ENMAX_CHANNELS
from instances.enmax.reflex_trigger import HAS_REFLEX as ENMAX_HAS_REFLEX

from instances.cycling.load_model import compute_load as cycling_load
from instances.cycling.config import CHANNELS as CYCLING_CHANNELS

from agents.observer import Observer
from agents.registry import load as load_registry

from api.models import (
    GovernRequest, GovernResponse,
    ENMAXGovernRequest, CyclingGovernRequest, DomainGovernResponse,
    ObserveRequest, ObserveResponse, AlertOut, WhyResponse,
)

# ---------------------------------------------------------------------------
# In-memory decision store for /why/{transaction_id}
# Capped at _MAX_STORED entries — oldest evicted first.
# ---------------------------------------------------------------------------
_MAX_STORED = 1000
_decision_store: OrderedDict[str, dict] = OrderedDict()


def _store(transaction_id: str, domain: str | None, trace: dict) -> None:
    if len(_decision_store) >= _MAX_STORED:
        _decision_store.popitem(last=False)
    _decision_store[transaction_id] = {
        "transaction_id": transaction_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "domain": domain,
        "trace": trace,
    }

app = FastAPI(
    title="Sensory Architecture Factory API",
    description=(
        "Attention-governance engine: given a person's cognitive load, "
        "decides which sensory channels (Touch/Sound/Vision/Presence/Voice) "
        "may reach them. Domain-agnostic core, domain-specific instances."
    ),
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Health + discovery
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "core_version": CORE_VERSION}


@app.get("/instances")
def list_instances():
    """List all registered instances and their current status."""
    registry = load_registry()
    return {
        "instances": [
            {
                "domain":           domain,
                "status":           info.get("status"),
                "data_provenance":  info.get("data_provenance"),
                "has_reflex":       info.get("has_reflex"),
                "has_perception":   info.get("has_perception"),
            }
            for domain, info in registry.get("instances", {}).items()
        ]
    }


@app.get("/instances/{domain}")
def get_instance(domain: str):
    """Return full registry entry for one instance."""
    registry = load_registry()
    instances = registry.get("instances", {})
    if domain not in instances:
        raise HTTPException(status_code=404, detail=f"Instance '{domain}' not found")
    return instances[domain]


@app.get("/why/{transaction_id}", response_model=WhyResponse)
def why(transaction_id: str):
    """
    Return the full decision trace for a previous govern call.

    Every /govern and /instances/{domain}/govern response includes a
    transaction_id. Pass it here to see exactly why each channel was
    admitted or blocked: budget at each step, reason per channel,
    voice path taken.

    Decisions are kept in memory (last 1000). For durable audit logs,
    forward the trace to your SIEM or logging pipeline.
    """
    record = _decision_store.get(transaction_id)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail=f"Transaction '{transaction_id}' not found. "
                   "Decisions are kept in memory (last 1000 calls)."
        )
    return WhyResponse(**record)


# ---------------------------------------------------------------------------
# Generic govern endpoint
# ---------------------------------------------------------------------------

@app.post("/govern", response_model=GovernResponse)
def govern_generic(req: GovernRequest):
    """
    Domain-agnostic single-sample governance.
    The caller supplies the attention budget and the channel list.
    The server runs the channel arbitration and returns which channels are open.

    Set observe_only=true for shadow mode: same response, but shadow_mode=true
    signals the client it should not actuate — used for pilot deployments that
    measure cognitive savings without routing changes.
    """
    channels = [(c.name, c.priority, c.cost, c.note) for c in req.channels]
    result, trace = govern_explain(
        channels,
        req.budget,
        req.reflex_active,
        voice_requested=req.voice_requested,
        risk_present=req.risk_present,
    )
    txn_id = str(uuid.uuid4())
    _store(txn_id, None, trace)

    consumed = sum(cost for name, _, cost, _ in channels
                   if name in result and name != "Touch")

    shadow_blocked = []
    if req.observe_only:
        shadow_blocked = [ch for ch in result if ch not in ("Touch",)]

    return GovernResponse(
        transaction_id=txn_id,
        active_channels=result,
        budget_consumed=round(consumed, 4),
        budget_remaining=round(max(0.0, req.budget - consumed), 4),
        reflex_fired=("Touch" in result and req.reflex_active),
        shadow_mode=req.observe_only,
        shadow_blocked=shadow_blocked if req.observe_only else [],
    )


# ---------------------------------------------------------------------------
# ENMAX domain endpoint
# ---------------------------------------------------------------------------

@app.post("/instances/enmax/govern", response_model=DomainGovernResponse)
def govern_enmax(req: ENMAXGovernRequest):
    """
    ENMAX dispatcher governance.

    Send raw CAD metrics; the server runs the full pipeline
    (load model + governance) and returns the channel decision.

    Typical integration: your CAD system calls this endpoint every second
    (or on any state change) and uses the active_channels list to filter
    which notifications reach the dispatcher.
    """
    sample = {
        "active_incidents": req.active_incidents,
        "queue_depth":      req.queue_depth,
        "p1_active":        req.p1_active,
        "crew_available":   req.crew_available,
        "shift_elapsed_h":  req.shift_elapsed_h,
    }
    instant_arr, fatigue_arr, load_arr, attention_arr = enmax_load([sample])
    instant   = float(instant_arr[0])
    fatigue   = float(fatigue_arr[0])
    load      = float(load_arr[0])
    attention = float(attention_arr[0])

    reflex_active = req.p1_active and ENMAX_HAS_REFLEX
    result, trace = govern_explain(
        ENMAX_CHANNELS,
        attention,
        reflex_active,
        voice_requested=req.voice_requested,
        risk_present=req.p1_active,
    )
    txn_id = str(uuid.uuid4())
    _store(txn_id, "enmax", trace)

    voice_blocked = req.voice_requested and "Voice" not in result and "Voice:pulse" not in result
    voice_retry_before = None
    if voice_blocked:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=req.voice_ttl_s)
        voice_retry_before = expires_at.isoformat()

    note = ""
    if req.p1_active and "Touch" in result:
        note = "P1 active — Touch bypassed budget. Supervisor cannot interrupt via Voice."
    elif req.voice_requested and "Voice" in result:
        note = "Voice admitted — cognitive budget available for supervisor contact."
    elif voice_blocked:
        note = f"Voice blocked — budget insufficient. Request expires at {voice_retry_before}."

    shadow_blocked = []
    if req.observe_only:
        shadow_blocked = [ch for ch in result if ch != "Touch"]

    return DomainGovernResponse(
        transaction_id=txn_id,
        domain="enmax",
        active_channels=result,
        budget=round(attention, 4),
        load=round(load, 4),
        instant_load=round(instant, 4),
        fatigue=round(fatigue, 4),
        reflex_fired=("Touch" in result and reflex_active),
        data_provenance=req.data_provenance,
        governance_note=note,
        shadow_mode=req.observe_only,
        shadow_blocked=shadow_blocked,
        voice_retry_before=voice_retry_before,
    )


# ---------------------------------------------------------------------------
# Cycling domain endpoint
# ---------------------------------------------------------------------------

@app.post("/instances/cycling/govern", response_model=DomainGovernResponse)
def govern_cycling(req: CyclingGovernRequest):
    """
    Cycling instance governance.

    Send a single power-meter sample; the server runs the load model
    and returns the channel decision. Note: the two-timescale model
    (accumulated fatigue) requires the full ride history to be meaningful.
    This endpoint computes single-sample instantaneous load only —
    fatigue will be 0.0 for isolated calls. For full-session governance,
    use the batch endpoint or run instances/cycling/run.py directly.
    """
    import pandas as pd
    df = pd.DataFrame([{
        "power_w":      req.power_w,
        "gradient_pct": req.gradient_pct,
        "phase":        req.phase,
    }])
    instant_arr, fatigue_arr, load_arr, attention_arr = cycling_load(df, req.ftp_w)
    instant   = float(instant_arr[0])
    fatigue   = float(fatigue_arr[0])
    load      = float(load_arr[0])
    attention = float(attention_arr[0])

    result, trace = govern_explain(
        CYCLING_CHANNELS,
        attention,
        False,
        voice_requested=req.voice_requested,
        risk_present=False,
    )
    txn_id = str(uuid.uuid4())
    _store(txn_id, "cycling", trace)

    voice_blocked = req.voice_requested and "Voice" not in result
    voice_retry_before = None
    if voice_blocked:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=req.voice_ttl_s)
        voice_retry_before = expires_at.isoformat()

    note = ""
    if req.phase == "descent" and "Voice" in result:
        note = "Descent recovery window — Voice open for directeur sportif contact."
    elif req.phase == "climb" and "Voice" not in result:
        note = f"Climb load — Voice blocked. Request expires at {voice_retry_before}." \
               if voice_blocked else "Climb load — Voice blocked."

    shadow_blocked = []
    if req.observe_only:
        shadow_blocked = [ch for ch in result]

    return DomainGovernResponse(
        transaction_id=txn_id,
        domain="cycling",
        active_channels=result,
        budget=round(attention, 4),
        load=round(load, 4),
        instant_load=round(instant, 4),
        fatigue=round(fatigue, 4),
        reflex_fired=False,
        data_provenance=req.data_provenance,
        governance_note=note,
        shadow_mode=req.observe_only,
        shadow_blocked=shadow_blocked,
        voice_retry_before=voice_retry_before,
    )


# ---------------------------------------------------------------------------
# Observer endpoint
# ---------------------------------------------------------------------------

@app.post("/observe", response_model=ObserveResponse)
def observe(req: ObserveRequest):
    """
    Run the observer agent over a session's load/attention/fatigue arrays.

    Send the full arrays from a completed or ongoing session.
    Returns structured alerts (SUSTAINED_HIGH_LOAD, FATIGUE_CEILING,
    ATTENTION_FLOOR, RECOVERY_DETECTED) that a supervisor dashboard
    or on-call system can act on.
    """
    if len(req.load) != len(req.attention):
        raise HTTPException(status_code=422,
                            detail="load and attention arrays must be the same length")
    if req.fatigue and len(req.fatigue) != len(req.load):
        raise HTTPException(status_code=422,
                            detail="fatigue array must be the same length as load")

    obs = Observer(
        sample_rate_hz=req.sample_rate_hz,
        sustained_load_threshold=req.sustained_load_threshold,
        sustained_load_window_s=req.sustained_load_window_s,
        fatigue_ceiling=req.fatigue_ceiling,
        attention_floor=req.attention_floor,
        attention_floor_window_s=req.attention_floor_window_s,
        recovery_threshold=req.recovery_threshold,
        recovery_window_s=req.recovery_window_s,
        callback=lambda _: None,   # suppress stdout inside API
    )
    fatigue_arr = np.array(req.fatigue) if req.fatigue else None
    alerts = obs.scan(
        np.array(req.load),
        np.array(req.attention),
        fatigue_arr,
    )
    return ObserveResponse(
        total_alerts=len(alerts),
        alerts=[AlertOut(**a.as_dict()) for a in alerts],
    )
