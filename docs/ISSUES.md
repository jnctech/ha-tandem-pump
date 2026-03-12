# Issues & Planned Work — ha-tandem-pump

Tracks repo-specific issues, features, and planned work.
For quick cross-project tasks, see `~/Code/TODO.md`.

---

## Active

### ISS-003 — GitHub Branch Protection: Required Checks Not Yet Added
**Type:** Infrastructure / Config
**Priority:** High
**Created:** 2026-03-12
**Status:** 🔴 Open

Branch protection rules exist on `master` and `develop` but the status check search box is empty — no checks are enforced yet. Must be done after PR #37 merge (checks need at least one run to appear in search).

**Required checks to add on both branches:**
- `Python Tests`
- `SonarCloud Code Analysis`
- `Secret scanning - Gitleaks`
- `Security check - Bandit`
- `Dependency vulnerability check`
- `Dockerfile lint (hadolint)`
- `GitHub Actions lint (actionlint)`
- `Python Code Format Check`
- `Check hassfest`

**Steps:** GitHub → Settings → Branches → Edit rule → Status checks search

---

### ISS-004 — SONAR_TOKEN GitHub Actions Secret Missing
**Type:** Infrastructure / Config
**Priority:** High
**Created:** 2026-03-12
**Status:** 🔴 Open

SonarCloud job passes in latest run but requires `SONAR_TOKEN` secret to be present. If it's missing the job will silently skip or fail.

**Steps:** GitHub → Settings → Secrets and variables → Actions → New repository secret → `SONAR_TOKEN`

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

### ISS-007 — Baseline AI Review Not Yet Run
**Type:** Quality / Documentation
**Priority:** Medium
**Created:** 2026-03-12
**Status:** 🟡 Backlog

Per CLAUDE.md AI review policy, a full 3-review baseline pass across the entire codebase must be completed before the first PR-scoped review. This has not been run yet.

**Steps:** Open a new Opus session. Prompt: `Read CLAUDE.md then run a full baseline review. Output to docs/reviews/review-baseline-2026-MM-DD.md.`

---

## Completed

### ISS-001 — Engineering Controls Gap
**Closed:** 2026-03-12 (PR #37)
Full secret scanning, CI hardening, devcontainer, test container, Gitea inner-loop CI, API drift detection, sensor doc generation. See CR-002 in CHANGE-REGISTER.md.

### ISS-002 — Example Dashboard
**Closed:** 2026-01-xx (PR #34)
Added example Lovelace dashboard with card-mod prerequisites.

---
