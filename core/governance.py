"""
Sensory Architecture — Governance Core (domain-agnostic)

This is the mold. It decides which channels speak, given only an
attention budget and a reflex signal for that instant. It has no
knowledge of F1, telemetry, or any specific domain — that knowledge
lives in each instance's domain_adapter (see instances/<domain>/).

Behavior is unchanged from the original governance_engine.py's
reflex_trigger()/govern() logic — this is a mechanical extraction,
not a redesign.
"""

import numpy as np


def norm(s, lo_p=5, hi_p=95):
    """Scale to 0..1 using percentiles so absolute units don't matter."""
    lo, hi = np.nanpercentile(s, lo_p), np.nanpercentile(s, hi_p)
    if hi - lo < 1e-9:
        return np.zeros_like(s, dtype=float)
    return np.clip((s - lo) / (hi - lo), 0, 1)


def govern(channels, budget, reflex_active):
    """
    Decide which channels speak for a single sample.

    channels: list of (name, priority, cost, note) — this instance's
              tuned schema (see instances/<domain>/config.py)
    budget: float, this sample's available attention (0..1)
    reflex_active: bool, whether this instance's reflex trigger fired
                   at this sample

    Returns: list of channel names allowed to speak, admitted in
    priority order until the budget runs out. "Touch" is treated as
    the reflex channel by convention: it never draws from the budget,
    it only fires when reflex_active is True (fast path).
    """
    active = []
    remaining = budget
    for name, prio, cost, _ in sorted(channels, key=lambda c: c[1]):
        if name == "Touch":
            if reflex_active:
                active.append(name)
            continue
        if remaining >= cost:
            active.append(name)
            remaining -= cost
    return active


def govern_series(channels, attention, reflex_flags):
    """Vectorized convenience: govern() applied across a full session."""
    return [govern(channels, attention[i], reflex_flags[i])
            for i in range(len(attention))]


# --------------------------------------------------------------------
# Hybrid reactive/proactive layer for Voice (added — does not change
# govern()/govern_series() above, which stay exactly as verified
# against the original F1 output).
#
# govern() treats Voice like any other push channel: auto-admitted
# whenever the budget allows it, with no notion of whether the human
# actually asked for anything. govern_hybrid() replaces that with two
# tiers, matching the design discussion (safety > sterile-cockpit
# precedent > nuisance-alert risk of a generic ambient indicator):
#
#   urgent pull (pulse)   — bypasses the budget entirely, like Touch.
#                            Reserved for a real risk condition behind
#                            the ask, supplied by the domain adapter —
#                            never assumed here.
#   elective pull (queue) — stays budget-gated. If blocked, it queues
#                            instead of vanishing, and resolves the
#                            oldest pending request first once budget
#                            reopens — one at a time, so the payoff
#                            moment doesn't recreate the overload the
#                            gated moment just avoided.
# --------------------------------------------------------------------

class VoiceQueue:
    """
    Holds elective Voice requests blocked by budget; resolves the
    oldest one first once budget reopens. Requests older than
    `expiry_samples` are dropped instead of delivered late — a stale
    answer to "what happened three corners ago" is worse than none.
    """

    def __init__(self, expiry_samples):
        self.expiry_samples = expiry_samples
        self._pending = []  # sample indices at which a request was queued

    def prune(self, i):
        """Drop requests older than expiry_samples. Call once per sample, first."""
        self._pending = [q for q in self._pending if i - q <= self.expiry_samples]

    def add(self, i):
        self._pending.append(i)

    def deliver(self):
        """Pop the oldest pending request if there is one. Returns True if resolved."""
        if self._pending:
            self._pending.pop(0)
            return True
        return False

    @property
    def waiting(self):
        return len(self._pending)


