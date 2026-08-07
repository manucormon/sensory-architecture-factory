"""
ENMAX instance — dispatcher channel config.

Domain: ENMAX Energy (Calgary) field-crew dispatch. A dispatcher manages
multiple simultaneous incidents (power outages, gas leaks, downed lines),
coordinates field crews via radio, monitors a live incident map, and
escalates P1 emergencies (life-safety) to supervisors and emergency services.

CONTRACT DECLARATIONS:
  HAS_RECOVERY_WINDOW = True
    Both ruled and event-based. Ruled: shift handoff at 8h is a hard break.
    Event-based: after a storm clears, incident volume drops sharply — natural
    lull before the next event cluster. A dispatcher in the lull has budget.

  HAS_MULTI_TIMESCALE_LOAD = True
    Instant: active incident count + P1 flag drives moment-to-moment demand.
    Accumulated: 12-hour shift fatigue degrades decision quality over time —
    the same incident volume at hour 10 is harder than at hour 2.

CHANNEL COST RATIONALE:
  Touch (0.00, priority 0) — P1 reflex. Gas leak, transformer fire, person
    trapped: Touch fires regardless of budget. Zero cost by design — always
    admitted, budget-bypassing.

  Sound (0.10, priority 1) — radio chatter from field crews. Constant, low-
    level, directional audio. Dispatcher must hear it but it's background —
    lighter than F1's earcon (no sudden rival-entry moment; crew check-ins
    are expected). Cost 0.10.

  Vision (0.30, priority 2) — incident map + crew position overlay. The
    primary workspace. A dispatcher's eyes are on the map most of the time —
    higher cost than cycling (longer fixation, denser information). Cost 0.30.

  Presence (0.10, priority 3) — queue depth indicator + shift clock. Ambient
    dashboard: how many calls waiting, how long into shift. Low cognitive
    demand individually, but meaningful for self-regulation. Cost 0.10.

  Voice (0.20, priority 4) — supervisor escalation + cross-dispatch
    coordination. Not constant (unlike cycling's directeur sportif). A Voice
    request is a deliberate act — peer dispatcher asking for resource share,
    supervisor asking for status. Cost 0.20.

TUNING VERIFICATION:
  At peak incident load (P1 active, queue depth high): attention approaches
  zero → Sound+Vision+Presence = 0.50, remaining < Voice(0.20) → Voice stays
  closed. Supervisor cannot break through except via P1 Touch reflex. Correct.

  During lull (queue empty, no P1): attention high → all channels open
  including Voice. Supervisor coaching arrives exactly here. Correct.
"""

from core.channels_schema import CORE_VERSION

CORE_VERSION_REQUIRED = "1.0"
assert CORE_VERSION == CORE_VERSION_REQUIRED, (
    f"core version mismatch: requires {CORE_VERSION_REQUIRED}, core is {CORE_VERSION}."
)

SAMPLE_RATE_HZ = 1   # 1 sample per second — dispatch events are second-granularity

HAS_RECOVERY_WINDOW = True
HAS_MULTI_TIMESCALE_LOAD = True

CHANNELS = [
    # name        priority  cost   note
    ("Touch",      0,       0.00, "P1 reflex: gas leak / transformer fire / person trapped"),
    ("Sound",      1,       0.10, "field crew radio — constant, directional, expected"),
    ("Vision",     2,       0.30, "incident map + crew positions — primary workspace"),
    ("Presence",   3,       0.10, "queue depth + shift clock — ambient self-regulation"),
    ("Voice",      4,       0.20, "supervisor escalation / cross-dispatch coordination"),
]
