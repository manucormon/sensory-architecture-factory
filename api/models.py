"""
api/models.py — Pydantic request/response models for the governance API.

Every model that carries domain metrics must declare a data_provenance field.
The API does not enforce REAL/PROXY/DECLARED labeling (that's a contract between
the client and the governance model), but it surfaces the field so callers are
reminded they need to declare it — the discipline travels through the wire.
"""

from __future__ import annotations
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Generic govern endpoint
# ---------------------------------------------------------------------------

class ChannelSpec(BaseModel):
    name: str
    priority: int
    cost: float
    note: str = ""


class GovernRequest(BaseModel):
    """
    Domain-agnostic single-sample governance request.
    The caller has already computed the attention budget.
    """
    channels: List[ChannelSpec]
    budget: float = Field(..., ge=0.0, le=1.0,
                          description="Attention budget (1 - load), 0..1")
    reflex_active: bool = False
    voice_requested: bool = False
    risk_present: bool = False


class GovernResponse(BaseModel):
    active_channels: List[str]
    budget_consumed: float
    budget_remaining: float
    reflex_fired: bool


# ---------------------------------------------------------------------------
# Domain-specific govern endpoints
# ---------------------------------------------------------------------------

class ENMAXGovernRequest(BaseModel):
    """
    ENMAX dispatcher metrics — the CAD system sends these; the server runs
    perception + load_model + governance and returns the channel decision.

    data_provenance: caller must declare the label for each metric they send.
    In production this would be REAL (from a live CAD stream). In testing
    it may be DECLARED or PROXY.
    """
    active_incidents: int = Field(..., ge=0, description="Open tickets")
    queue_depth:      int = Field(..., ge=0, description="Calls waiting")
    p1_active:        bool = Field(..., description="Life-safety incident open")
    crew_available:   float = Field(..., ge=0.0, le=1.0,
                                    description="Fraction of field crews available")
    shift_elapsed_h:  float = Field(..., ge=0.0, le=24.0,
                                    description="Hours into the shift")
    voice_requested:  bool = False
    data_provenance:  str = Field(
        "DECLARED",
        description="REAL | PROXY | DECLARED — label for the metrics in this request"
    )


class CyclingGovernRequest(BaseModel):
    """
    Cycling instance metrics — power-meter data for a single sample.
    """
    power_w:         float = Field(..., ge=0.0, description="Current power output (W)")
    ftp_w:           float = Field(..., gt=0.0, description="Athlete FTP (W)")
    gradient_pct:    float = Field(..., ge=-20.0, le=20.0,
                                   description="Road gradient %, MEASURED from GPS")
    phase:           str   = Field(..., description="climb | descent | flat")
    shift_elapsed_s: float = Field(..., ge=0.0,
                                   description="Seconds elapsed in the ride")
    voice_requested: bool = False
    data_provenance: str = Field(
        "REAL",
        description="REAL | PROXY | DECLARED — label for the metrics in this request"
    )


class DomainGovernResponse(BaseModel):
    domain: str
    active_channels: List[str]
    budget: float
    load: float
    instant_load: float
    fatigue: float
    reflex_fired: bool
    data_provenance: str
    governance_note: str = ""


# ---------------------------------------------------------------------------
# Observer endpoint
# ---------------------------------------------------------------------------

class ObserveRequest(BaseModel):
    """
    Run the observer agent over a full session array.
    Arrays must be equal length. fatigue is optional (single-timescale instances).
    """
    load:      List[float]
    attention: List[float]
    fatigue:   Optional[List[float]] = None
    sample_rate_hz: int = Field(1, ge=1)
    sustained_load_threshold:  float = Field(0.80, ge=0.0, le=1.0)
    sustained_load_window_s:   float = Field(900.0, ge=0.0)
    fatigue_ceiling:           float = Field(0.70, ge=0.0, le=1.0)
    attention_floor:           float = Field(0.15, ge=0.0, le=1.0)
    attention_floor_window_s:  float = Field(300.0, ge=0.0)
    recovery_threshold:        float = Field(0.55, ge=0.0, le=1.0)
    recovery_window_s:         float = Field(60.0, ge=0.0)


class AlertOut(BaseModel):
    alert_type:   str
    sample_index: int
    elapsed_s:    float
    load:         float
    attention:    float
    fatigue:      Optional[float]
    message:      str


class ObserveResponse(BaseModel):
    total_alerts: int
    alerts: List[AlertOut]
