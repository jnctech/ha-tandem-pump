# Tandem Source API — Binary Event Payload Reference

Reverse-engineered from live API captures via the `capture_diagnostics` service
and debug payload logging. The Tandem Source API returns pump events as binary
data (26 bytes per event: 10-byte header + 16-byte payload).

**Last updated:** 2026-03-16
**Pump firmware:** Control-IQ v7.8.1
**API region:** EU (source.eu.tandemdiabetes.com)

---

## Event Header (10 bytes, all events)

| Offset | Type | Field |
|--------|------|-------|
| 0 | `>H` | event_id |
| 2 | `>I` | timestamp (seconds since 2008-01-01 00:00:00 local) |
| 6 | `>I` | seq (monotonic sequence number) |

## Decoded Events

### Event 33 — CartridgeFilled

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>f` | _unknown_ | Always 0.0 in all captures |
| 4 | `>f` | **insulin_volume** | Fill volume in units (e.g. 163.3, 296.1) |
| 8–15 | — | _padding_ | All zeros |

**History:** Originally decoded with `insulin_volume` at offset 0 (always returned 0.0).
Fixed 2026-03-16 — actual volume is at offset 4. The offset-0 field purpose is unknown;
offset-2 as uint16 shows values like 60, 180, 240 (possibly fill duration in seconds?).

### Event 20 — BolusCompleted

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>H` | bolus_id | Matches across events 64/65/66/280/20 |
| 2 | `>H` | completion_status | 3 = normal completion |
| 4 | `>f` | iob | Insulin on board (units) |
| 8 | `>f` | insulin_delivered | Actual delivered (units) |
| 12 | `>f` | insulin_requested | Requested amount (units) |

### Event 21 — BolexCompleted (Extended Bolus)

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>H` | bolus_id | |
| 2 | `>H` | completion_status | |
| 4 | `>f` | iob | |
| 8 | `>f` | insulin_delivered | Extended portion delivered |
| 12 | `>f` | insulin_requested | Extended portion requested |

### Event 280 — BolusDelivery

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>B` | bolus_type | 9=standard correction, 25=food+correction |
| 1 | `>B` | delivery_status | 0=completed, 1=in-progress |
| 2 | `>H` | bolus_id | |
| 4 | `>H` | requested_now_mu | Milli-units requested |
| 6 | `>H` | correction_mu | Correction portion (milli-units) |
| 8 | `>H` | delivered_total_mu | Total delivered (milli-units) |
| 10 | `>f` | insulin_delivered | Delivered in units (= delivered_total_mu / 1000) |

### Event 279 — BasalDelivery

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>B` | commanded_source | 0=profile, 3=Control-IQ |
| 2 | `>H` | profile_rate_mu | Profile basal rate (milli-units/hr) |
| 4 | `>H` | commanded_rate_mu | Actual commanded rate (milli-units/hr) |
| 6 | `>f` | commanded_rate | Rate in units/hr (= commanded_rate_mu / 1000) |

### Event 81 — DailyBasal

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>f` | daily_total_basal | Cumulative basal for the day (units) |
| 4 | `>f` | last_basal_rate | Current basal rate (units/hr) |
| 8 | `>f` | iob | Insulin on board |
| 12 | `>f` | battery_percent | Battery level (%) — from DailyBasal, may differ from ShelfMode |

### Event 256 — CGM (Dexcom G6/GXB layout)

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>H` | glucose_mgdl | Glucose in mg/dL |
| 2 | `>f` | rate_of_change | mg/dL per minute |
| 6 | `>B` | status | 0=normal |

### Event 399 — CGM (Dexcom G7, same layout as 256)

### Event 372 — CGM (FreeStyle Libre 2)

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>h` | glucose_mgdl | **Signed** int16 (vs unsigned for G6/G7) |
| 2 | `>f` | rate_of_change | |
| 6 | `>B` | status | |

### Event 4 — AlertActivated

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>H` | alert_id | Maps to TANDEM_ALERT_MAP in const.py |
| 2 | `>H` | fault_locator | |
| 4 | `>H` | param1 | |
| 6 | `>f` | param2 | |

### Event 5 — AlarmActivated

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>H` | alert_id | Maps to TANDEM_ALARM_MAP in const.py |
| 2 | `>H` | fault_locator | |
| 4 | `>H` | param1 | |
| 6 | `>f` | param2 | |

