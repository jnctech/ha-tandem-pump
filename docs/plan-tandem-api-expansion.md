# Implementation Plan: Tandem Source API Expansion

**Date:** 2026-03-12
**Branch:** claude/review-upstream-changes-wjqgX
**Status:** Planning complete, ready for implementation
**Motivation:** Teen diabetes management — missed charging, ignored low insulin alerts,
incorrect bolusing, upcoming G7 CGM transition

## Architecture (unchanged)

Every new event follows the same 3-file pipeline — `sensor.py` requires NO changes:

1. **`tandem_api.py`** — Add event constant + binary decoder case in `decode_pump_events()`
2. **`const.py`** — Add `TANDEM_SENSOR_KEY_*` constant + `SensorEntityDescription` in `TANDEM_SENSORS`
3. **`__init__.py`** — Add categorisation + sensor population in `TandemCoordinator._parse_pump_events()`

## Event IDs: Current vs Planned

```
Current (15):  256,20,21,280,3,279,11,12,16,33,48,61,63,229,230
Adding  (17):  81,53,36,37,4,5,6,26,28,399,372,313,64,65,66,140,90
Total   (32)
```

---

## Phase 1: Battery Monitoring

**Priority:** CRITICAL — teen not charging pump
**Events:** 81 (DailyBasal), 53 (ShelfMode), 36/37 (USB connect/disconnect)

### Event 81 — LID_DAILY_BASAL (emitted daily)

```
Offset  Type     Field                       Unit
0       float32  dailyTotalBasal             units
4       float32  lastBasalRate               units/hour
8       float32  iob                         units
12      uint8    batteryChargePercentMSBRaw  (raw)
13      uint8    batteryChargePercentLSBRaw  (raw, needs transform)
14      uint16   batteryLipoMilliVolts       mV
```

Battery % formula (from tconnectsync transforms.py):
```python
percent = min(100, max(0, round((256 * (MSB - 14) + LSB) / (3 * 256) * 100, 1)))
```

### Event 53 — LID_SHELF_MODE

```
Offset  Type     Field          Unit
0       uint32   msecSinceReset ms
4       uint8    LiPo_IBC       % (battery percent, display value)
5       uint8    LiPo_ABC       % (alternate battery calc)
6       int16    LiPoCurrent    mA (charge/discharge current)
8       uint32   LiPo_RemCap    mAh (remaining capacity)
12      uint32   LiPo_mV        mV (battery voltage)
```

### Events 36/37 — USB Connected/Disconnected

```
Offset  Type     Field              Unit
0       float32  negotiatedCurrent  mA
```

### New Sensors

| Sensor Key | Name | Device Class | Unit | Icon | Always Available |
|------------|------|-------------|------|------|-----------------|
| `tandem_battery_percent` | Battery level | BATTERY | % | mdi:battery | Yes |
| `tandem_battery_voltage` | Battery voltage | VOLTAGE | mV | mdi:flash | No (diagnostic) |
| `tandem_battery_remaining_mah` | Battery remaining | — | mAh | mdi:battery-charging | No (diagnostic) |
| `tandem_charging_status` | Charging status | — | — | mdi:power-plug | Yes |

### Implementation Steps

1. Add constants in `tandem_api.py`: `EVT_DAILY_BASAL = 81`, `EVT_SHELF_MODE = 53`,
   `EVT_USB_CONNECTED = 36`, `EVT_USB_DISCONNECTED = 37`
2. Add decoder cases in `decode_pump_events()` for each event
3. Add `"81,53,36,37,"` to `event_ids` string in `get_pump_events()`
4. Add sensor key constants in `const.py`
5. Add `SensorEntityDescription` entries in `TANDEM_SENSORS`
6. Add battery keys to `TANDEM_SENSORS_ALWAYS_AVAILABLE`
7. Add categorisation lists and sensor population in `_parse_pump_events()`
8. Import new constants in `__init__.py`
9. Tests: decoder tests, coordinator tests, battery formula edge cases

### HA Automation Example

```yaml
automation:
  - alias: "Alert: Pump battery low"
    trigger:
      - platform: numeric_state
        entity_id: sensor.carelink_tandem_battery_level
        below: 20
    action:
      - service: notify.mobile_app_parent_phone
        data:
          title: "Pump Battery Low"
          message: "Battery at {{ states('sensor.carelink_tandem_battery_level') }}%"
```

---

## Phase 2: Alerts & Alarms

**Priority:** HIGH — teen ignoring low insulin, missed bolus alerts
**Events:** 4 (AlertActivated), 5 (AlarmActivated), 6 (MalfunctionActivated),
26 (AlertCleared), 28 (AlarmCleared)

### Event 4/5/6 — Alert/Alarm/Malfunction Activated

