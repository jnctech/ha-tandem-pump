# Change Register — ha-tandem-pump

Significant changes to this repository, listed in reverse chronological order.

---

## CR-003 — Fix Suspend Reason Lookup Bug (L-1)
**Date:** 2026-03-12
**Branch:** `bugfix/l1-suspend-reason`
**Status:** Open

### What Changed
| Area | Change |
|------|--------|
| Coordinator | Removed redundant `SUSPEND_REASON_MAP` lookup — `suspend_reason` is already decoded to a human-readable string by `tandem_api.py` |
| const.py | Removed unused `SUSPEND_REASON_MAP` constant |
| Tests | Updated `_suspend_event` helper to pass string values matching real API output |

### Finding Reference
Baseline review L-1 (Medium): `SUSPEND_REASON_MAP` has int keys but `suspend_reason` field is a string from the API decoder. Lookup always returned `None`, producing `"Unknown (User)"` instead of `"User"`.

---

## CR-002 — Engineering Controls Gap Closure
**Date:** 2026-03-12
**Branch:** `feature/test-gitea-ci`
**PR:** [#37](https://github.com/jnctech/ha-tandem-pump/pull/37)
**Status:** Merged to `develop`

### What Changed
Full implementation of engineering controls to meet quality gate and security requirements.

| Area | Change |
|------|--------|
| Secret scanning | Gitleaks CI job + pre-commit hook + `.gitleaks.toml` |
| CI hardening | SonarCloud blocking gate, `pip-audit`, Anchore SBOM |
| Dockerfile linting | `hadolint` CI job added |
| Workflow linting | `actionlint` CI job added |
| Dev container | `.devcontainer/`, `docker-compose.dev.yml` |
| Test container | `Dockerfile.test`, `docker-compose.test.yml` |
| Inner-loop CI | `.gitea/workflows/ci.yml` (runner: 192.168.30.10) |
| API drift detection | `scripts/check_api_drift.py`, `tests/test_api_drift.py` |
| Sensor doc generation | `scripts/generate_sensor_docs.py` |
| Known-good fixture | `tests/fixtures/known_good_api_response.json` |
| Dependencies | `tzdata` added to `requirements.txt` |
| Docs | `SECURITY.md`, `CONTRIBUTING.md` rewrite, `README.md`, `info.md`, `docs/reviews/README.md` |
| Dependabot | `.github/dependabot.yml` |

### Quality Gate Results (at merge)
| Metric | Value | Gate |
|--------|-------|------|
| Coverage | 83% | ≥80% ✅ |
| Tests | 549 passed | — ✅ |
| Bugs/Vulns/Smells | Grade A | Grade A ✅ |
| Gitea CI time | ~54s | <3min ✅ |
| SonarCloud | PASSED | Blocking ✅ |

### Post-Deploy Actions
- ✅ `SONAR_TOKEN` added to GitHub Actions secrets — 2026-03-12
- ✅ GitHub branch protection required checks wired on `master` and `develop` — 2026-03-12
- ✅ `develop` pulled on docker host via `git pull github develop` — 2026-03-12

---

## CR-001 — Initial Fork Setup
**Date:** 2026-01-xx
**Status:** Merged to `master`

### What Changed
- Forked from upstream (noiwid/HAFamilyLink pattern)
- Initial sensor definitions for Tandem t:slim via Medtronic Carelink
- Example dashboard
- Basic GitHub Actions CI

---
