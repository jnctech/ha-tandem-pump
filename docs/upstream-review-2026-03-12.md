# Upstream Review: yo-han/Home-Assistant-Carelink (develop branch)

**Date:** 2026-03-12
**Upstream:** https://github.com/yo-han/Home-Assistant-Carelink (develop branch)
**Commits reviewed:** 17 significant commits since ~2025.8.0 tag

## Overview

The upstream has had 17 significant commits spanning security hardening, critical
bug fixes, API v13 upgrade, Nightscout dedup, sensor availability improvements,
and code cleanup. **No new battery or reservoir sensors were added** — the existing
CareLink sensors (`pump_battery_level`, `reservoir_level`, `reservoir_remaining_units`)
were already present and are mirrored in our fork's `const.py`.

## Already Handled in Our Fork

| Area | Status | Notes |
|------|--------|-------|
| Battery sensors (CareLink) | Present | `SENSOR_KEY_PUMP_BATTERY_LEVEL`, etc. |
| Reservoir sensors (CareLink) | Present | `SENSOR_KEY_RESERVOIR_LEVEL`, etc. |
| Cartridge sensor (Tandem) | Present | `TANDEM_SENSOR_KEY_CARTRIDGE_INSULIN`, etc. |
| SSL off event loop (tandem_api) | Fixed | `tandem_api.py` uses `run_in_executor` |
| Data staleness detection | Implemented | `helpers.py` `is_data_stale()` |
| PumpEntityMixin | Implemented | Centralises device_info |
| Client close() methods | Present | Both NightscoutUploader and TandemSourceClient |
| Snake_case naming | Done | Written fresh with modern conventions |

## Applicable Changes (Ranked by Priority)

### 1. CRITICAL: SSL blocking in `api.py` (CareLink client) — upstream b868f0a

**Issue:** `api.py:114-118` creates `httpx.AsyncClient()` in a sync `@property`.
`ssl.SSLContext.load_verify_locations()` blocks the HA event loop.

**Upstream fix:** Converts to async method using `asyncio.to_thread()`.

**Our status:** `tandem_api.py` already uses `run_in_executor` (good), but `api.py`
(CareLink client) does NOT.

**Action:** Port fix — convert `async_client` property to async method with `to_thread`.

### 2. CRITICAL: SSL blocking in `nightscout_uploader.py` — same commit

**Issue:** `nightscout_uploader.py:52-59` creates `ssl.create_default_context()` in
a sync `@property`, blocking the event loop on first access.

**Action:** Convert `@property` to async method with thread-based SSL context creation.

### 3. HIGH: Defensive data access in Nightscout uploads — upstream f5994f4

**Issue:** Nightscout upload code accesses dict keys directly, crashes on missing data.

**Upstream fix:** `.get()` with defaults, existence guards on upload blocks.

**Action:** Review Nightscout uploader for equivalent guard patterns.

### 4. HIGH: Sensor availability with "always-available" exemptions — upstream ca9335e

**Issue:** Upstream marks sensors unavailable when data is stale (>2 hours), but
exempts safety-critical sensors (timestamps, alarms, notifications).

**Our status:** Staleness check in `sensor.py` is currently BYPASSED (diagnostic mode).

**Action:** Re-enable selective staleness with `SENSORS_ALWAYS_AVAILABLE` exemptions.

### 5. MEDIUM: Config flow reconfiguration — upstream ce7d4e0

**Feature:** Change Nightscout URL, API secret, scan interval without re-entering credentials.

**Action:** Add `async_step_reconfigure()` to config_flow.py.

### 6. MEDIUM: String faultId handling — upstream cc3b06d

**Issue:** Newer sensors (Simplera) return string faultIds, crashing alarm parser.

**Action:** Verify our alarm parsing handles both string and numeric faultIds.

### 7. LOW: PII sanitisation in logs — upstream d1346ad, 34961c2

**Feature:** Redacts patient names, serial numbers, etc. from debug logs.

**Action:** Add `sanitize_for_logging()` helper (nice to have for support log sharing).

### 8. LOW: API v13 / Auth0 support — upstream c6bb778

CareLink-specific only. Does NOT apply to Tandem API.

### 9. LOW: Nightscout upload deduplication — upstream 78c7cce

Previously implemented then intentionally removed from our fork. Re-evaluate only
if users report duplicate treatments.

## Battery & Reservoir — Key Finding

**Upstream CareLink** provides `pump_battery_level` (%), `reservoir_level` (%), and
`reservoir_remaining_units` directly from the CareLink API response.

**Tandem Source API** does NOT expose:
- Real-time battery percentage (not available in any known endpoint)
- Real-time reservoir/cartridge remaining level

The only insulin data from Tandem comes from:
- `CartridgeFilled` event (event_id 33) — records fill volume at fill time
- `BolusDelivery` / `BolusCompleted` / `BasalDelivery` events — record delivered insulin

**Possible enhancement:** Estimate remaining insulin by subtracting cumulative
delivered insulin from last cartridge fill volume. This is non-trivial but doable.

## Recommended Action Plan

| Priority | Action | Effort |
|----------|--------|--------|
| Do now | Fix SSL blocking in `api.py` and `nightscout_uploader.py` | Small |
| Do soon | Re-enable selective staleness in sensor availability | Small |
| Do soon | Add defensive `.get()` guards in Nightscout uploader | Small |
| Plan | Add config flow reconfiguration | Medium |
| Plan | Add PII sanitisation helper | Small |
| Investigate | Estimate remaining insulin from delivery events | Medium-Large |
| Skip | API v13 / Auth0 (CareLink-specific) | N/A |
| Skip | Nightscout dedup (removed intentionally) | N/A |