```
Offset  Type     Field            Unit
0       uint32   AlertID/AlarmID  (lookup in map)
4       uint32   faultLocatorData
8       uint32   param1
12      float32  param2
```

### Events 26/28 — Alert/Alarm Cleared

```
Offset  Type     Field    Unit
0       uint32   AlertID/AlarmID
```

### Lookup Maps (from tconnectsync static_dicts.py)

**TANDEM_ALERT_MAP** (key entries):
```python
{
    0: "Low Insulin", 1: "USB Connection", 2: "Low Power",
    3: "Low Power (Critical)", 5: "Auto Off", 7: "Power Source",
    11: "Incomplete Bolus", 12: "Incomplete Temp Rate",
    13: "Incomplete Cartridge Change", 17: "Low Insulin (2nd)",
    19: "Low Transmitter", 22: "Sensor Expiring",
    39: "Transmitter End of Life", 48: "CGM Unavailable",
    # ... 64 entries total
}
```

**TANDEM_ALARM_MAP** (key entries):
```python
{
    0: "Cartridge Alarm", 2: "Occlusion", 3: "Pump Reset",
    7: "Auto Off", 8: "Empty Cartridge", 10: "Temperature",
    12: "Battery Shutdown", 18: "Resume Pump",
    21: "Altitude", 25: "Cartridge Removed",
    # ... 64 entries total
}
```

**TANDEM_CGM_ALERT_MAP:**
```python
{
    11: "CGM Sensor Fail", 13: "CGM Sensor Expired",
    14: "CGM Out Of Range", 20: "CGM Transmitter Error",
    26: "CGM Temperature", 27: "CGM Failed Connection",
    39: "CGM Transmitter Expired", 40: "Pump Bluetooth Error",
}
```

### New Sensors

| Sensor Key | Name | Notes |
|------------|------|-------|
| `tandem_last_alert` | Last alert | State = human-readable name |
| `tandem_last_alert_attributes` | — | alert_id, params, timestamp, cleared, recent list (10 max) |
| `tandem_last_alarm` | Last alarm | State = human-readable name |
| `tandem_last_alarm_attributes` | — | Same structure |
| `tandem_active_alerts_count` | Active alerts | Count of activated minus cleared |

### Active Tracking Logic

```python
activated: dict[int, dict] = {}  # alert_id → event details
for evt in sorted(alert_events, key=lambda e: e["timestamp"]):
    if evt["event_name"] in ("AlertActivated", "AlarmActivated"):
        activated[evt["alert_id"]] = evt
    elif evt["event_name"] in ("AlertCleared", "AlarmCleared"):
        activated.pop(evt["alert_id"], None)
active_count = len(activated)
```

### HA Automation Examples

```yaml
automation:
  - alias: "Alert: Low insulin ignored"
    trigger:
      - platform: state
        entity_id: sensor.carelink_tandem_last_alert
        to: "Low Insulin"
        for: "00:15:00"  # still active after 15 min
    action:
      - service: notify.mobile_app_parent_phone
        data:
          title: "Low Insulin Alert Active"
          message: "Pump has had a low insulin alert for 15 minutes"

  - alias: "Alert: Any pump alarm"
    trigger:
      - platform: state
        entity_id: sensor.carelink_tandem_last_alarm
    condition:
      - condition: template
        value_template: "{{ trigger.to_state.state not in ['unavailable', 'unknown'] }}"
    action:
      - service: notify.mobile_app_parent_phone
        data:
          title: "Pump Alarm: {{ states('sensor.carelink_tandem_last_alarm') }}"
```

---

## Phase 3: G7 & Libre 2 CGM Support

**Priority:** MEDIUM — G7 transition upcoming, Libre 2 for broader user base
**Events:** 399 (CGM_DATA_G7), 372 (CGM_DATA_FSL2), 313 (AA_DAILY_STATUS)

### Event 399 — LID_CGM_DATA_G7 (same layout as 256)

```
Offset  Type     Field                       Unit
0       int8     Rate                        mg/dL/min (÷10)
2       uint16   glucoseValueStatus
4       uint16   currentGlucoseDisplayValue  mg/dL
6       int8     RSSI                        dBm
```

### Event 372 — LID_CGM_DATA_FSL2 (Libre 2)

```
Offset  Type     Field                       Unit
0       int16    Rate                        mg/dL/min (÷10)  ← NOTE: int16 not int8
2       uint8    glucoseValueStatus          ← NOTE: uint8 not uint16
4       uint16   currentGlucoseDisplayValue  mg/dL
6       int8     RSSI                        dBm
```

### Event 313 — LID_AA_DAILY_STATUS

