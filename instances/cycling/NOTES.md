# NOTES — cycling instance

Status: VERIFIED. See instance_registry.json — last_verified 2026-08-07.

Upgraded from DECLARED synthetic data to real GoldenCheetah OpenData
(OSF DOI: 10.17605/OSF.IO/6HFPZ). Anonymised cyclist, mountain loop,
2019-12-28. 79 min, 339m elevation, 4762 samples at 1Hz.

## Data provenance (per instance_registry.json)

  power_w       — REAL (power meter)
  gradient_pct  — MEASURED (GPS altitude, 60s central-difference window)
  phase         — PROXY (gradient threshold: >2% → climb, <-2% → descent)
  FTP = 240W    — PROXY (95% of best 20-min rolling power — industry
                  standard estimate, not a lab VO2 test)

## Contract declarations

  HAS_RECOVERY_WINDOW      = True  — geographic (descent segments)
  HAS_MULTI_TIMESCALE_LOAD = True  — instant (power/FTP) + TSS-inspired fatigue
  HAS_REFLEX               = False — no crash labels in real data
  HAS_PERCEPTION           = True  — perception.py validates gradient_pct and phase

## Key verified finding

Voice opens on descent (coasting, power ≈ 0W) and closes at climb peak.
Confirmed against real power-meter trace — not a synthetic assumption.
Tests: test_voice_opens_on_descent_with_fresh_request(),
       test_voice_closed_at_climb_peak() in tests/test_cycling_instance.py.
