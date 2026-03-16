# Issues & Planned Work — ha-tandem-pump

Tracks repo-specific issues, features, and planned work.
For quick cross-project tasks, see `~/Code/TODO.md`.

---

## Current Priorities

1. **ISS-012** — HACS review findings (6 HIGH — before HACS submission)
2. **ISS-011 Phase 7** — OpenSSF Security Baseline + Dependabot (before HACS submission)
3. **ISS-010** — ADRs + templates done; tooling + ADR-007/008 remaining
4. **ISS-005** — tandem_api.py coverage gap
5. Remaining baseline findings (D-1, L-5, S-4)

---

## Active

### ISS-012 — HACS Review Findings
**Type:** Quality / HACS Compliance
**Priority:** High
**Created:** 2026-03-16
**Status:** 🟢 Active
**Source:** `docs/reviews/review-hacs-2026-03-16.md`

**HIGH findings to resolve (before HACS submission):**
- [ ] F-1: No `async_set_unique_id` in config flow — allows duplicate entries
- [ ] F-9: Auth errors raise `UpdateFailed` not `ConfigEntryAuthFailed` — no automatic reauth
- [ ] F-8: Pre-coordinator setup failures not wrapped in `ConfigEntryNotReady`
- [ ] A-6: `_migrate_legacy_logindata` does sync file I/O on event loop
- [ ] H-4: Requirements in manifest use `>=` instead of exact `==` pins

**Deferred (accepted risk):**
- A-4a: Own httpx.AsyncClient instead of HA shared session — major refactor, clients are lifecycle-managed. Not blocking for HACS submission.

**MEDIUM (fix opportunistically):**
- H-11: Missing `integration_type` in manifest.json
- F-7: No reauth flow implemented (pairs with F-9)

**Reference:** `/hacs-review` skill created 2026-03-16 (`~/.claude/skills/hacs-review/`)

### ISS-010 — Architecture Decision Records & Documentation Gaps
**Type:** Documentation / Engineering Practice
**Priority:** Medium
**Created:** 2026-03-13
**Status:** 🟢 Active — ADRs + templates done, tooling remaining