```
Offset  Type     Field            Values
1       uint8    SensorType       0=None, 1=G6, 2=Libre2, 3=G7
2       uint8    usermode         0=Normal, 1=Sleeping, 2=Exercising
3       uint8    PumpControlState 0=No Control, 1=Open Loop, 2=Pining, 3=Closed Loop
```

### Design Decision

Events 399 and 372 route into the **same `cgm_readings` list** as event 256.
The decoder produces identical field names (`glucose_mgdl`, `rate_of_change`, `status`).
Downstream parsing in `_parse_pump_events()` is unchanged.

### New Sensor

| Sensor Key | Name | Notes |
|------------|------|-------|
| `tandem_cgm_sensor_type` | CGM sensor type | "G6" / "G7" / "Libre2" / "None" (diagnostic) |

---

## Phase 4: Bolus Calculator Details

**Priority:** MEDIUM — teen not bolusing correctly for meals
**Events:** 64/65/66 (BolusRequested Msg1/Msg2/Msg3) — three events per bolus, joined by BolusID

### Event 64 — LID_BOLUS_REQUESTED_MSG1

```
Offset  Type     Field                   Unit
0       uint8    CorrectionBolusIncluded enum
1       uint8    BolusType               enum
2       uint16   BolusID
4       uint16   BG                      mg/dL
6       float32  IOB                     units
10      uint16   CarbAmount              grams
12      uint32   CarbRatio               g/u (needs ratio transform)
```

### Event 65 — LID_BOLUS_REQUESTED_MSG2

```
Offset  Type     Field               Unit
0       uint8    StandardPercent      %
2       uint16   BolusID
4       uint16   TargetBG            mg/dL
6       uint16   ISF                 (mg/dL)/unit
8       uint16   Duration            minutes
10      uint8    DeclinedCorrection  0=No, 1=Yes
11      uint8    UserOverride        0=No, 1=Yes
```

### Event 66 — LID_BOLUS_REQUESTED_MSG3

```
Offset  Type     Field               Unit
0       uint16   BolusID
2       float32  FoodBolusSize       units
6       float32  CorrectionBolusSize units
10      float32  TotalBolusSize      units
```

### Join Logic

```python
bolus_calc: dict[int, dict] = {}  # keyed by BolusID
for msg in msg1_events:
    bolus_calc.setdefault(msg["bolus_id"], {}).update({
        "bg": msg["bg_mgdl"], "carbs": msg["carb_amount"],
        "iob_at_request": msg["iob"], "bolus_type": msg["bolus_type"],
    })
for msg in msg2_events:
    bolus_calc.setdefault(msg["bolus_id"], {}).update({
        "target_bg": msg["target_bg"], "isf": msg["isf"],
        "declined_correction": bool(msg["declined_correction"]),
        "user_override": bool(msg["user_override"]),
    })
for msg in msg3_events:
    bolus_calc.setdefault(msg["bolus_id"], {}).update({
        "food_bolus": msg["food_bolus_size"],
        "correction_bolus": msg["correction_bolus_size"],
        "total_bolus": msg["total_bolus_size"],
        "timestamp": msg["timestamp"],
    })
# Latest complete = most recent msg3 with matching msg1
```

### New Sensors

| Sensor Key | Name | Notes |
|------------|------|-------|
| `tandem_last_bolus_bg` | Last bolus BG | mg/dL at time of request |
| `tandem_last_bolus_carbs_entered` | Last bolus carbs | grams entered into calculator |
| `tandem_last_bolus_correction` | Last bolus correction | units (correction portion) |
| `tandem_last_bolus_food_portion` | Last bolus food | units (food portion) |
| `tandem_bolus_calculator_attributes` | — | Full joined record in attributes |

### HA Automation Example

```yaml
automation:
  - alias: "Alert: Bolus without carbs (possible missed meal entry)"
    trigger:
      - platform: state
        entity_id: sensor.carelink_tandem_last_bolus_carbs_entered
        to: "0"
    condition:
      - condition: template
        value_template: >
          {{ states('sensor.carelink_tandem_last_bolus_food_portion') | float > 0 }}
    action:
      - service: notify.mobile_app_parent_phone
        data:
          title: "Bolus without carbs"
          message: "A bolus was given without carb entry — check if meal was counted"
```

---

## Phase 5: PLGS & Daily Status

**Priority:** LOW — advanced dashboards
**Events:** 140 (PLGS_Periodic), 90 (NewDay)

### Event 140 — LID_PLGS_PERIODIC

```
Offset  Type     Field       Unit
4       uint8    HoMinState  enum
5       uint8    RuleState   bitmask
10      uint16   PGV         mg/dL (predicted glucose value)
12      uint16   FMR         mg/dL
```

### Event 90 — LID_NEW_DAY

```
Offset  Type     Field              Unit
0       float32  CommandedBasalRate  units/hour
4       uint32   FeaturesBitmask
```

