# Troubleshooting Summary - Tandem Sensor Population Issue

**Issue**: [#3](https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink/issues/3)
**Branch**: `bugfix/sensor-population-unknown-state`
**Status**: Investigation in progress

## What We've Done

### 1. ✅ Created GitHub Issue
- **Issue #3**: "Tandem sensors stuck in Unknown state - not populating with data"
- Documented symptoms, technical analysis, and troubleshooting steps
- Link: https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink/issues/3

### 2. ✅ Added Comprehensive Debug Logging

Enhanced logging throughout the Tandem data flow:

**In `__init__.py` (TandemCoordinator):**
- Login attempts and success/failure
- API data fetch with type checking
- Data parsing for therapy timeline and dashboard summary
- Data dictionary population (number of keys)
- First coordinator refresh status
- Coordinator data keys after setup

**In `sensor.py` (Sensor Platform):**
- Sensor platform setup initiation
- Number of entities being created
- Entity addition to Home Assistant
- Individual sensor value retrieval (logs when value is None)

### 3. ✅ Created Diagnostic Script

**File**: `diagnostic_tandem.py`

A standalone Python script that:
- Tests Tandem API authentication independently
- Fetches and analyzes data structure
- Shows which sensor values can be extracted
- Saves full API response to JSON (with PII redacted)
- Provides step-by-step diagnostic output

**Usage**:
```bash
python diagnostic_tandem.py
```

### 4. ✅ Created Documentation

**DIAGNOSTIC_README.md**:
- Instructions for enabling debug logging
- How to run the diagnostic script
- How to interpret log messages
- Common issues and solutions
- What to look for in logs

**ISSUE_SENSOR_POPULATION.md**:
- Detailed technical analysis
- Data flow architecture
- Critical code locations
- Investigation log

## Next Steps for Troubleshooting

### Step 1: Enable Debug Logging

Add to Home Assistant `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.carelink: debug
```

Restart Home Assistant.

### Step 2: Run Diagnostic Script

```bash
cd /config/custom_components/carelink
python diagnostic_tandem.py
```

This will show if the API connection and data fetch work outside Home Assistant.

### Step 3: Review Home Assistant Logs

Look for these key log messages:

#### ✅ Good Signs
```
TandemCoordinator created with update interval: X seconds
First coordinator refresh completed successfully
Coordinator data keys after first refresh: ['tandem_last_sg_mmol', 'tandem_last_sg_mgdl', ...]
TandemCoordinator: Data dictionary populated with 20+ keys
Creating 18 sensor entities for tandem
```

#### ❌ Problem Signs
```
TandemCoordinator: Login failed: [error]
TandemCoordinator: get_recent_data() returned None!
TandemCoordinator: Data dictionary populated with 0 keys
First coordinator refresh FAILED: [error]
Tandem data sources: pump_metadata=MISSING, therapy_timeline=MISSING
Sensor [name] has None value (key: [key] not in coordinator.data)
```

### Step 4: Identify Root Cause

Based on logs, the issue will be in one of these areas:

1. **API Authentication** - Login fails
   - Check credentials, region setting
   - Verify with diagnostic script

2. **API Data Fetch** - Returns None or empty
   - Check pump has uploaded data recently
   - Verify API endpoint is accessible

3. **Data Parsing** - Exception during parsing
   - Check error messages in logs
   - May need to fix parsing logic

4. **Data Structure** - API response format changed
   - Check diagnostic script output
   - Compare with expected structure

5. **Sensor Mapping** - Keys don't match
   - Check coordinator.data keys
   - Verify sensor keys in TANDEM_SENSORS

## Files Modified

### Code Changes
- `custom_components/carelink/__init__.py` - Added logging to TandemCoordinator
- `custom_components/carelink/sensor.py` - Added logging to sensor platform

### New Files
- `diagnostic_tandem.py` - Standalone diagnostic script
- `DIAGNOSTIC_README.md` - Troubleshooting guide
- `ISSUE_SENSOR_POPULATION.md` - Issue documentation
- `TROUBLESHOOTING_SUMMARY.md` - This file

## Expected Outcomes

After running diagnostics, we should be able to determine:

1. ✅ **If API works**: Diagnostic script completes successfully
2. ✅ **If data is fetched**: Logs show "API data fetch completed"
3. ✅ **If data is structured correctly**: Diagnostic script shows all data sources present
4. ✅ **If parsing works**: Logs show "parsed successfully" for timeline and summary
5. ✅ **If coordinator is populated**: Logs show "Data dictionary populated with X keys"
6. ✅ **If sensors are created**: Logs show "X entities added"
7. ✅ **If sensor keys match**: No "None value" messages for sensors

## Contact

For questions or to report findings:
- GitHub Issue: #3
- Include relevant log excerpts
- Include diagnostic script output
- Specify which sensors are affected

---

**Last Updated**: 2026-02-11
**Commit**: f9e44ce
