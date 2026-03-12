# Issues & Planned Work — ha-tandem-pump

Tracks repo-specific issues, features, and planned work.
For quick cross-project tasks, see `~/Code/TODO.md`.

---

## Current Priorities

1. **ISS-011 Phase 1** — ✅ Battery monitoring merged (PR #45); **needs deploy & verify**
2. **ISS-010** — ADRs + templates done; tooling + ADR-007/008 remaining
3. **ISS-011 Phase 2+** — Alerts, CGM, Bolus Calculator, PLGS, ERI
4. **ISS-005** — tandem_api.py coverage gap
5. Remaining baseline findings (D-1, L-5, D-2, S-4, S-5)

---

## Active

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

**Reference:** Plan file `peaceful-sauteeing-star.md`

### ISS-011 — Tandem API Expansion (Battery & Beyond)
**Type:** Feature / Upstream Sync
**Priority:** High
**Created:** 2026-03-13
**Status:** 🟢 Active — Phase 1 complete (PR #45 merged), needs deploy & verify

Upstream review of yo-han/Home-Assistant-Carelink (17 commits since fork point `ac6f2a3`) found **no new battery/reservoir sensors upstream**. Battery data IS available in the Tandem Source API via event IDs not previously requested.

**Phase 1 (Battery Monitoring) — ✅ Complete:**
- PR #43: Investigation docs (upstream review + 6-phase plan) — merged
- PR #44: Housekeeping (ISSUES.md updates) — merged
- PR #45: Battery monitoring implementation — merged
- 4 new sensors: battery %, voltage (mV), remaining (mAh), charging status
- 20 new tests, 568 total passing
- **Pending:** deploy to HA and verify entities. See CR-005.

**Remaining phases:**
1. ~~Phase 1: Battery Monitoring~~ — ✅ Done
2. Phase 2: Alerts & Alarms — events 4, 5, 6, 26, 28
3. Phase 3: G7 & Libre 2 CGM — events 399, 372, 313
4. Phase 4: Bolus Calculator — events 64, 65, 66
5. Phase 5: PLGS & Daily Status — events 140, 90
6. Phase 6: Estimated Remaining Insulin — computed from existing events

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