### New Sensor

| Sensor Key | Name | Notes |
|------------|------|-------|
| `tandem_predicted_glucose` | Predicted glucose | PGV from PLGS algorithm |

---

## Phase 6: Estimated Remaining Insulin

**Priority:** MEDIUM — complements battery for teen safety
**Events:** None new — computed from existing events 33, 20/21, 280, 279

### State Tracking (on TandemCoordinator)

```python
self._cumulative_delivered_since_fill: float = 0.0
self._last_cartridge_fill_seq: int = 0
self._last_cartridge_fill_volume: float = 0.0
```

### Calculation Logic

```python
# In _parse_pump_events():
# 1. Check for new CartridgeFilled event
for cf in cartridge_fills:
    if cf["seq"] > self._last_cartridge_fill_seq:
        self._last_cartridge_fill_seq = cf["seq"]
        self._last_cartridge_fill_volume = cf["insulin_volume"]
        self._cumulative_delivered_since_fill = 0.0

# 2. Sum delivered insulin from this batch
for bolus in bolus_completed + bolex_completed:
    self._cumulative_delivered_since_fill += bolus.get("insulin_delivered", 0)
# Also add basal: daily_basal event 81 gives dailyTotalBasal

# 3. Calculate remaining
estimated = max(0, self._last_cartridge_fill_volume - self._cumulative_delivered_since_fill)
data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING] = round(estimated, 1)
```

### New Sensor

| Sensor Key | Name | Unit | Notes |
|------------|------|------|-------|
| `tandem_estimated_insulin_remaining` | Est. insulin remaining | units | mdi:needle, clamped at 0 |

### HA Automation Example

```yaml
automation:
  - alias: "Alert: Low insulin — change cartridge"
    trigger:
      - platform: numeric_state
        entity_id: sensor.carelink_tandem_est_insulin_remaining
        below: 30
    action:
      - service: notify.mobile_app_parent_phone
        data:
          title: "Insulin Running Low"
          message: "~{{ states('sensor.carelink_tandem_est_insulin_remaining') }}u remaining"
```

---

## Implementation Order

| Order | Phase | Safety Value | Complexity | Independently Deployable |
|-------|-------|-------------|------------|-------------------------|
| 1st | Phase 1: Battery | Highest | Simple | Yes |
| 2nd | Phase 2: Alerts/Alarms | High | Moderate (active tracking) | Yes |
| 3rd | Phase 3: G7/Libre2 CGM | Medium | Simple (reuse CGM path) | Yes |
| 4th | Phase 6: Insulin remaining | Medium | Moderate (stateful) | Yes |
| 5th | Phase 4: Bolus calculator | Medium | Highest (3-way join) | Yes |
| 6th | Phase 5: PLGS | Low | Simple | Yes |

## Files Modified Per Phase

| File | Ph1 | Ph2 | Ph3 | Ph4 | Ph5 | Ph6 |
|------|-----|-----|-----|-----|-----|-----|
| `tandem_api.py` | 4 evts | 5 evts | 3 evts | 3 evts | 2 evts | — |
| `const.py` | 4 keys, 4 sensors | 5 keys, 2 maps, 5 sensors | 1 key, 1 sensor | 5 keys, 5 sensors | 1 key, 1 sensor | 1 key, 1 sensor |
| `__init__.py` | Parse + populate | Parse + active tracking | Route to CGM | Parse + 3-way join | Parse + populate | Stateful calc |
| `sensor.py` | — | — | — | — | — | — |
| Tests | Decoder + coord | Decoder + active logic | Decoder + routing | Decoder + join | Decoder | Calc + reset |

## References

- [tconnectsync events.json](https://github.com/jwoglom/tconnectsync/blob/master/tconnectsync/eventparser/events.json) — Full event type catalogue (43 events)
- [tconnectsync custom_events.json](https://github.com/jwoglom/tconnectsync/blob/master/tconnectsync/eventparser/custom_events.json) — Event 81 (battery) definition
- [tconnectsync transforms.py](https://github.com/jwoglom/tconnectsync/blob/master/tconnectsync/eventparser/transforms.py) — Battery % formula
- [tconnectsync static_dicts.py](https://github.com/jwoglom/tconnectsync/blob/master/tconnectsync/eventparser/static_dicts.py) — Alert/alarm lookup maps
- [tconnectsync process_device_status.py](https://github.com/jwoglom/tconnectsync/blob/master/tconnectsync/sync/tandemsource/process_device_status.py) — Battery Nightscout upload reference
- [pumpX2](https://github.com/jwoglom/pumpX2) — Bluetooth protocol (battery/insulin via BT, not cloud)
- [controlX2](https://github.com/jwoglom/controlX2) — Android/WearOS app using pumpX2
