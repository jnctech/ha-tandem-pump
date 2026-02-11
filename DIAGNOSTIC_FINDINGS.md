# Diagnostic Findings - Tandem Sensor Issue

**Date**: 2026-02-11
**Issue**: #3 - Tandem sensors stuck in Unknown state

## Summary

✅ **Integration IS loaded and working partially**
❌ **Sensors are NOT being populated with data**

## Key Findings

### 1. Sensors Are Created ✅

Found multiple Tandem sensors in Home Assistant, including:
- `sensor.last_glucose_level_mmol` - **State: unknown**
- `sensor.last_glucose_level_mg_dl` - **State: unknown**
- `sensor.last_glucose_update` - **State: unknown**
- `sensor.last_glucose_delta` - **State: unknown**
- `sensor.active_insulin_iob` - **State: unknown**

**Conclusion**: The integration loads successfully, creates sensor entities, and registers them in Home Assistant. The problem is NOT with:
- Integration installation
- Sensor entity creation
- Entity registration

### 2. All Sensors Show "Unknown" State ❌

**This indicates**:
- The `TandemCoordinator._async_update_data()` method is likely **not running** OR
- The method is **running but returning empty data** OR
- The method is **encountering an exception** that's being silently caught

### 3. Sensor Entity IDs

The sensors don't use the `sensor.carelink_` prefix we expected. They use:
- `sensor.last_glucose_*`
- `sensor.active_insulin_*`

This suggests they might be using custom entity IDs rather than the default pattern.

## Root Cause Analysis

Based on the code review and these findings, the issue is in one of these areas:

### Most Likely: Coordinator Not Updating

**Location**: `custom_components/carelink/__init__.py` line 680-776

**Hypothesis**:
- The `TandemCoordinator._async_update_data()` method is failing
- The enhanced logging we added should show us what's happening
- Need to check if:
  - Login is succeeding
  - API data fetch is working
  - Data parsing is completing

### Possible Issues:

1. **API Authentication Failure**
   - `await self.client.login()` fails
   - Should log: "TandemCoordinator: Login failed"

2. **API Returns No Data**
   - `get_recent_data()` returns `None` or `{}`
   - Should log: "get_recent_data() returned None!"

3. **Data Parsing Exception**
   - Exception in `_parse_therapy_timeline()` or `_parse_dashboard_summary()`
   - Should log: "Error parsing..."

4. **Coordinator Not Running**
   - First refresh failed during setup
   - Should log: "First coordinator refresh FAILED"

## Next Steps

### CRITICAL: Enable Debug Logging

We MUST enable debug logging to see what's happening. Here's how:

#### Option 1: SSH to Home Assistant

```bash
# SSH to HA server
ssh homeassistant@192.168.88.43

# Edit configuration.yaml
nano /config/configuration.yaml

# Add these lines:
logger:
  default: info
  logs:
    custom_components.carelink: debug

# Restart Home Assistant
ha core restart

# Watch logs
tail -f /config/home-assistant.log | grep -i tandem
```

#### Option 2: Via Home Assistant UI

1. Go to: http://192.168.88.43:8123
2. Settings → System → Logs
3. Look for any "carelink" or "tandem" entries
4. If nothing shows, enable debug logging:
   - Developer Tools → YAML → Edit in configuration.yaml
   - Add logger config above
   - Restart HA

### What to Look For in Logs

Once debug logging is enabled and HA is restarted, look for these log entries in order:

1. **Integration Setup**:
   ```
   Setting up Tandem entry: [entry_id]
   TandemCoordinator created with update interval: X seconds
   Performing first coordinator refresh...
   ```

2. **First Refresh**:
   ```
   TandemCoordinator: Starting _async_update_data
   TandemCoordinator: Attempting login to Tandem Source API
   TandemCoordinator: Login successful
   TandemCoordinator: Fetching recent data from API
   TandemCoordinator: API data fetch completed
   ```

3. **Data Sources Check**:
   ```
   Tandem data sources: pump_metadata=present, pumper_info=present,
                        therapy_timeline=present, dashboard_summary=present
   ```

4. **Data Parsing**:
   ```
   TandemCoordinator: Parsing therapy timeline (present: True)
   TandemCoordinator: Therapy timeline parsed successfully
   TandemCoordinator: Parsing dashboard summary (present: True)
   TandemCoordinator: Dashboard summary parsed successfully
   ```

5. **Completion**:
   ```
   TandemCoordinator: Data dictionary populated with X keys
   First coordinator refresh completed successfully
   Coordinator data keys after first refresh: ['tandem_last_sg_mmol', ...]
   ```

### Expected vs Actual

**If everything works**, we should see:
- Login successful
- Data fetched
- All 4 data sources present
- Parsing successful
- Data dictionary has 15-20 keys
- Sensors should update

**If it fails**, we'll see WHERE it fails:
- Login failed → Credentials or region issue
- Data fetch returns None → API connectivity issue
- Data sources missing → Pump not uploading data
- Parsing errors → Data structure changed
- Dictionary empty → All parsing failed

## Files Modified for Debugging

We've added comprehensive logging to:

1. `custom_components/carelink/__init__.py`:
   - Line 272-314: Tandem entry setup logging
   - Line 680-776: Coordinator update logging
   - Line 754-768: Parsing error logging

2. `custom_components/carelink/sensor.py`:
   - Line 45-65: Sensor setup logging
   - Line 85-92: Sensor value retrieval logging

## Action Required

**IMMEDIATE**: Enable debug logging in Home Assistant and restart

**THEN**: Share the log output focusing on:
- Any lines containing "Tandem" or "carelink"
- Especially ERROR or WARNING messages
- The sequence of log messages during HA startup

Once we see the logs, we'll know exactly where the failure occurs and can fix it.

---

**Status**: Waiting for debug logs
**Next**: Analyze logs to identify exact failure point
