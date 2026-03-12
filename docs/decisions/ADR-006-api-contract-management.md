# ADR-006: API Contract Management

**Date:** 2026-03-13
**Status:** Accepted

## Context

The Tandem Source / Carelink API is **undocumented and reverse-engineered**. There are no official API docs, no versioning guarantees, and no change notifications. The API can change shape without warning when Tandem updates their cloud infrastructure.

Key risks:
- Fields accessed in code may disappear from API responses
- New fields may appear in responses that could provide useful data
- Existing fields may change type or value encoding
- ControlIQ endpoints return 404 (confirmed — these are permanently unavailable in this API path)

## Decision

Three-layer API contract management:

**Layer 1: Known-good fixture** (`tests/fixtures/known_good_api_response.json`)
A captured real API response used as the reference shape for all contract tests. Updated manually when a fresh API capture reveals structural changes. This is the ground truth for "what the API currently returns".

**Layer 2: Automated drift detection** (`scripts/check_api_drift.py` + `tests/test_api_drift.py`)
Run on every PR that touches `tandem_api.py` or `__init__.py`. Compares the fixture against fields accessed in code and reports:
- Fields accessed in code but missing from the fixture (new assumptions)
- Fields in the fixture not accessed by code (potential missed data)

**Layer 3: Opus API contract review (Review 2)**
Triggered when a fresh API capture reveals new structural changes. Uses a structured prompt against `tandem_api.py` + the fixture to identify type mismatches, wrong nesting, and enum value assumptions. See CLAUDE.md AI Review Checkpoints.

## Alternatives Considered

**Mock API in tests**
Rejected as the sole approach. Mock tests can pass while encoding the same wrong assumption as the code — if the fixture itself is wrong, mock tests do not catch it. The fixture is used directly (not mocked) in `test_api_drift.py` to ensure code-to-fixture alignment.

**OpenAPI schema generation**
Not applicable. No official schema exists for this API, and maintaining an auto-generated schema for a reverse-engineered API adds overhead without benefit.

**ControlIQ endpoints**
Explicitly out of scope. ControlIQ API endpoints return 404 and are confirmed unavailable through the Carelink path. Do not add code that depends on them.

## Consequences

- `tests/fixtures/known_good_api_response.json` must be updated when real API responses change shape — this is a manual step requiring a test credential capture
- `scripts/check_api_drift.py` is run manually as part of the pre-PR checklist when `tandem_api.py` changes; `tests/test_api_drift.py` runs automatically in CI
- Drift findings D-1 (no binary event fixture) and D-2 (partNumber missing from drift check) are tracked in `docs/reviews/review-findings.md` as open low-priority items
- Sessions with access to real credentials can run `python scripts/check_api_drift.py` to get a current drift report