### Event 26 — AlertCleared / Event 28 — AlarmCleared

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>H` | alert_id | |

### Event 36 — USBConnected / Event 37 — USBDisconnected

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>f` | negotiated_current_ma | USB negotiated current (mA) |

### Event 53 — ShelfMode

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>H` | battery_voltage_mv | Reliable voltage reading (mV) |
| 2 | `>H` | battery_remaining_mah | Remaining capacity (mAh) |

### Event 11 — PumpingSuspended

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | decoded string | suspend_reason | Human-readable reason |

### Event 12 — PumpingResumed

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>H` | pre_resume_state | |
| 2 | `>f` | insulin_amount | |

### Event 16 — BGReading

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>H` | bg_mgdl | Manual BG reading (mg/dL) |
| 2 | `>f` | iob | IOB at time of reading |
| 6 | decoded | entry_type | "Manual", etc. |

### Event 48 — CarbsEntered

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>f` | carbs | Grams of carbs entered |

### Event 64 — BolusRequestedMsg1

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | bits | correction_included | Bit flag |
| 0 | bits | bolus_type | 1=food+correction, 2=correction only |
| 2 | `>H` | bolus_id | |
| 4 | `>H` | bg_mgdl | BG at time of request |
| 6 | `>f` | iob | |
| 10 | `>H` | carb_amount | Raw carb value |
| 12 | `>f` | carb_ratio | |

### Event 65 — BolusRequestedMsg2

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>B` | standard_percent | % delivered immediately |
| 2 | `>H` | bolus_id | |
| 4 | `>H` | target_bg | |
| 6 | `>H` | isf | Insulin sensitivity factor |
| 8 | `>H` | duration_minutes | Extended bolus duration |
| 10 | bits | declined_correction | |
| 10 | bits | user_override | |

### Event 66 — BolusRequestedMsg3

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>H` | bolus_id | |
| 2 | `>f` | food_bolus_size | Food portion (units) |
| 6 | `>f` | correction_bolus_size | Correction portion (units) |
| 10 | `>f` | total_bolus_size | Total (units) |

### Event 140 — PLGS Periodic

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>H` | predicted_glucose | Predicted glucose value (mg/dL); 0 = no prediction |
| 2 | `>B` | plgs_state | Algorithm state |

### Event 90 — NewDay

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>H` | commanded_rate_mu | Basal rate at midnight (milli-units/hr) |
| 2 | `>H` | features_bitmap | Active features bitmap |

### Event 313 — AA_DAILY_STATUS

| Offset | Type | Field | Notes |
|--------|------|-------|-------|
| 0 | `>B` | sensor_type | 1=G6, 2=G7, 3=Libre 2, 0=None |

### Event 229 — UserModeChange

Decoded in tandem_api.py — contains current/previous user mode strings.

### Event 230 — PCMChange

Decoded in tandem_api.py — contains current/previous PCM (Pump Control Mode) strings.

---

## Undecoded / Partially Decoded

These events are fetched but have fields not yet fully mapped:

- **Event 33 offset 0** — `>f` always 0.0; offset 2 as `>H` shows 60/180/240 (fill duration?)
- **Event 61 (CannulaFilled)** — fetched but never seen in API responses (Tandem API limitation)
- **Event 63 (TubingFilled)** — decoded but payload structure not fully documented
- **Event 6 (MalfunctionActivated)** — same layout as AlertActivated, not yet seen in captures

---

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/reports/reportsfacade/pumpevents/{pumperId}/{deviceId}` | GET | Binary pump events |
| `/api/reports/reportsfacade/pumpeventmetadata/{pumperId}/{deviceId}` | GET | Metadata (maxDateWithEvents) |
| `/api/pumpers/pumpers/{pumperId}` | GET | Pumper info (name, devices) |

Query params for pumpevents: `minDate`, `maxDate`, `eventIds` (comma-separated).

---

## Notes

- All multi-byte values are **big-endian**
- Timestamps are seconds since **2008-01-01 00:00:00** (Tandem epoch), in **local pump time**
- Milli-unit fields (suffix `_mu`) divide by 1000 for units
- The 14-day event window is set by the integration, not an API limit
- Pump uploads data via Bluetooth to the t:connect mobile app, then to Tandem Source cloud
- Upload frequency depends on user behavior — data can be hours or days stale
