# Issues & Planned Work — ha-tandem-pump

Tracks repo-specific issues, features, and planned work.
For quick cross-project tasks, see `~/Code/TODO.md`.

---

## Current Priorities

1. ~~**Deploy & verify**~~ — ✅ Done 2026-03-13
2. **ISS-010** — Architecture Decision Records (in progress — docs/adr-initial branch)
3. **ISS-011** — Review upstream changes (battery/reservoir improvements)
4. **ISS-005** — tandem_api.py coverage gap
5. Remaining baseline findings (D-1, L-5, D-2, S-4, S-5)

---

## Active

### ISS-010 — Architecture Decision Records & Documentation Gaps
**Type:** Documentation / Engineering Practice
**Priority:** Medium
**Created:** 2026-03-13
**Status:** 🔵 Active — planned, not started

No formal architecture decision records exist. Design knowledge is scattered across CLAUDE.md (AI-only), code comments, and baseline review findings.

**Scope:**
- Create `docs/decisions/` directory with ADR template
- Write ADR-001 through ADR-006 (content outlined in session plan 2026-03-13):
  - ADR-001: Two LTS data paths (explicit imports vs sensor state_class)
  - ADR-002: Sensor state_class strategy
  - ADR-003: Polling interval and data freshness
  - ADR-004: Error handling philosophy
  - ADR-005: Timezone handling strategy
  - ADR-006: API contract management
- ADR-007 (test coverage targets) and ADR-008 (unit consistency) need further research
- Create `.github/pull_request_template.md` and issue templates
- Additional tooling: CHANGELOG.md, release checklist, pre-push hook

**Branch:** `docs/adr-initial` (ADRs), `chore/github-templates` (templates)
**Reference:** Plan file `peaceful-sauteeing-star.md` has full gap analysis and tooling recommendations

### ISS-011 — Review Upstream Changes (Battery & Reservoir)
**Type:** Upstream Sync / Feature
**Priority:** Medium
**Created:** 2026-03-13
**Status:** 🔵 Active — flagged, not started
**Reference:** Session note `review-upstream-changes-wjqgX`

Upstream (noiwid/HAFamilyLink) may have improvements to battery and reservoir sensor handling that are relevant to decision-making in the household (low insulin, low battery alerts). Need to:
- Review upstream commits since our fork point (`ac6f2a3`)
- Identify battery/reservoir changes worth backporting
- Assess impact on existing sensor definitions and alert thresholds
- Decision: adopt upstream changes, adapt them, or document why our approach differs

**Why important:** Battery level and cartridge insulin are used for time-sensitive alerts (e.g., "insulin reservoir low — need to change cartridge"). Improvements to accuracy or alerting in upstream are high-value.

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