def govern_hybrid(channels, budget, reflex_active, *,
                   voice_requested=False, risk_present=False,
                   queue=None, i=None):
    """
    Same as govern(), but Voice is decided by the reactive/pull layer
    instead of being auto-admitted by budget alone.

    voice_requested: bool, the human initiated a query this sample.
    risk_present: bool, domain-supplied — true only for a genuine
                  safety-relevant condition behind the ask, never for
                  curiosity. Drives the urgent pulse bypass.
    queue: an optional VoiceQueue for deferring elective requests.
    i: this sample's index, required if queue is given.

    Design note worth flagging: with Voice's cost this high (0.70) and
    lowest priority, Sound/Vision/Presence can eat most of the budget
    before Voice is even considered — under F1's tuned values, that
    means a plain "is there enough budget left" check can stay false
    almost indefinitely, even wide open. So once something is queued,
    a pending request gets FIRST claim on the raw budget instead of
    competing for the leftovers: resolving a promise outranks granting
    a fresh, lower-stakes channel. That's a real design choice, not a
    neutral default — worth deciding on purpose, not by accident.

    Note: without voice_requested/queue, Voice is simply never
    admitted here — unlike govern(), which admits it by budget alone
    with no request signal at all. That gap is intentional: Voice is
    the query channel, so "nobody asked" now means "stays silent."
    """
    if queue is not None and i is not None:
        queue.prune(i)

    voice = next((c for c in channels if c[0] == "Voice"), None)
    non_voice = [c for c in channels if c[0] != "Voice"]
    if voice is None:
        return govern(non_voice, budget, reflex_active)
    _, _, voice_cost, _ = voice

    if voice_requested and risk_present:
        active = govern(non_voice, budget, reflex_active)
        active.append("Voice:pulse")   # urgent bypass — zero cost, no budget check
        return active

    pending = queue is not None and queue.waiting > 0

    if pending and budget >= voice_cost:
        active = govern(non_voice, budget - voice_cost, reflex_active)
        queue.deliver()
        active.append("Voice")
        return active

    active = govern(non_voice, budget, reflex_active)
    spent = sum(cost for name, _, cost, _ in channels
                if name in active and name != "Touch")
    remaining = budget - spent
    budget_ok = remaining >= voice_cost

    if voice_requested and budget_ok and not pending:
        active.append("Voice")
        return active

    if voice_requested and queue is not None and i is not None:
        queue.add(i)

    return active


# --------------------------------------------------------------------
# Explainability layer — govern_explain()
#
# Runs the same arbitration logic as govern_hybrid() but also returns
# a structured trace capturing every channel decision and its reason.
# Used by the /why/{transaction_id} API endpoint so auditors can see
# exactly why each channel was admitted or blocked at any given sample.
# --------------------------------------------------------------------

def govern_explain(channels, budget, reflex_active, *,
                   voice_requested=False, risk_present=False):
    """
    Same arbitration as govern_hybrid() (no queue, single sample).
    Returns (active_channels, trace) where trace is a dict with:
      - budget_in, reflex_active, voice_requested, risk_present
      - channels: list of per-channel decisions with reason
      - voice_path: "urgent_pulse" | "elective_admitted" |
                    "elective_blocked" | "not_requested"
      - active_channels, budget_remaining
    """
    trace = {
        "budget_in": round(budget, 4),
        "reflex_active": reflex_active,
        "voice_requested": voice_requested,
        "risk_present": risk_present,
        "channels": [],
        "voice_path": None,
    }

    voice = next((c for c in channels if c[0] == "Voice"), None)
    non_voice = [c for c in channels if c[0] != "Voice"]

    active = []
    remaining = budget

    for name, prio, cost, _ in sorted(non_voice, key=lambda c: c[1]):
        if name == "Touch":
            admitted = reflex_active
            trace["channels"].append({
                "name": name, "priority": prio, "cost": 0.0,
                "admitted": admitted,
                "reason": "reflex_active" if admitted else "reflex_inactive",
                "budget_after": round(remaining, 4),
            })
            if admitted:
                active.append(name)
            continue
        admitted = remaining >= cost
        trace["channels"].append({
            "name": name, "priority": prio, "cost": cost,
            "admitted": admitted,
            "reason": "budget_ok" if admitted else "budget_exhausted",
            "budget_after": round(remaining - cost if admitted else remaining, 4),
        })
        if admitted:
            active.append(name)
            remaining -= cost

    if voice is not None:
        _, vprio, vcost, _ = voice
        if voice_requested and risk_present:
            active.append("Voice:pulse")
            trace["channels"].append({
                "name": "Voice", "priority": vprio, "cost": 0.0,
                "admitted": True, "reason": "urgent_bypass_risk_present",
                "budget_after": round(remaining, 4),
            })
            trace["voice_path"] = "urgent_pulse"
        elif voice_requested and remaining >= vcost:
            active.append("Voice")
            trace["channels"].append({
                "name": "Voice", "priority": vprio, "cost": vcost,
                "admitted": True, "reason": "budget_ok",
                "budget_after": round(remaining - vcost, 4),
            })
            trace["voice_path"] = "elective_admitted"
        elif voice_requested:
            trace["channels"].append({
                "name": "Voice", "priority": vprio, "cost": vcost,
                "admitted": False, "reason": "budget_exhausted",
                "budget_after": round(remaining, 4),
            })
            trace["voice_path"] = "elective_blocked"
        else:
            trace["channels"].append({
                "name": "Voice", "priority": vprio, "cost": vcost,
                "admitted": False, "reason": "not_requested",
                "budget_after": round(remaining, 4),
            })
            trace["voice_path"] = "not_requested"

    trace["active_channels"] = active
    trace["budget_remaining"] = round(remaining, 4)
    return active, trace
