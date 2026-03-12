# AI Review Audit Trail

Structured AI reviews run against this codebase. Each review produces a report in this directory.

## Review Types

| Type | Trigger | Model | Scope |
|------|---------|-------|-------|
| Logic correctness | PR touches coordinator or API client | Opus | Changed files + their test files |
| API contract drift | PR touches `tandem_api.py` | Opus | `tandem_api.py` + API response fixtures |
| Sensor entity correctness | PR adds/modifies sensors | Sonnet | `const.py` + `sensor.py` |
| Full release review | Before each release tag | Opus (single session) | All 3 reviews scoped to changes since last release |
| Baseline | One-time, full codebase | Opus | All source files |

## Running a Review

Open a **new** Opus session (do not run in an active implementation session — context pollution degrades quality).

```
Read CLAUDE.md then run a full [review type] review against [files].
Output findings and actions taken to docs/reviews/review-[scope]-YYYY-MM-DD.md.
Include token usage at the end of the report.
```

## Token Usage Log

Track cost vs value here. After 2–3 reviews of each type, assess whether findings justify token cost.

| Date | Review Type | Model | Files Reviewed | Tokens (approx) | Findings |
|------|-------------|-------|----------------|-----------------|----------|

## Review File Naming

```
docs/reviews/review-baseline-YYYY-MM-DD.md
docs/reviews/review-logic-YYYY-MM-DD.md
docs/reviews/review-api-drift-YYYY-MM-DD.md
docs/reviews/review-sensor-correctness-YYYY-MM-DD.md
docs/reviews/review-release-vX.Y.Z.md
```
