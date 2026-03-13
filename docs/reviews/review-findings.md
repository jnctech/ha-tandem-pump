# Review Findings Tracker

Updated per review. Read this file first in every PR review session (~30 lines).

## Open Findings

| ID | Severity | Status | Fixed In | Description |
|----|----------|--------|----------|-------------|
| L-5 | Low | OPEN | — | Profile `idp` matching may silently fail |
| D-1 | Medium | OPEN | — | No binary event fixture |
| D-2 | Low | OPEN | — | `partNumber` missing from drift check |
| S-2 | Low | DEFERRED | — | Inconsistent insulin unit strings (next major) |
| S-4 | Low | OPEN | — | Threshold sensors missing BLOOD_GLUCOSE |
| S-5 | Low | OPEN | — | suggested_display_precision not set |

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

## File Checksums (updated: 2026-03-13, post PR #46)

Compare before reading files. Skip unchanged files.

```
76aaa7aa __init__.py
b6fe32de tandem_api.py
a38419d6 const.py
85c251a2 sensor.py
```

**Status values:** OPEN, ACCEPTED, FIXED, DEFERRED, OK
