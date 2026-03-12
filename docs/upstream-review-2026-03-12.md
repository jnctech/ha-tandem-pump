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

## Battery & Reservoir — CRITICAL FINDING (Deep Investigation)

### Battery: IT IS IN THE API — We Just Don't Request It

**Previous assumption was WRONG.** The Tandem Source pumpevents API DOES expose
battery data. We simply never request the event type that contains it.

**Event ID 81 — `LID_DAILY_BASAL`** (from tconnectsync `custom_events.json`):
```
Offset  Type     Field                       Unit
0       float32  dailyTotalBasal             units
4       float32  lastBasalRate               units/hour
8       float32  iob                         units
12      uint8    batteryChargePercentMSBRaw  (raw)
13      uint8    batteryChargePercentLSBRaw  (raw, needs transform)
14      uint16   batteryLipoMilliVolts       mV
```

**Battery percent formula** (from tconnectsync `transforms.py`):
```python
percent = (256 * (MSB_raw - 14) + LSB_raw) / (3 * 256)
# Result is 0.0–1.0, multiply by 100 for percentage
```

This event is emitted daily by the pump and tconnectsync already uses it to upload
battery status to Nightscout via `process_device_status.py`. We just need to:
1. Add `"81,"` to the `event_ids` string in `tandem_api.py:676`
2. Add a decoder case in `decode_pump_events()` for event_id 81
3. Parse and expose as `TANDEM_SENSOR_KEY_BATTERY_PERCENT` and
   `TANDEM_SENSOR_KEY_BATTERY_VOLTAGE`

**Additionally, Event ID 53 — `LID_SHELF_MODE`** contains even more battery detail:
```
Offset  Type     Field          Unit
0       uint32   msecSinceReset ms
4       uint8    LiPo_IBC       % (battery percent, display value)
5       uint8    LiPo_ABC       % (alternate battery calc)
6       int16    LiPoCurrent    mA (charge/discharge current)
8       uint32   LiPo_RemCap    mAh (remaining capacity)
12      uint32   LiPo_mV        mV (battery voltage)
```

### Reservoir/Cartridge Remaining: Not Directly Available

Confirmed: **No event type tracks remaining insulin continuously.** The only data
points are:
- Event 33 `CARTRIDGE_FILLED` — fill volume at fill time (we already decode this)
- Bolus/basal delivery events — cumulative delivered amounts

**Viable enhancement:** Calculate estimated remaining insulin:
```
remaining = last_cartridge_fill_volume - sum(all_delivered_since_fill)
```
This requires tracking cumulative delivered insulin across polling cycles.

### Additional Undiscovered Events Worth Requesting

| Event ID | Name | What it provides |
|----------|------|------------------|
| **81** | LID_DAILY_BASAL | **Battery %, voltage, daily total basal, IOB** |
| **53** | LID_SHELF_MODE | Battery detail (%, mV, mAh, current draw) |
| **90** | LID_NEW_DAY | Commanded basal rate, feature bitmask |
| **313** | LID_AA_DAILY_STATUS | PumpControlState, UserMode, SensorType (G6/G7/Libre2) |
| **36** | LID_USB_CONNECTED | Charging current (mA) |
| **37** | LID_USB_DISCONNECTED | Charging current (mA) |

### How controlX2/WearPump Get Battery & Cartridge

Projects like [controlX2](https://github.com/jwoglom/controlX2) and WearPump get
real-time battery and cartridge data via **Bluetooth** (pumpX2 library), NOT the
cloud API. The Bluetooth protocol exposes:
- `CurrentBatteryV2Response` — battery IBC % and charging status
- `InsulinStatusResponse` — currentInsulinAmount, isEstimate, insulinLowAmount
- `HomeScreenMirrorResponse` — mirrors pump display state

These are NOT available via the Tandem Source cloud API — they require direct
Bluetooth connection to the pump. However, the cloud API binary events DO contain
battery data in the daily status events (81, 53) that the pump uploads periodically.

### Data Source Architecture Summary

```
Tandem Pump Hardware
  ├── Bluetooth (pumpX2) → Real-time: battery %, insulin remaining, IOB
  │                         [NOT available to us — requires phone BT pairing]
  │
  └── Cloud Upload → Tandem Source API (what we use)
       ├── Metadata endpoint → serial, model, firmware, lastUpload, settings
       ├── Pump events endpoint (binary, 26-byte records)
       │    ├── Event 256: CGM readings ✅ (we decode)
       │    ├── Event 20/21/280: Bolus data ✅ (we decode)
       │    ├── Event 3/279: Basal data ✅ (we decode)
       │    ├── Event 11/12: Suspend/resume ✅ (we decode)
       │    ├── Event 33: Cartridge filled ✅ (we decode)
       │    ├── Event 81: DAILY BASAL + BATTERY ❌ NOT REQUESTED
       │    ├── Event 53: SHELF MODE + BATTERY DETAIL ❌ NOT REQUESTED
       │    ├── Event 313: DAILY STATUS (sensor type) ❌ NOT REQUESTED
       │    └── Event 36/37: USB connect/disconnect ❌ NOT REQUESTED
       └── ControlIQ endpoints → therapy timeline, dashboard summary
```

## Recommended Action Plan (Updated)

| Priority | Action | Effort |
|----------|--------|--------|
| **Do now** | Add event ID 81 to API request + decoder → battery sensors | Small |
| **Do now** | Add event ID 53 to API request + decoder → detailed battery | Small |
| **Do now** | Add event ID 313 to API request + decoder → CGM sensor type | Small |
| Do soon | Fix SSL blocking in `nightscout_uploader.py` | Small |
| Do soon | Re-enable selective staleness in sensor availability | Small |
| Do soon | Add defensive `.get()` guards in Nightscout uploader | Small |
| Plan | Estimate remaining insulin from delivery totals | Medium |
| Plan | Add config flow reconfiguration | Medium |
| Plan | Add PII sanitisation helper | Small |
| Skip | Fix SSL in `api.py` (CareLink-only, not used by Tandem) | N/A |
| Skip | API v13 / Auth0 (CareLink-specific) | N/A |
| Skip | Nightscout dedup (removed intentionally) | N/A |

## References

- [tconnectsync](https://github.com/jwoglom/tconnectsync) — Tandem Source to Nightscout sync
- [pumpX2](https://github.com/jwoglom/pumpX2) — Reverse-engineered Bluetooth protocol
- [controlX2](https://github.com/jwoglom/controlX2) — Android/WearOS pump control app
- [tconnectsync custom_events.json](https://github.com/jwoglom/tconnectsync/blob/master/tconnectsync/eventparser/custom_events.json) — Event ID 81 definition
- [tconnectsync events.json](https://github.com/jwoglom/tconnectsync/blob/master/tconnectsync/eventparser/events.json) — Full event type catalogue
