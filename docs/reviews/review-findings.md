# Review Findings Tracker

Updated per review. Read this file first in every PR review session (~30 lines).

## Open Findings

| ID | Severity | Status | Fixed In | Description |
|----|----------|--------|----------|-------------|
| L-1 | Medium | FIXED | bugfix/l1-suspend-reason | Suspend reason lookup uses wrong key type |
| L-5 | Low | OPEN | — | Profile `idp` matching may silently fail |
| D-1 | Medium | OPEN | — | No binary event fixture |
| D-2 | Low | OPEN | — | `partNumber` missing from drift check |
| S-1 | Medium | OPEN | — | state_class=MEASUREMENT on discrete events |
| S-2 | Low | DEFERRED | — | Inconsistent insulin unit strings (next major) |
| S-3 | Medium | OPEN | — | Daily totals use MEASUREMENT |
| S-4 | Low | OPEN | — | Threshold sensors missing BLOOD_GLUCOSE |
| S-5 | Low | OPEN | — | suggested_display_precision not set |

## Accepted / Closed

| ID | Status | Notes |
|----|--------|-------|
| L-2 | ACCEPTED | resp.json() not wrapped — caught by broad except |
| L-3 | ACCEPTED | CGM usage calc works via min() cap |
| L-4 | ACCEPTED | Timestamp approach correct, documented |
| L-6 | ACCEPTED | 0.0555 vs 0.05551 — clinically insignificant |
| D-3 | OK | PII excluded by design |
| D-4 | OK | pumper_info minimal by design |
| D-5 | OK | ControlIQ returns 404 |

## File Checksums (baseline: 2026-03-12)

Compare before reading files. Skip unchanged files.

```
7f8473fc __init__.py
37a6952e tandem_api.py
688cabcf const.py
f61f7695 sensor.py
```

**Status values:** OPEN, ACCEPTED, FIXED, DEFERRED, OK
