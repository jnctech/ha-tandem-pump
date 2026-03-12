# Baseline Opus Review — 2026-03-12

**ISS-007** | **Reviewer:** Claude Opus 4.6 | **Scope:** Full codebase — all three review types

## Review 1: Logic Correctness

**Files:** `__init__.py` (TandemCoordinator), `tandem_api.py`

### L-1: Suspend reason lookup uses wrong key type [BUG]
**Location:** `__init__.py:1562-1567`

The event parser (`tandem_api.py:188-196`) stores the human-readable string in `suspend_reason` and the raw int in `suspend_reason_id`. The coordinator looks up `last_sr.get("suspend_reason")` (a string like `"User"`) in `SUSPEND_REASON_MAP` which maps `int -> str`. The lookup always returns `None`, producing `"Unknown (User)"` instead of `"User"`.

**Fix:** Use `suspend_reason_id` for the map lookup, or use `suspend_reason` directly.

### L-2: resp.json() error not wrapped [LOW]
**Location:** `tandem_api.py:573`

`_api_get` returns `resp.json()` which can raise `json.JSONDecodeError`, not caught or wrapped in `TandemApiError`. Functional in practice — the coordinator's broad `except Exception` catches it.

### L-3: CGM usage calculation assumes 1-day window [LOW]
**Location:** `__init__.py:1910`

`n / 288` assumes 1-day window. Fetch is 2 days, but `min(..., 100.0)` caps it. Fragile if fetch window changes.

### L-4: Timestamp handling is correct but unintuitive [INFO]
**Location:** `tandem_api.py:110-113`

`TANDEM_EPOCH + ts_raw` as Unix timestamp → naive datetime → coordinator attaches pump tz. Correct because naive values equal local pump time. Comment explains the approach.

### L-5: Profile `idp` matching may silently fail [LOW]
**Location:** `__init__.py:1744-1750`

Matches `prof.get("idp") == active_idp`. Fixture doesn't include `idp` in profile entries. Verify against live API response.

### L-6: mmol/L conversion uses 0.0555 [INFO]
Standard is 1/18.018 = 0.05551. Error is 0.018% — clinically insignificant.

---

## Review 2: API Contract Drift

**Files:** `tandem_api.py`, `tests/fixtures/known_good_api_response.json`

### D-1: No binary event fixture [GAP]
The pump events binary format (26-byte records, base64-encoded) has no fixture or contract test. `check_api_drift.py` only validates JSON field names.

**Recommendation:** Add a `pump_events_binary_fixture` with known base64 payload and expected decoded output.

### D-2: Fixture missing `partNumber` in drift check [LOW]
Present in fixture, referenced in code as `softwareVersion` fallback, but not in `_drift_check.pump_event_metadata_fields`.

### D-3: Fixture doesn't cover PII fields [OK]
Intentionally excluded. Code handles absence via `.get()` with defaults.

### D-4: `pumper_info_response` is minimal [OK]
Only `pumperId` and `accountId` — sufficient.

### D-5: No fixture for ControlIQ endpoints [OK]
Return 404. No fixture needed.

---

## Review 3: Sensor Entity Correctness

**Files:** `const.py` (TANDEM_SENSORS), `sensor.py`

### S-1: `state_class=MEASUREMENT` on discrete event sensors [WRONG]

| Sensor | Key | Issue |
|--------|-----|-------|
| Last bolus | `tandem_last_bolus_units` | Discrete event, not measurement |
| Last meal bolus | `tandem_last_meal_bolus` | Discrete event |
| Last cartridge fill | `tandem_last_cartridge_fill_amount` | One-time fill event |

**Impact:** HA records meaningless mean/min/max statistics.
**Fix:** Change `state_class` to `None`.

### S-2: Inconsistent insulin unit strings [COSMETIC]
Sensor entities use `"units"`, settings entities use `"U"`. HA treats as different units.
**Defer** to next major version (breaking change for long-term statistics).

### S-3: Daily totals use MEASUREMENT instead of TOTAL [WRONG]

| Sensor | Key |
|--------|-----|
| Total daily insulin | `tandem_total_daily_insulin` |
| Daily bolus total | `tandem_daily_bolus_total` |
| Daily basal total | `tandem_daily_basal_total` |
| Daily carbs | `tandem_daily_carbs` |
| Daily bolus count | `tandem_daily_bolus_count` |

**Fix:** Change to `state_class=None` (safest — daily-reset accumulators confuse HA's `TOTAL` logic).

### S-4: Threshold sensors missing BLOOD_GLUCOSE device class [ENHANCEMENT]
CGM High/Low Alert and BG threshold sensors could use `_BLOOD_GLUCOSE` for automatic unit conversion.

### S-5: `suggested_display_precision` not set [LOW]
Glucose mmol sensors would benefit from precision=1, insulin from precision=2.

---

## Summary

| Category | Critical | Medium | Low | Info |
|----------|----------|--------|-----|------|
| Logic | 0 | 1 (L-1) | 3 | 2 |
| API Drift | 0 | 1 (D-1) | 1 | 0 |
| Sensor | 0 | 2 (S-1, S-3) | 2 | 0 |
| **Total** | **0** | **4** | **6** | **2** |

### Recommended fix order
1. **L-1** — Fix suspend reason lookup (one-liner)
2. **S-1** — Fix state_class on discrete event sensors
3. **S-3** — Fix state_class on daily total sensors
4. **D-1** — Add binary event fixture
5. **S-4** — Add BLOOD_GLUCOSE device class to thresholds
6. **S-2** — Standardise insulin units (next major)
