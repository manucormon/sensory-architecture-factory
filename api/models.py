"""
api/models.py — Pydantic request/response models for the governance API.

Every model that carries domain metrics must declare a data_provenance field.
The API does not enforce REAL/PROXY/DECLARED labeling (that's a contract between
the client and the governance model), but it surfaces the field so callers are
reminded they need to declare it — the discipline travels through the wire.
"""

from __future__ import annotations
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import math


# ---------------------------------------------------------------------------
# Generic govern endpoint
# ---------------------------------------------------------------------------

class ChannelSpec(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    priority: int = Field(..., ge=0, le=100)
    cost: float = Field(..., ge=0.0, le=1.0)
    note: str = Field("", max_length=256)

    @field_validator("cost")
    @classmethod
    def cost_must_be_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("cost must be a finite number")
        return v


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
    observe_only: bool = Field(
        False,
        description="Shadow mode: run all logic but mark response as observation-only. "
                    "Actuation is the client's responsibility — this flag tells it not to."
    )


class GovernResponse(BaseModel):
    transaction_id: str
    active_channels: List[str]
    budget_consumed: float
    budget_remaining: float
    reflex_fired: bool
    shadow_mode: bool = False
    shadow_blocked: List[str] = []


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
    voice_ttl_s:      float = Field(
        30.0, ge=1.0,
        description="Seconds before a blocked Voice request is considered stale. "
                    "If Voice is blocked, voice_retry_before in the response marks "
                    "the deadline — retry after that delivers a stale alert."
    )
    observe_only: bool = Field(
        False,
        description="Shadow mode: engine runs but client should not actuate."
    )
    data_provenance: Literal["REAL", "PROXY", "DECLARED"] = Field(
        "DECLARED",
        description="REAL | PROXY | DECLARED — label for the metrics in this request"
    )


class CyclingGovernRequest(BaseModel):
    """
    Cycling instance metrics — power-meter data for a single sample.

    API 1.1 changes (backwards-compatible):
      - fatigue: Optional[float] = None — None means unknown; server uses instant_only mode.
        Absence MUST NOT be silently converted to 0.0 (that would fabricate history).
        If you have ride history, supply fatigue + fatigue_provenance.
      - fatigue_provenance: required when fatigue is not None.
      - load_mode: "instant_only" (default) | "two_timescale". Reflects what the server did.
        Consumers that require two_timescale must return 422 when fatigue is None.
      - voice_retry_before: deprecated alias for voice_request_expires_at (API 1.x compat).
        Both carry the same value. Removed in API 2.0.
    """
    power_w:         float = Field(..., ge=0.0, description="Current power output (W)")
    ftp_w:           float = Field(..., gt=0.0, description="Athlete FTP (W)")
    gradient_pct:    float = Field(..., ge=-20.0, le=20.0,
                                   description="Road gradient %, MEASURED from GPS")
    phase:           Literal["climb", "descent", "flat"] = Field(..., description="climb | descent | flat")
    shift_elapsed_s: float = Field(..., ge=0.0,
                                   description="Seconds elapsed in the ride (informational; "
                                               "used for audit trail, not fatigue computation)")
    fatigue: Optional[float] = Field(
        None, ge=0.0, le=1.0,
        description="Accumulated fatigue [0..1], DECLARED by the client. "
                    "None = unknown / start of session. "
                    "The server has no ride history — the client must compute and supply this. "
                    "MUST NOT be defaulted to 0.0 by the server (fabricated history). "
                    "When None, server uses instant_only load model."
    )
    fatigue_provenance: Optional[Literal["REAL", "PROXY", "DECLARED"]] = Field(
        None,
        description="Required when fatigue is not None. Declares how fatigue was derived."
    )
    voice_requested: bool = False
    voice_ttl_s:     float = Field(
        30.0, ge=1.0,
        description="Seconds before a blocked Voice request is considered stale."
    )
    observe_only: bool = Field(
        False,
        description="Shadow mode: engine runs but client should not actuate."
    )
    data_provenance: Literal["REAL", "PROXY", "DECLARED"] = Field(
        "REAL",
        description="REAL | PROXY | DECLARED — label for the metrics in this request"
    )

    @model_validator(mode="after")
    def check_fatigue_provenance_consistency(self):
        fatigue_present = self.fatigue is not None
        provenance_present = self.fatigue_provenance is not None
        if fatigue_present and not provenance_present:
            raise ValueError("fatigue_provenance is required when fatigue is provided")
        if not fatigue_present and provenance_present:
            raise ValueError(
                "fatigue_provenance must not be provided when fatigue is absent"
            )
        return self


class DomainGovernResponse(BaseModel):
    transaction_id: str
    domain: str
    active_channels: List[str]
    budget: float
    load: float
    instant_load: float
    fatigue: Optional[float]  # None when load_mode="instant_only"
    reflex_fired: bool
    data_provenance: str
    load_mode: Literal["instant_only", "two_timescale"] = Field(
        "instant_only",
        description="instant_only: fatigue not available, load from current power only. "
                    "two_timescale: fatigue supplied by client, full model applied."
    )
    governance_note: str = ""
    shadow_mode: bool = False
    shadow_blocked: List[str] = []
    voice_request_expires_at: Optional[str] = Field(
        None,
        description="API 1.1+. ISO-8601 timestamp: retry Voice before this time. "
                    "Server is stateless — it does NOT queue or deliver automatically. "
                    "Only set when voice_requested=True and Voice was blocked."
    )
    voice_retry_before: Optional[str] = Field(
        None,
        description="Deprecated (API 1.x). Same value as voice_request_expires_at. "
                    "Will be removed in API 2.0. Use voice_request_expires_at instead.",
        json_schema_extra={"deprecated": True},
    )


class WhyResponse(BaseModel):
    transaction_id: str
    timestamp: str
    domain: Optional[str]
    trace: dict


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
    sustained_load_window_s:   float = Field(900.0, gt=0.0)
    fatigue_ceiling:           float = Field(0.70, ge=0.0, le=1.0)
    attention_floor:           float = Field(0.15, ge=0.0, le=1.0)
    attention_floor_window_s:  float = Field(300.0, gt=0.0)
    recovery_threshold:        float = Field(0.55, ge=0.0, le=1.0)
    recovery_window_s:         float = Field(60.0, gt=0.0)


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
