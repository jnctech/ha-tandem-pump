# Change Register — ha-tandem-pump

Significant changes to this repository, listed in reverse chronological order.

---

## CR-006 — Sensor Audit & Diagnostics Service (ISS-011 Support)
**Date:** 2026-03-13
**Branch:** `fix/sensor-audit-diagnostics`
**PR:** [#46](https://github.com/jnctech/ha-tandem-pump/pull/46)
**Status:** Merged to `develop`
**Deployed:** 2026-03-13 — verified on HA (4 battery entities + diagnostics service)

### What Changed
| Area | Change |
|------|--------|
| __init__.py | Added `capture_diagnostics` service handler — dumps full API response to `/config/carelink_diagnostics_*.json` for field discovery |
| __init__.py | Widened event fetch window from 1 day to 14 days — ensures battery/daily events are captured even with infrequent uploads |
| const.py | Fixed glucose delta sensor: changed unit from `None` to `mg/dL` |
| tandem_api.py | Minor formatting cleanup |
| services.yaml | Added `capture_diagnostics` service definition |
| tests | 8 new tests for `capture_diagnostics` service handler (file write, error handling, service registration) |

### Finding Reference
- Glucose delta unit fix addresses sensor metadata gap found during baseline review
- Diagnostics service enables API schema discovery for future ISS-011 phases
- Event window widening ensures battery sensors (daily cadence) reliably populate

### Quality Gate Results (at merge)
| Metric | Value | Gate |
|--------|-------|------|
| Coverage | 83%+ | ≥80% ✅ |
| Tests | 576 passed | — ✅ |
| Bugs/Vulns/Smells | Grade A | Grade A ✅ |

### Post-Deploy Actions
- [ ] Deploy with CR-005 (same scp + restart)
- [ ] Verify `capture_diagnostics` service appears in Developer Tools → Actions
- [ ] Run service, retrieve diagnostics JSON for fixture update

---

## CR-005 — Battery Monitoring Sensors (ISS-011 Phase 1)
**Date:** 2026-03-12
**Branch:** `feat/phase1-battery-monitoring`
**PR:** [#45](https://github.com/jnctech/ha-tandem-pump/pull/45)
**Status:** Merged to `develop`
**Deployed:** 2026-03-13 — verified on HA (battery %, voltage, remaining, charging status)

### What Changed
| Area | Change |
|------|--------|
| tandem_api.py | Added event constants EVT_USB_CONNECTED (36), EVT_USB_DISCONNECTED (37), EVT_SHELF_MODE (53), EVT_DAILY_BASAL (81); added 4 binary decoders; added event IDs to API request |
| const.py | Added 4 sensor keys (battery %, voltage mV, remaining mAh, charging status) + SensorEntityDescription entries |
| __init__.py | Added battery sensor categorisation with DailyBasal/ShelfMode priority logic, USB charging status detection |
| tests | 20 new tests: 11 decoder tests (TestBatteryEventDecoders) + 9 coordinator tests (TestBatterySensorPopulation) |

### Finding Reference
- ISS-011 Phase 1 — battery data available in Tandem Source API via event IDs not previously requested
- Battery % formula from tconnectsync: `min(100, max(0, round((256 * (MSB - 14) + LSB) / (3 * 256) * 100, 1)))`

### Quality Gate Results (at merge)
| Metric | Value | Gate |
|--------|-------|------|
| Coverage | 83%+ | ≥80% ✅ |
| Tests | 568 passed | — ✅ |
| Bugs/Vulns/Smells | Grade A | Grade A ✅ |

### Post-Deploy Actions
- [ ] scp updated files to HA (`tandem_api.py`, `const.py`, `__init__.py`)
- [ ] `ha core restart`
- [ ] Verify 4 new battery entities appear (battery %, voltage, remaining mAh, charging status)
- [ ] Confirm battery % matches pump display (within daily update cadence)

---

## CR-004 — Fix Sensor state_class Metadata (S-1, S-3)
**Date:** 2026-03-12
**Branch:** `fix/sensor-state-class`
**PR:** [#40](https://github.com/jnctech/ha-tandem-pump/pull/40)
**Status:** Merged to `develop`
**Deployed:** 2026-03-13 — verified on HA (62 entities, no errors)

### What Changed
| Area | Change |
|------|--------|
| const.py | Removed `state_class=MEASUREMENT` from 3 discrete event sensors (last bolus, last meal bolus, last cartridge fill) — these are one-time events, not continuous measurements |
| const.py | Removed `state_class=MEASUREMENT` from 5 daily total sensors — daily-reset accumulators produce meaningless HA long-term statistics with MEASUREMENT |

### Finding Reference
- S-1 (Medium): Discrete event sensors with MEASUREMENT produce meaningless mean/min/max statistics
- S-3 (Medium): Daily totals with MEASUREMENT instead of None confuse HA statistics

### Impact
Existing HA long-term statistics for affected sensors will stop accumulating. No data loss — historical values remain but new entries won't be added. Users who relied on statistics graphs for these sensors will see them stop updating.

---

## CR-003 — Fix Suspend Reason Lookup Bug (L-1)
**Date:** 2026-03-12
**Branch:** `bugfix/l1-suspend-reason`
**PR:** [#39](https://github.com/jnctech/ha-tandem-pump/pull/39)
**Status:** Merged to `develop`
**Deployed:** 2026-03-13 — verified on HA (no errors)

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
