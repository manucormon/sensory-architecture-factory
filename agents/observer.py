"""
agents/observer.py — Load telemetry observer sub-agent.

Sits alongside the governance engine and watches the load/attention signal
over time. When thresholds are crossed it fires structured alerts to a
configurable callback (log, supervisor system, external API endpoint).

This agent is domain-agnostic: it does not know about power meters or
dispatch queues — it only sees the load/attention arrays that any instance
produces. The governance engine (govern_series) protects the user; this
agent reports outward to whoever needs to know.

Two separate concerns, two separate agents:
  govern_series  → filters what reaches the user        (inward)
  observer       → reports what the user is experiencing (outward)

Alert types
-----------
SUSTAINED_HIGH_LOAD
    load has exceeded threshold for at least window_s consecutive seconds.
    Default: load > 0.80 for 900s (15 min).
    Meaning: the person has had very little cognitive slack for a long time.

FATIGUE_CEILING
    fatigue (accumulated timescale) has crossed a ceiling.
    Default: fatigue > 0.70.
    Meaning: multi-hour accumulated demand is approaching exhaustion.
    Only fires for instances with HAS_MULTI_TIMESCALE_LOAD = True.

ATTENTION_FLOOR
    attention has dropped below a floor for at least window_s seconds.
    Default: attention < 0.15 for 300s (5 min).
    Meaning: essentially no budget left — the person is cognitively maxed.

RECOVERY_DETECTED
    attention has risen above recovery_threshold after a SUSTAINED_HIGH_LOAD
    or ATTENTION_FLOOR alert. Informs the external system the person has
    cognitive slack again — useful for timing supervisor calls or coaching.
    Default: attention > 0.55 sustained for 60s.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional
import numpy as np


# ---------------------------------------------------------------------------
# Alert data structure
# ---------------------------------------------------------------------------

@dataclass
class Alert:
    alert_type: str          # one of the four types above
    sample_index: int        # first sample that triggered the alert
    elapsed_s: float         # seconds into the session at trigger
    load: float              # load value at trigger (or mean over window)
    attention: float         # attention value at trigger (or mean over window)
    fatigue: Optional[float] # fatigue at trigger (None if not available)
    message: str

    def as_dict(self) -> dict:
        return {
            "alert_type":   self.alert_type,
            "sample_index": self.sample_index,
            "elapsed_s":    round(self.elapsed_s, 1),
            "load":         round(self.load, 3),
            "attention":    round(self.attention, 3),
            "fatigue":      round(self.fatigue, 3) if self.fatigue is not None else None,
            "message":      self.message,
        }


# ---------------------------------------------------------------------------
# Observer
# ---------------------------------------------------------------------------

class Observer:
    """
    Stateless batch observer: call scan() with arrays from any instance.

    Parameters
    ----------
    sample_rate_hz : int
        Samples per second — used to convert window_s to sample counts.
    sustained_load_threshold : float
        Load level considered "high" for SUSTAINED_HIGH_LOAD.
    sustained_load_window_s : float
        Seconds above threshold before SUSTAINED_HIGH_LOAD fires.
    fatigue_ceiling : float
        Fatigue level for FATIGUE_CEILING alert.
    attention_floor : float
        Attention level considered critically low.
    attention_floor_window_s : float
        Seconds below floor before ATTENTION_FLOOR fires.
    recovery_threshold : float
        Attention level signalling recovery after an alert.
    recovery_window_s : float
        Seconds above recovery_threshold before RECOVERY_DETECTED fires.
    callback : callable, optional
        Called with each Alert as it is found. Default: print to stdout.
    """

    def __init__(
        self,
        sample_rate_hz: int = 1,
        sustained_load_threshold: float = 0.80,
        sustained_load_window_s: float = 900,
        fatigue_ceiling: float = 0.70,
        attention_floor: float = 0.15,
        attention_floor_window_s: float = 300,
        recovery_threshold: float = 0.55,
        recovery_window_s: float = 60,
        callback: Optional[Callable[[Alert], None]] = None,
    ):
        if any(w <= 0 for w in (sustained_load_window_s,
                                attention_floor_window_s,
                                recovery_window_s)):
            raise ValueError("All window_s parameters must be > 0")
        self.hz = sample_rate_hz
        self.shl_thresh = sustained_load_threshold
        self.shl_window = max(1, int(sustained_load_window_s * sample_rate_hz))
        self.fat_ceil = fatigue_ceiling
        self.attn_floor = attention_floor
        self.attn_window = max(1, int(attention_floor_window_s * sample_rate_hz))
        self.rec_thresh = recovery_threshold
        self.rec_window = max(1, int(recovery_window_s * sample_rate_hz))
        self.callback = callback or _default_callback

    def scan(
        self,
        load: np.ndarray,
        attention: np.ndarray,
        fatigue: Optional[np.ndarray] = None,
    ) -> List[Alert]:
        """
        Scan a complete session and return all alerts in chronological order.

        Args:
            load:      combined load array (0..1), length N.
            attention: attention array (0..1), length N. Should be 1 - load.
            fatigue:   fatigue array (0..1), length N. None for single-timescale instances.

        Returns:
            List of Alert objects, sorted by sample_index.
        """
        alerts: List[Alert] = []
        n = len(load)

        # --- SUSTAINED_HIGH_LOAD ---
        high = (load >= self.shl_thresh).astype(int)
        run = _run_lengths(high)
        alerted_shl = False
        shl_end = -1
        for start, length in run:
            if length >= self.shl_window and start > shl_end:
                idx = start + self.shl_window - 1
                a = Alert(
                    alert_type="SUSTAINED_HIGH_LOAD",
                    sample_index=idx,
                    elapsed_s=idx / self.hz,
                    load=float(load[idx]),
                    attention=float(attention[idx]),
                    fatigue=float(fatigue[idx]) if fatigue is not None else None,
                    message=(
                        f"Load ≥ {self.shl_thresh:.0%} for "
                        f"{self.shl_window // self.hz // 60} min. "
                        "Consider intervention or workload redistribution."
                    ),
                )
                alerts.append(a)
                self.callback(a)
                alerted_shl = True
                shl_end = start + length

        # --- FATIGUE_CEILING (fires once per crossing, not on oscillation) ---
        if fatigue is not None:
            crossings = np.where(
                (fatigue[1:] >= self.fat_ceil) & (fatigue[:-1] < self.fat_ceil)
            )[0]
            for idx in crossings[:1]:  # first crossing only
                # idx points to the sample BEFORE the crossing; idx+1 is the
                # first sample at or above the ceiling.
                trigger = int(idx) + 1
                a = Alert(
                    alert_type="FATIGUE_CEILING",
                    sample_index=trigger,
                    elapsed_s=trigger / self.hz,
                    load=float(load[trigger]),
                    attention=float(attention[trigger]),
                    fatigue=float(fatigue[trigger]),
                    message=(
                        f"Accumulated fatigue crossed {self.fat_ceil:.0%}. "
                        "Multi-hour demand is near exhaustion — schedule a break."
                    ),
                )
                alerts.append(a)
                self.callback(a)

        # --- ATTENTION_FLOOR ---
        low = (attention <= self.attn_floor).astype(int)
        run_low = _run_lengths(low)
        for start, length in run_low:
            if length >= self.attn_window:
                idx = start + self.attn_window - 1
                a = Alert(
                    alert_type="ATTENTION_FLOOR",
                    sample_index=idx,
                    elapsed_s=idx / self.hz,
                    load=float(load[idx]),
                    attention=float(attention[idx]),
                    fatigue=float(fatigue[idx]) if fatigue is not None else None,
                    message=(
                        f"Attention ≤ {self.attn_floor:.0%} for "
                        f"{self.attn_window // self.hz // 60} min. "
                        "Cognitive budget critically low — immediate review."
                    ),
                )
                alerts.append(a)
                self.callback(a)

        # --- RECOVERY_DETECTED ---
        high_rec = (attention >= self.rec_thresh).astype(int)
        run_rec = _run_lengths(high_rec)
        alerted_indices = {a.sample_index for a in alerts
                           if a.alert_type in ("SUSTAINED_HIGH_LOAD", "ATTENTION_FLOOR")}
        if alerted_indices:
            last_alert_idx = max(alerted_indices)
            for start, length in run_rec:
                if length >= self.rec_window and start > last_alert_idx:
                    idx = start + self.rec_window - 1
                    a = Alert(
                        alert_type="RECOVERY_DETECTED",
                        sample_index=idx,
                        elapsed_s=idx / self.hz,
                        load=float(load[idx]),
                        attention=float(attention[idx]),
                        fatigue=float(fatigue[idx]) if fatigue is not None else None,
                        message=(
                            f"Attention recovered above {self.rec_thresh:.0%}. "
                            "Cognitive slack available — safe window for coaching or handoff."
                        ),
                    )
                    alerts.append(a)
                    self.callback(a)
                    break  # one recovery notification per session is enough

        alerts.sort(key=lambda a: a.sample_index)
        return alerts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_lengths(binary: np.ndarray):
    """
    Return list of (start_index, run_length) for runs of 1s in a binary array.
    """
    if len(binary) == 0:
        return []
    padded = np.concatenate([[0], binary, [0]])
    changes = np.diff(padded)
    starts = np.where(changes == 1)[0]
    ends = np.where(changes == -1)[0]
    return list(zip(starts.tolist(), (ends - starts).tolist()))


def _default_callback(alert: Alert) -> None:
    elapsed_min = alert.elapsed_s / 60
    print(f"[OBSERVER] {alert.alert_type:25s} | "
          f"t={elapsed_min:5.1f}min | "
          f"load={alert.load:.2f} attn={alert.attention:.2f}"
          + (f" fatigue={alert.fatigue:.2f}" if alert.fatigue is not None else "")
          + f" | {alert.message}")
