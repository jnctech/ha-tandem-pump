# Review Findings Tracker

Updated per review. Read this file first in every PR review session (~30 lines).

## Open Findings

| ID | Severity | Status | Fixed In | Description |
|----|----------|--------|----------|-------------|
| L-5 | Low | OPEN | — | Profile `idp` matching may silently fail |
| B-1 | Low | OPEN | — | Missing test: msg1+msg3 without msg2 — join works but msg2 fields are None in attrs |
| B-2 | Low | OPEN | — | carb_ratio 1000x multiplier from tconnectsync spec — cannot validate without real capture |
| D-1 | Medium | OPEN | — | No binary event fixture |
| C-1 | High | FIXED | feature/cgm-g7-libre2-phase3 | Magic event IDs in coordinator — replaced ALL with EVT_* constants from tandem_api |
| C-2 | High | FIXED | feature/cgm-g7-libre2-phase3 | Daily status `except Exception` + `warning` — narrowed to `(KeyError, TypeError, IndexError)` + `error` + event count |
| C-3 | Medium | FIXED | feature/cgm-g7-libre2-phase3 | Unknown sensor type fallback silent — added `_LOGGER.info` when sensor_type starts with "Unknown" |
| C-4 | Medium | DEFERRED | — | No per-event struct error isolation in decoder (pre-existing, all phases) |
| C-5 | Medium | FIXED | PR #51 | Duplicate decode logic: event 399 is copy of 256 — extracted `_decode_cgm_gxb_layout` shared helper |
| A-1 | Low | FIXED | feature/alerts-alarms-phase2 | payload invariant undocumented — comment added; EVENT_LEN guard makes struct.error impossible in practice |
| A-2 | High | FIXED | feature/alerts-alarms-phase2 | alarm parse catch used `warning` not `error`; no event counts in log — changed to `error` + added counts |
| A-3 | Important | FIXED | feature/alerts-alarms-phase2 | active_alerts_count: MEASUREMENT + UNAVAILABLE fallback causes LTS gaps — changed to state_class=None |
| A-4 | Low | FIXED | feature/alerts-alarms-phase2 | MalfunctionActivated clearing assumption undocumented — comment added |
| A-5 | Low | FIXED | feature/alerts-alarms-phase2 | `recent` list repeat-activation semantics undocumented — comment added |
| A-6 | Low | FIXED | feature/alerts-alarms-phase2 | malfunction test asserted `is not UNAVAILABLE` not name — strengthened to `== "Software Error"` |
| A-7 | Low | FIXED | feature/alerts-alarms-phase2 | missing test: MalfunctionActivated + AlarmCleared → count=0 — test added |
| D-2 | Low | FIXED | PR #48 | `partNumber` missing from drift check — added to fixture _drift_check |
| S-2 | Low | FIXED | PR #47 | Inconsistent insulin unit strings — "U" → UNITS constant, "mV" → UnitOfElectricPotential, "kg" → UnitOfMass |
| S-4 | Low | ACCEPTED | — | Threshold sensors: no HA BLOOD_GLUCOSE device class exists; device_class=None is correct |
| S-5 | Low | FIXED | PR #48 | suggested_display_precision added to 25 Tandem sensors (22 initial + 3 from code review) |
| S-6 | Medium | FIXED | PR #47 | Duration sensors: bare "h"/"m" → UnitOfTime, added DURATION device class |
| S-7 | Medium | FIXED | PR #47 | Battery sensors (conduit, CGM): missing SensorDeviceClass.BATTERY |
| S-8 | Medium | FIXED | PR #47 | Device info sensors (6 Carelink): missing EntityCategory.DIAGNOSTIC |
| S-9 | Medium | FIXED | PR #47 | Active insulin, reservoir, max basal: MEASUREMENT with no unit → added units |
| S-10 | High | FIXED | PR #47 | sgBelowLimit: was unitless, incorrectly assigned PERCENT → fixed to MGDL |
| S-11 | Medium | FIXED | PR #47 | DailyBasal voltage: raw ADC (25344) not millivolts → removed, ShelfMode only |
| P-1 | Medium | FIXED | PR #47 | PII: "name" and "birthdate" missing from redaction fields |

## Accepted / Closed

| ID | Status | Notes |
|----|--------|-------|
| L-1 | FIXED | Suspend reason lookup — PR #39, merged 2026-03-12 |
| S-1 | FIXED | state_class on discrete events — PR #40, merged 2026-03-13 |
| S-3 | FIXED | Daily totals MEASUREMENT — PR #40, merged 2026-03-13 |
| L-2 | ACCEPTED | resp.json() not wrapped — caught by broad except |
| L-3 | ACCEPTED | CGM usage calc works via min() cap |
| L-4 | ACCEPTED | Timestamp approach correct, documented |
| L-6 | ACCEPTED | 0.0555 vs 0.05551 — clinically insignificant |
| D-3 | OK | PII excluded by design |
| D-4 | OK | pumper_info minimal by design |
| D-5 | OK | ControlIQ returns 404 |

## File Checksums (updated: 2026-03-13, post PR #53 bugfix/bolus-calc-attrs-not-sensor)

Compare before reading files. Skip unchanged files.

```
ec093426 __init__.py
7f1a5d40 tandem_api.py
022f7643 const.py
d0a63142 sensor.py
```

**Status values:** OPEN, ACCEPTED, FIXED, DEFERRED, OK
