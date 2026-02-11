# Issue: Home Assistant Sensors Not Populating

**Status**: Resolved (PR #4)
**Priority**: High
**Type**: Bug
**Created**: 2026-02-11
**Resolved**: 2026-02-12

## Description

Home Assistant sensors are not being populated and remain in their initial "Unknown" state after integration setup.

## Symptoms

- All sensors show "Unknown" state
- No visible error logs in Home Assistant logs
- Integration appears to load successfully
- No errors during configuration

## Environment

- Home Assistant version: TBD
- Integration version: develop branch
- Platform: TBD

## Expected Behavior

Sensors should populate with data from Tandem Source/Carelink API after integration is configured.

## Actual Behavior

All sensors remain in "Unknown" state indefinitely.

## Troubleshooting Steps

### Debug Logging Added

Enhanced debug logging has been added to:
- ✅ `__init__.py` - TandemCoordinator setup and data updates
- ✅ `sensor.py` - Sensor platform setup and value retrieval

To enable, add to `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.carelink: debug
```

### Diagnostic Script Created

A standalone diagnostic script `diagnostic_tandem.py` has been created to test the Tandem API independently.

See [DIAGNOSTIC_README.md](DIAGNOSTIC_README.md) for detailed instructions.

### To Be Performed:

1. [x] Enable debug logging for the integration
2. [ ] Run diagnostic script to verify API connection
3. [ ] Check Home Assistant logs for coordinator refresh
4. [ ] Verify API authentication and data fetch succeed
5. [ ] Check coordinator.data dict is populated
6. [ ] Verify sensor keys match coordinator.data keys
7. [ ] Identify specific point where data flow breaks

## Related Files

- `custom_components/carelink/coordinator.py` - Data coordinator
- `custom_components/carelink/sensor.py` - Sensor entities
- `custom_components/carelink/tandem_api.py` - API client
- `custom_components/carelink/__init__.py` - Integration initialization

## Investigation Log

### Initial Analysis (2026-02-11)

Based on code review, identified the key data flow:

**Architecture Overview:**
1. `__init__.py` - Contains coordinator classes (`CarelinkCoordinator` and `TandemCoordinator`)
2. `sensor.py` - Defines sensor entities that subscribe to coordinator data
3. API clients (`api.py` for Carelink, `tandem_api.py` for Tandem) - Fetch data from cloud services

**Data Flow:**
```
API Client → Coordinator._async_update_data() → coordinator.data dict → Sensor.native_value property
```

**Sensor Value Retrieval:**
In `sensor.py:85`, sensors get values via:
```python
def native_value(self) -> float:
    return self.coordinator.data.setdefault(self.sensor_description.key, None)
```

**Critical Points to Investigate:**

1. **Coordinator First Refresh** (`__init__.py:259, 294`)
   - Both setup functions call `await coordinator.async_config_entry_first_refresh()`
   - This should trigger the first data fetch
   - Need to verify this completes successfully

2. **Data Dictionary Population** (`__init__.py:346-659` for Carelink, `680-987` for Tandem)
   - `_async_update_data()` methods populate the `data` dict
   - Returns this dict which should become `coordinator.data`
   - Need to verify the data dict is being returned and stored

3. **Sensor Registration** (`sensor.py:33-57`)
   - Sensors are created and added via `async_add_entities()`
   - Each sensor gets the coordinator reference
   - Need to verify sensors are properly linked to coordinator

4. **API Data Fetch**
   - For Carelink: `await self.client.get_recent_data()` at line 352
   - For Tandem: `await self.client.get_recent_data()` at line 684
   - Need to verify API calls are succeeding

**Likely Root Causes:**

1. **Coordinator not updating** - First refresh may be failing silently
2. **Empty data dict** - API may be returning None or empty data
3. **Exception during parsing** - Data parsing errors may leave sensors unset
4. **Timing issue** - Sensors may be reading before first update completes

---

## Resolution (2026-02-12)

### Root Cause
The ControlIQ API endpoints (`tdcservices.eu.tandemdiabetes.com/tconnect/controliq/api/`) return HTTP 404 errors when accessed with Source OIDC tokens. This meant `therapy_timeline` and `dashboard_summary` were always `None`, leaving all sensors in Unknown state.

### Fix Applied (PR #4)
Switched to the **Source Reports pumpevents API** (`source.eu.tandemdiabetes.com/api/reports/reportsfacade/pumpevents/`) as the primary data source. This is the same endpoint the Tandem Source web UI uses.

The pumpevents API returns **base64-encoded binary data** using Tandem's proprietary 26-byte record format. Implemented a binary decoder (`decode_pump_events()`) that parses each record:
- **Header** (bytes 0-9): 4-bit source + 12-bit event_id, 4-byte timestamp (seconds since 2008-01-01), 4-byte sequence number
- **Payload** (bytes 10-25): 16 bytes of event-specific data

### Event Types Decoded
| Event ID | Name | Sensor Data Extracted |
|----------|------|----------------------|
| 256 | CGM_DATA_GXB | glucose_mgdl, rate_of_change, status |
| 20 | BOLUS_COMPLETED | iob, insulin_delivered, insulin_requested, bolus_id |
| 280 | BOLUS_DELIVERY | bolus_type, delivery_status, insulin_delivered |
| 3 | BASAL_RATE_CHANGE | commanded_rate, base_rate, max_rate, change_type |
| 279 | BASAL_DELIVERY | commanded_source, profile_rate_mu, commanded_rate |

### Sensors Now Populating
- Last glucose (mg/dL and mmol/L)
- Last glucose timestamp
- Active insulin (IOB)
- Basal rate
- Last bolus (units and timestamp)
- Last meal bolus
- Control-IQ status
- Glucose delta (after second update cycle)

### Sensors Still Unknown
See Issue #5 for remaining sensor gaps:
- Average glucose, CGM usage, Time in range (require dashboard_summary or computation from CGM history)
- Last pump upload, Last update (metadata timestamp parsing)

### Key Discovery: How the Web UI Gets Data
By inspecting network traffic on the Tandem Source web UI (`source.eu.tandemdiabetes.com`), we discovered the web UI uses the pumpevents endpoint - NOT the ControlIQ API. The web UI decodes the same binary format client-side in JavaScript.

### Binary Format Reference
Based on [tconnectsync](https://github.com/jwoglom/tconnectsync) event parser by @jwoglom.

---

## Branch

- Bugfix branch: `bugfix/sensor-population-unknown-state`
- Base: `develop`
- PR: #4
