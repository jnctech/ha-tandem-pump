# AI Review Workflow — ha-tandem-pump

## AI Review Checkpoints

Three structured reviews cover gaps that automated tooling (Ruff, Bandit, SonarCloud, pytest) cannot catch.

**Why these exist:** Automated tools catch syntax, style, known vulnerability patterns, and complexity. They cannot catch:
- Logic errors where tests pass because the tests encode the same wrong assumption as the code
- API contract drift on an undocumented, reverse-engineered API
- Sensor metadata errors (wrong unit, device class, state class) that produce valid Python but incorrect HA behaviour

### Review 1: Logic correctness
Trigger: PR touches coordinator (`__init__.py`) or API client (`tandem_api.py`)
Model: Opus | Scope: Changed files + their test files

Prompt:
```
Review the following files for logic correctness only. Do not suggest stylistic
changes, formatting improvements, or anything covered by Ruff, Bandit, or SonarCloud.

Focus on:
- Logic errors and incorrect assumptions in coordinator data parsing
- Edge cases not covered by the test files (especially None/missing field handling)
- Incorrect handling of API response fields (wrong type, wrong key, wrong nesting)
- Cases where tests pass because they encode the same wrong assumption as the code
- Error paths that silently swallow exceptions or return misleading defaults

Files to review: [paste changed files + their test files]
Reference: tests/fixtures/known_good_api_response.json for expected API shape

Return findings as a numbered list. For each finding state:
- File and line reference
- What the logic does
- What it should do
- Suggested fix

If no issues are found, state that explicitly.
```

### Review 2: API contract drift
Trigger: PR touches `tandem_api.py`
Model: Opus | Scope: `tandem_api.py` + `tests/fixtures/known_good_api_response.json`
Note: `scripts/check_api_drift.py` handles per-PR static drift detection automatically.
The Opus review is for when a fresh API capture reveals new structural changes.

Prompt:
```
Review tandem_api.py against the known-good API fixture for contract drift.

Focus on:
- Fields accessed in code but missing from the fixture (new assumptions)
- Fields in the fixture not accessed by code (potential missed data)
- Type mismatches between what the code expects and what the fixture shows
- Any hardcoded field names that don't match the fixture structure
- Decoder functions that assume specific value formats (string vs int, enum values)

Files to review: custom_components/carelink/tandem_api.py,
  tests/fixtures/known_good_api_response.json
Reference: scripts/check_api_drift.py output for automated drift results

Return findings as a numbered list with field name, expected type/value, actual type/value.
If no drift is found, state that explicitly.
```

### Review 3: Sensor entity correctness
Trigger: PR adds or modifies sensors in `const.py` or `sensor.py`
Model: Sonnet | Scope: `const.py` + `sensor.py`
Catches: wrong unit_of_measurement, device_class, state_class, suggested_display_precision

Prompt:
```
Review sensor definitions in const.py and entity creation in sensor.py for
metadata correctness against Home Assistant sensor platform conventions.

For each sensor check:
- device_class matches the data type (e.g., BLOOD_GLUCOSE for mg/dL values,
  DURATION for time values, not generic None when a specific class exists)
- state_class is appropriate: MEASUREMENT for continuous readings,
  TOTAL for accumulators, None for discrete events and daily-reset totals
- unit_of_measurement matches the device_class expectations
- suggested_display_precision is set for decimal values
- entity_category is correct (DIAGNOSTIC for metadata, None for primary data)

Files to review: custom_components/carelink/const.py, custom_components/carelink/sensor.py
Reference: https://developers.home-assistant.io/docs/core/entity/sensor/

Return findings as a table: sensor name | field | current value | correct value | reason
If all sensors are correct, state that explicitly.
```

### Release review
Before each release tag — Opus single session, all 3 reviews scoped to changes since last release.
Output to `docs/reviews/review-release-vX.Y.Z.md`.

### Initial baseline
A full 3-review pass across the entire codebase must be completed before the first PR-scoped review.
Run as a single Opus session. Output to `docs/reviews/review-baseline-YYYY-MM-DD.md`.

How to run: Open a new Opus session. Do not run in an active implementation session.

## PR Review Process (token-efficient)

1. **Read `docs/reviews/review-findings.md` first** (~30 lines) — know what's already tracked
2. Run `git diff develop...HEAD --stat` — identify changed files
3. Compare file checksums against review-findings.md — **skip unchanged files**
4. Read only changed hunks: `git diff develop...HEAD -- <file>` — never read full unchanged files
5. **Never re-read the baseline narrative** (`review-baseline-*.md`) — it's a historical record
6. Use `docs/reviews/REVIEW-TEMPLATE.md` for output format
7. After review: update review-findings.md with any status changes or new findings

## Community Trust Strategy

- README includes development approach transparency section and all SonarCloud badges
- `docs/reviews/` audit trail committed with each release review
- CONTRIBUTING.md quality bar applies equally to AI-assisted and human-written contributions
- HACS uses `render_readme: true` — badges and transparency visible in HACS UI