**Done:**
- ✅ ADR-001 through ADR-006 (PR #41, merged)
- ✅ PR template + issue templates (PR #42, merged)

**Remaining:**
- ADR-007 (test coverage targets) — needs research
- ADR-008 (unit consistency: "U" vs "units") — needs research
- CHANGELOG.md + generator
- Release checklist action
- Pre-push hook
- Commit message validation
- Dependency pinning
- ~~**Devcontainer build fix**~~ — ✅ Fixed in CR-014 (`bugfix/devcontainer-gitleaks-download`): added `--retry 3`, `-L` flag, dropped redundant `--proto-redir`

**Reference:** Plan file `peaceful-sauteeing-star.md`

### ISS-011 — Tandem API Expansion (Battery & Beyond)
**Type:** Feature / Upstream Sync
**Priority:** High
**Created:** 2026-03-13
**Status:** 🟢 Active — Phase 6 deployed & verified, Phase 7 next

Upstream review of yo-han/Home-Assistant-Carelink (17 commits since fork point `ac6f2a3`) found **no new battery/reservoir sensors upstream**. Battery data IS available in the Tandem Source API via event IDs not previously requested.

**Phase 1 (Battery Monitoring) — ✅ Complete:**
- PR #43: Investigation docs (upstream review + 6-phase plan) — merged
- PR #44: Housekeeping (ISSUES.md updates) — merged
- PR #45: Battery monitoring implementation — merged
- PR #46: Sensor audit + diagnostics service — merged
- 4 new sensors: battery %, voltage (mV), remaining (mAh), charging status
- `capture_diagnostics` service for API schema discovery
- Widened event fetch window (1→14 days) for reliable battery data
- Fixed glucose delta unit (None → mg/dL)
- 28 new tests (20 battery + 8 diagnostics), 576 total passing
- ✅ Deployed & verified 2026-03-13. See CR-005, CR-006.
- ⚠️ Battery voltage (18944 mV) may be raw ADC — investigate with diagnostics capture

**Phase 2 (Alerts & Alarms) — ✅ Deployed & verified:**
- PR #49 — merged to develop, deployed 2026-03-13
- 3 new sensors: last_alert, last_alarm, active_alerts_count
- TANDEM_ALERT_MAP (~35 entries) + TANDEM_ALARM_MAP (~29 entries) in const.py
- 20 new tests (7 decoder + 13 coordinator), 596 total passing
- See CR-009

**Phase 3 (G7 & Libre 2 CGM) — ✅ Deployed & verified:**
- PR #50 + PR #51 (SonarCloud S1871 fix) — merged to develop, deployed 2026-03-13
- 1 new sensor: cgm_sensor_type (diagnostic, from AA_DAILY_STATUS event 313)
- G7 (event 399) and Libre 2 (event 372) CGM readings routed into existing cgm_readings pipeline
- Replaced all magic event IDs in coordinator with EVT_* constants
- Extracted `_decode_cgm_gxb_layout` shared decoder to eliminate duplication
- 19 new tests (11 decoder + 8 coordinator), 613 total passing
- See CR-010

**Phase 4 (Bolus Calculator) — ✅ Deployed & verified:**
- PR #52 (implementation) + PR #53 (bugfix: remove dict-as-sensor, use _attributes pattern)
- 4 new sensors: last_bolus_bg, last_bolus_carbs_entered, last_bolus_correction, last_bolus_food_portion
- Bolus calculator details surfaced as extra_state_attributes on last_bolus_bg (not a standalone sensor)
- 3-way join by BolusID across events 64/65/66
- 14 new tests (6 decoder + 8 coordinator), 627 total passing
- Sensors show "unknown" until bolus calculator wizard is used (quick boluses are event 17, not 64/65/66)
- See CR-011, CR-012

**Phase 5 (PLGS & Daily Status) — ✅ Deployed & verified:**
- PR #55 — merged to develop, deployed 2026-03-14
- 1 new sensor: predicted_glucose (from PLGS algorithm PGV, event 140)
- Event 90 (NewDay) decoded for diagnostics logging; sensor deferred to Phase 6
- 15 new tests (8 decoder + 7 coordinator), 641 total passing
- Sensor shows "unknown" until a PLGS event occurs (expected — PLGS only activates on predicted low)
- See CR-013

**Phase 6 (Estimated Remaining Insulin) — ✅ Deployed & verified:**
- PR #58 — merged to develop, deployed 2026-03-14
- 1 new sensor: estimated_insulin_remaining (cumulative seq-based tracking)
- Compute-then-commit pattern prevents state corruption on exceptions
- 11 new tests, 652 total passing
- Sensor shows "unknown" until cartridge fill event appears in 14-day window (expected)
- See CR-015

**All 6 implementation phases complete.** Remaining:
1. ~~Phase 1: Battery Monitoring~~ — ✅ Done
2. ~~Phase 2: Alerts & Alarms~~ — ✅ Done
3. ~~Phase 3: G7 & Libre 2 CGM~~ — ✅ Done
4. ~~Phase 4: Bolus Calculator~~ — ✅ Done
5. ~~Phase 5: PLGS & Daily Status~~ — ✅ Done
6. ~~Phase 6: Estimated Remaining Insulin~~ — ✅ Done

7. ~~Phase 7: OpenSSF Security Baseline~~ — ✅ Done (PR #60, merged 2026-03-14)
   - SHA-pinned 9 actions, dependabot github-actions, scorecard, dependency-review
   - ⏳ Opus compliance review → `docs/reviews/review-openssf-YYYY-MM-DD.md` (next session)

**Investigation items:**
- CGM sensor change tracking (Dexcom G6 10-day cycle) — check if any undecoded event ID corresponds to sensor insertion/removal. Phase 3 CGM events (399, 372, 313) may include this.
- CGM transmitter change tracking (Dexcom G6 3-month cycle) — check if transmitter pairing/unpairing events exist in undecoded event IDs.

**Reference:** `docs/upstream-review-2026-03-12.md`, `docs/plan-tandem-api-expansion.md`

---

## Backlog

### ISS-005 — `tandem_api.py` Coverage at 47% (below 80% file-level)
**Type:** Quality / Testing
**Priority:** Medium
**Created:** 2026-03-12
**Status:** 🟡 Backlog

Overall coverage is 83% (passes gate), but `tandem_api.py` is at 47% line coverage individually. The SonarCloud gate measures project-wide, so this passes — but the API client is the highest-risk file and deserves dedicated test coverage.

**Suggested approach:**
- Audit what isn't covered in `tests/test_tandem_api.py`
- Add tests for error paths, session handling, and retry logic
- Target ≥80% on this file specifically

---

### ISS-006 — Gitea Mirror of GitHub develop/master
**Type:** Infrastructure / Workflow
**Priority:** Low
**Created:** 2026-03-12
**Status:** 🟡 Backlog

Docker host's Gitea remote (`origin`) only has the inner-loop CI workflow. Pushing merged `develop` to Gitea requires removing branch protection (done 2026-03-12) then pushing manually. A proper mirror setup would auto-sync GitHub→Gitea.

**Option A:** Configure Gitea pull-mirror from GitHub (Settings → Repository → Mirror Settings)
**Option B:** Keep as-is (push manually after major merges — low friction for solo workflow)

---

## Completed

### ISS-009 — Fix Sensor state_class Metadata (S-1, S-3)
**Closed:** 2026-03-13 (PR #40)
Removed `state_class=MEASUREMENT` from 8 sensors: 3 discrete events (last bolus, meal bolus, cartridge fill) and 5 daily totals. These produced meaningless HA long-term statistics. See CR-004.

### ISS-008 — Fix Suspend Reason Lookup Bug (L-1)
**Closed:** 2026-03-12 (PR #39)
Removed redundant `SUSPEND_REASON_MAP` lookup — API already returns decoded strings. Standardised unknown-code format. Added defensive try/except. See CR-003.

### ISS-007 — Baseline AI Review
**Closed:** 2026-03-12
Full 3-review baseline pass (Logic, API Drift, Sensor) completed by Opus. 16 findings tracked in `docs/reviews/review-findings.md`. Baseline narrative at `docs/reviews/review-baseline-2026-03-12.md`. PR review template and token-efficiency rules added to CLAUDE.md.

### ISS-003 — GitHub Branch Protection: Required Checks
**Closed:** 2026-03-12
All 9 required checks wired to both `master` and `develop` branch protection rules.

### ISS-004 — SONAR_TOKEN GitHub Actions Secret
**Closed:** 2026-03-12
`SONAR_TOKEN` added to GitHub Actions secrets. SonarCloud blocking gate confirmed working.

### ISS-001 — Engineering Controls Gap
**Closed:** 2026-03-12 (PR #37)
Full secret scanning, CI hardening, devcontainer, test container, Gitea inner-loop CI, API drift detection, sensor doc generation. See CR-002 in CHANGE-REGISTER.md.

### ISS-002 — Example Dashboard
**Closed:** 2026-01-xx (PR #34)
Added example Lovelace dashboard with card-mod prerequisites.

---
