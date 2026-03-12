# ADR-004: Coordinator Error Handling Philosophy

**Date:** 2026-03-13
**Status:** Accepted

## Context

The coordinator's `_async_update_data()` method fetches data from the API and parses the response into sensor values. Several things can fail:

- Network errors (API unreachable, timeout)
- Authentication errors (expired session, invalid credentials)
- Parse errors (API response changed shape, missing fields)
- Unexpected data types or None values in deeply nested response

HA's `DataUpdateCoordinator` pattern handles errors as follows:
- If `_async_update_data()` raises `UpdateFailed`, HA marks all dependent entities as `unavailable`
- If it raises any other exception, HA logs an error and marks all entities `unavailable`
- If it returns successfully (even with partial data), entities remain `available`

Baseline review finding L-2 identified broad `except Exception` blocks in the coordinator.

## Decision

Use **broad exception handling** in the coordinator's top-level update path with structured logging. Allow specific sub-functions to raise naturally, catch at the coordinator boundary.

Rationale:
1. A parse error in one sensor field (e.g., a missing nested key) should not mark all 99 sensors as `unavailable`. HA unavailability triggers "entity unavailable" notifications and breaks automations.
2. Stale data is generally preferable to `unavailable` for a monitoring-only integration — the pump data does not change rapidly and a missed update is recoverable.
3. The `sensor.tandem_data_age` sensor makes data staleness explicit, so users can detect when the integration has stopped updating.

Specific error boundaries:
- **API network/auth errors** → raise `UpdateFailed` (HA marks unavailable — correct, the data source is gone)
- **Parse errors on individual fields** → log warning, use `None` or previous value, do not propagate
- **`_import_statistics()` failures per type** → individual try/except per stat type so one failure does not prevent others

## Alternatives Considered

**Strict exception propagation (raise on any error)**
Rejected. A single API response field changing shape would mark all 99 sensors unavailable and trigger user-facing alerts. For a monitoring integration, this is disproportionate — the underlying pump data has not changed, only its representation in the API response.

**Silent failure (catch all, log nothing)**
Rejected. This was flagged by `silent-failure-hunter` review as a risk. All caught exceptions are logged at WARNING level with context, so failures are diagnosable from HA logs.

## Consequences

- Broad `except Exception` blocks are intentional defensive patterns — do not remove them during refactoring
- The `pr-review-toolkit:silent-failure-hunter` check is mandatory in the pre-PR checklist to catch new silent failures introduced during development
- Error handling strategy is not marked as a code smell in SonarCloud (exceptions are logged, not swallowed)
- CLAUDE.md: **Do NOT run code-simplifier on `fix/security-*` branches** — it reverts intentional defensive patterns
