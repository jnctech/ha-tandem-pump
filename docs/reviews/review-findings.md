# Review Findings Tracker

Updated per review. Read this file first in every PR review session (~30 lines).

## Open Findings

| ID | Severity | Status | Fixed In | Description |
|----|----------|--------|----------|-------------|
| L-5 | Low | OPEN | — | Profile `idp` matching may silently fail |
| D-1 | Medium | OPEN | — | No binary event fixture |
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

## File Checksums (updated: 2026-03-13, post PR #48)

Compare before reading files. Skip unchanged files.

```
2eb0d3ee __init__.py
320a4b85 tandem_api.py
a252e7c1 const.py
85c251a2 sensor.py
```

**Status values:** OPEN, ACCEPTED, FIXED, DEFERRED, OK
