# Architecture Decision Records

Lightweight records of key design decisions for ha-tandem-pump.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](ADR-001-lts-data-paths.md) | Long-Term Statistics: Two Data Paths | Accepted |
| [ADR-002](ADR-002-state-class-strategy.md) | Sensor state_class Strategy | Accepted |
| [ADR-003](ADR-003-polling-and-freshness.md) | Polling Interval and Data Freshness | Accepted |
| [ADR-004](ADR-004-error-handling.md) | Coordinator Error Handling Philosophy | Accepted |
| [ADR-005](ADR-005-timezone-handling.md) | Pump Timestamp and Timezone Handling | Accepted |
| [ADR-006](ADR-006-api-contract-management.md) | API Contract Management | Accepted |

## Template

```markdown
# ADR-NNN: Title

**Date:** YYYY-MM-DD
**Status:** Accepted | Superseded by ADR-NNN | Deprecated

## Context
What problem or need prompted this decision?

## Decision
What did we decide, and what are the key design choices?

## Alternatives Considered
What other approaches were evaluated and why were they rejected?

## Consequences
What are the trade-offs, risks, and follow-on constraints?
```

## Notes

- ADRs are **immutable once accepted** — never edit a decision after the fact. If the decision changes, create a new ADR marked "Supersedes ADR-NNN" and update the old one to "Superseded by ADR-NNN".
- ADRs live alongside the code — check `docs/reviews/review-findings.md` for tactical findings that may eventually become ADRs.
- For cross-project patterns, see `~/Code/develop/homelab-docs/` (future: extract template there).
