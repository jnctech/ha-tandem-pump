# Change Register — ha-tandem-pump

Significant changes to this repository, listed in reverse chronological order.

---

## CR-014 — Devcontainer Gitleaks Download Fix
**Date:** 2026-03-14
**Branch:** `bugfix/devcontainer-gitleaks-download`
**PR:** [#57](https://github.com/jnctech/ha-tandem-pump/pull/57)
**Status:** In review

### What Changed
| Area | Change |
|------|--------|
| .devcontainer/Dockerfile | Added `--retry 3 --retry-delay 5` to gitleaks curl download |
| .devcontainer/Dockerfile | Added `-L` to explicitly follow HTTP redirects |
| .devcontainer/Dockerfile | Removed `--proto-redir -all,https` (redundant — GitHub redirect chain is HTTPS only) |
| .devcontainer/Dockerfile | Added SHA256 checksum verification (`sha256sum -c`) — resolves SonarCloud Security Hotspot |

### Why
Devcontainer build was failing intermittently with `gzip: stdin: unexpected end of file` — the gitleaks tarball download was completing partially due to transient network interruption. The `--proto-redir` flag was also potentially suppressing the redirect follow-through in some curl versions. Added retry logic, explicit `-L`, and SHA256 integrity verification to make the download resilient and satisfy SonarCloud's security analysis.

### Quality Gate Results
| Metric | Value | Gate |
|--------|-------|------|
| Python tests | N/A (no Python changes) | — |
| Ruff format | N/A | — |
| Bandit | N/A | — |
| API drift | N/A | — |

---

## CR-013 — PLGS & Daily Status Sensors (Phase 5)
**Date:** 2026-03-13
**Branch:** `feature/plgs-daily-status-phase5`
**PR:** TBD
**Status:** In review

### What Changed
| Area | Change |
|------|--------|
| tandem_api.py | Added decoders for event 140 (PLGS Periodic) and event 90 (NewDay) |
| tandem_api.py | Added events 90 and 140 to API event filter string |
| const.py | Added `TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE` constant and `SensorEntityDescription` |
| __init__.py | Added PLGS event categorisation, sorting, and predicted glucose sensor population |
| __init__.py | Added NewDay event collection and logging (sensor population deferred to Phase 6) |

### Why
PLGS (Predictive Low Glucose Suspend) events contain the pump's predicted glucose value — useful for dashboards showing what Control-IQ "sees" ahead of actual CGM readings. NewDay events capture the commanded basal rate at midnight, decoded for diagnostics and future Phase 6 use.

### New Sensor
| Sensor | Device Class | Unit | Notes |
|--------|-------------|------|-------|
| Predicted glucose | BLOOD_GLUCOSE | mg/dL | From PLGS algorithm PGV; 0 = UNAVAILABLE (No Prediction) |

### Tests
- 8 decoder tests (PLGS states, unknown fallback, NewDay rate/features)
- 7 coordinator tests (latest-wins, zero PGV, no events, combined events)
- 641 total passing

---

## CR-012 — Bolus Calculator Attributes Bugfix
**Date:** 2026-03-13
**Branch:** `bugfix/bolus-calc-attrs-not-sensor`
**PR:** [#53](https://github.com/jnctech/ha-tandem-pump/pull/53)
**Status:** Merged & deployed

### What Changed
| Area | Change |
|------|--------|
| const.py | Removed `TANDEM_SENSOR_KEY_BOLUS_CALC_ATTRS` SensorEntityDescription — dict values are not valid HA sensor states |
| const.py | Changed constant value to `"tandem_last_bolus_bg_attributes"` so bolus calc details surface as `extra_state_attributes` on `last_bolus_bg` sensor via the existing `_attributes` convention in `sensor.py` |

### Why
Code review (post-merge on PR #52) identified that the `bolus_calculator_attributes` sensor was passing a dict as `native_value`. HA sensors require scalar values. The existing codebase pattern for attribute dicts (e.g., `LAST_BOLUS_ATTRS`, `LAST_MEAL_BOLUS_ATTRS`) stores them as coordinator data keys with `_attributes` suffix but does NOT register them as SensorEntityDescriptions. Applied the same pattern.

---

## CR-011 — Bolus Calculator Sensors (Phase 4)
**Date:** 2026-03-13
**Branch:** `feature/bolus-calculator-phase4`
**PR:** [#52](https://github.com/jnctech/ha-tandem-pump/pull/52)
**Status:** Merged & deployed (bugfix in CR-012)

### What Changed
| Area | Change |
|------|--------|
| tandem_api.py | Added 3 event constants (EVT_BOLUS_REQUESTED_MSG1=64, MSG2=65, MSG3=66) |
| tandem_api.py | Added 3 decoder cases for bolus calculator messages (BG, carbs, IOB, ISF, food/correction split) |
| tandem_api.py | Updated get_pump_events() event_ids to include 64, 65, 66 |
| const.py | Added 5 sensor key constants and 4 SensorEntityDescriptions (5th removed in CR-012) |
| __init__.py | Added 3-way join by BolusID across msg1/msg2/msg3 events |
| __init__.py | Populate 4 primary sensors + attributes dict from latest complete bolus calc record |
| tests | Added TestBolusCalcDecoder (6 tests) + TestBolusCalcCoordinator (8 tests); 627 total passing |

### Sensors Added
| Key | Name | Value |
|-----|------|-------|
| tandem_last_bolus_bg | Last bolus BG | mg/dL at time of bolus request (+ bolus calc details as extra_state_attributes) |
| tandem_last_bolus_carbs_entered | Last bolus carbs entered | grams entered into calculator |
| tandem_last_bolus_correction | Last bolus correction | units (correction portion) |
| tandem_last_bolus_food_portion | Last bolus food portion | units (food portion) |

### Review Gate Results
| Gate | Result |
|------|--------|
| Logic Review 1 (Opus) | No bugs; 2 low-severity notes (B-1, B-2) |
| API Drift Review 2 (Opus) | No drift (binary events not in JSON fixture) |
| Sensor Review 3 (Sonnet) | All correct |
| silent-failure-hunter | No new findings (pre-existing C-4 noted) |
| code-reviewer | 1 critical finding — dict-as-sensor (fixed in CR-012) |

### Quality Gate Results (at branch)
| Metric | Value | Gate |
|--------|-------|------|
| Tests | 627 passed | ✅ |
| Ruff format | Clean | ✅ |
| Ruff lint | Clean | ✅ |
| API drift | None | ✅ |
| Bandit | Clean | ✅ |

---

## CR-010 — G7, Libre 2 CGM Support & Sensor Type Detection (Phase 3)
**Date:** 2026-03-13
**Branch:** `feature/cgm-g7-libre2-phase3`
**PR:** #50, #51
**Status:** Merged & deployed

### What Changed
| Area | Change |
|------|--------|
| tandem_api.py | Added 3 event constants (EVT_AA_DAILY_STATUS=313, EVT_CGM_DATA_FSL2=372, EVT_CGM_DATA_G7=399) |
| tandem_api.py | Added 3 decoder cases (G7 same layout as GXB, FSL2 different int16/uint8 layout, AA_DAILY_STATUS for sensor type) |
| tandem_api.py | Updated get_pump_events() event_ids to include 313, 372, 399 |
| const.py | Added CGM sensor type key constant and SensorEntityDescription (diagnostic, icon mdi:chip) |
| __init__.py | Replaced ALL magic event IDs with EVT_* constants (import from tandem_api) |
| __init__.py | Route events 399/372 into cgm_readings alongside 256; parse 313 for sensor type |
| __init__.py | Updated LTS statistics to include G7 and FSL2 CGM events |
| __init__.py | Narrowed exception handling: `except Exception` → `except (KeyError, TypeError, IndexError)`, warning → error |
| __init__.py | Added logging for unknown CGM sensor types |
| tests | Added TestCGMPhase3Decoder (11 tests) + TestCGMPhase3Coordinator (8 tests); 613 total passing |

### Sensors Added
| Key | Name | Value |
|-----|------|-------|
| tandem_cgm_sensor_type | CGM sensor type | G6, G7, Libre 2, None, or Unknown (N) — from AA_DAILY_STATUS event 313 |

### Review Gate Results
| Gate | Result |
|------|--------|
| Logic Review 1 (Opus) | No bugs; 7 low-severity test-coverage suggestions |
| API Drift Review 2 (Opus) | No drift; FSL2 uint8 vs uint16 status noted — can't validate without real capture |
| Sensor Review 3 (Sonnet) | All correct |
| silent-failure-hunter | 6 findings; 4 fixed (magic numbers, exception narrowing, unknown type logging, error severity) |
| code-reviewer | Pending final run |

### Quality Gate Results (at branch)
| Metric | Value | Gate |
|--------|-------|------|
| Tests | 613 passed | ✅ |
| Ruff format | Clean | ✅ |
| Ruff lint | Clean | ✅ |
| API drift | None | ✅ |
| Bandit | Clean | ✅ |

---

## CR-009 — Alerts & Alarms Sensors (Phase 2)
**Date:** 2026-03-13
**Branch:** `feature/alerts-alarms-phase2`
**PR:** [#49](https://github.com/jnctech/ha-tandem-pump/pull/49)
**Status:** Merged to `develop`
**Deployed:** 2026-03-13 — verified on HA

### What Changed
| Area | Change |
|------|--------|
| tandem_api.py | Added 5 event constants (EVT_ALERT_ACTIVATED=4, EVT_ALARM_ACTIVATED=5, EVT_MALFUNCTION_ACTIVATED=6, EVT_ALERT_CLEARED=26, EVT_ALARM_CLEARED=28) |
| tandem_api.py | Added 3 decoder cases; updated get_pump_events() event_ids to include 4, 5, 6, 26, 28 |
| const.py | Added 3 sensor key constants, TANDEM_ALERT_MAP (~35 entries), TANDEM_ALARM_MAP (~29 entries), 3 SensorEntityDescription entries |
| __init__.py | Added UNAVAILABLE defaults; updated _parse_pump_events() categorisation; added _parse_alert_alarm_events() |
| tests | Added TestAlertAlarmDecoders (7 tests) + TestAlertAlarmCoordinator (13 tests); 596 total passing |

### Sensors Added
| Key | Name | Value |
|-----|------|-------|
| tandem_last_alert | Last pump alert | Human-readable alert name (TANDEM_ALERT_MAP) |
| tandem_last_alarm | Last pump alarm | Human-readable alarm name (TANDEM_ALARM_MAP) |
| tandem_active_alerts_count | Active pump alerts | Count of uncleared alerts + alarms |

### Review Gate Results
| Gate | Result |
|------|--------|
| silent-failure-hunter | 5 findings; all addressed (comments, error→warning, state_class fix) |
| code-reviewer | 2 findings; both addressed (state_class=None, malfunction comment) |
| Logic Review 1 (Opus) | 2 test gaps; both addressed (name assert + malfunction-cleared test) |
| Sensor Review 3 (Sonnet) | No errors found |

### Quality Gate Results (at branch)
| Metric | Value | Gate |
|--------|-------|------|
| Tests | 596 passed | ✅ |
| Ruff format | Clean | ✅ |
| Ruff lint | Clean | ✅ |
| API drift | None | ✅ |
| Bandit | Clean | ✅ |

---

## CR-008 — Display Precision & Fixture Update
**Date:** 2026-03-13
**Branch:** `fix/sensor-display-precision`
**PR:** [#48](https://github.com/jnctech/ha-tandem-pump/pull/48)
**Status:** Merged to `develop`
**Deployed:** 2026-03-13 — verified on HA (IOB 2dp, basal 3dp, battery 1dp, percentages 1dp)

### What Changed
| Area | Change |
|------|--------|
| const.py | Added `suggested_display_precision` to 25 Tandem sensors (0 for integers, 1 for %/mmol, 2 for insulin, 3 for basal rates) |
| fixture | Rebuilt `known_good_api_response.json` from real API capture — full metadata structure, pumper_info, 16 event samples |
| fixture | Updated `_drift_check` field lists: added `patientName`, profile sub-fields |
| docs | Resolved findings D-2 (drift check), S-4 (accepted), S-5 (fixed) |

### Finding Reference
- S-5: suggested_display_precision was missing from all sensors — HA showed raw float precision
- S-4: No HA `SensorDeviceClass.BLOOD_GLUCOSE` exists — `device_class=None` is correct
- D-2: `partNumber` and `patientName` now in drift check canonical field list

### Quality Gate Results (at branch)
| Metric | Value | Gate |
|--------|-------|------|
| Coverage | 83%+ | ≥80% ✅ |
| Tests | 576 passed | — ✅ |
| Ruff format | Clean | ✅ |
| Ruff lint | Clean | ✅ |
| API drift | None | ✅ |

---

## CR-007 — Sensor Metadata Audit & Battery Voltage Fix
**Date:** 2026-03-13
**Branch:** `fix/sensor-metadata-audit`
**PR:** [#47](https://github.com/jnctech/ha-tandem-pump/pull/47)
**Status:** Merged to `develop`
**Deployed:** 2026-03-13 — verified on HA (voltage from ShelfMode, duration formatting, diagnostic categories)

### What Changed
| Area | Change |
|------|--------|
| const.py | Duration sensors: bare "h"/"m" → UnitOfTime.HOURS/MINUTES + SensorDeviceClass.DURATION |
| const.py | Battery sensors (conduit, CGM sensor): added SensorDeviceClass.BATTERY |
| const.py | Device info sensors (6 Carelink): added EntityCategory.DIAGNOSTIC |
| const.py | Active insulin, reservoir, max basal: added missing unit_of_measurement |
| const.py | sgBelowLimit: corrected from PERCENT to MGDL (glucose threshold, not percentage) |
| const.py | Tandem sensors: "U"→UNITS, "mV"→UnitOfElectricPotential.MILLIVOLT, "kg"→UnitOfMass.KILOGRAMS |
| tandem_api.py | Removed unreliable DailyBasal voltage (raw ADC, not millivolts) |
| __init__.py | Coordinator: voltage now exclusively from ShelfMode; expanded PII redaction |
| tests | Updated battery decoder/coordinator tests; expanded PII test coverage |

### Finding Reference
- 8 new review findings (S-6 through S-11, P-1) tracked in review-findings.md
- DailyBasal voltage 25344 confirmed as raw ADC via diagnostics capture
- ShelfMode voltage 3722 mV confirmed as accurate

### Quality Gate Results (at branch)
| Metric | Value | Gate |
|--------|-------|------|
| Coverage | 83%+ | ≥80% ✅ |
| Tests | 576 passed | — ✅ |
| Ruff format | Clean | ✅ |
| Ruff lint | Clean | ✅ |
| API drift | None | ✅ |

### Post-Deploy Actions
- [ ] scp updated files to HA
- [ ] `ha core restart`
- [ ] Verify battery voltage shows realistic mV (from ShelfMode) or UNAVAILABLE
- [ ] Verify duration sensors show proper HA duration formatting

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
