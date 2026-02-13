# Diagnostic Tools for Sensor Population Issue

This directory contains diagnostic tools to help troubleshoot the Tandem sensor population issue.

## Quick Start

### 0. Check Current Sensor States

First, check the current state of your sensors:

```bash
cd Home-Assistant-Tandem-Source-Carelink
python check_ha_sensors.py
```

This will show:
- Which sensors are in "Unknown" state
- Which sensors are working
- Recent errors from Home Assistant logs

**Note**: You'll need a Home Assistant Long-Lived Access Token. Add it to `test_credentials.json` as `ha_token` or pass via `--token` argument.

### 1. Enable Debug Logging in Home Assistant

Add this to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.carelink: debug
```

Then restart Home Assistant and check the logs at `Settings > System > Logs` or in `home-assistant.log`.

### 2. Run the Diagnostic Script

The diagnostic script tests the Tandem API independently from Home Assistant:

```bash
cd Home-Assistant-Tandem-Source-Carelink
python diagnostic_tandem.py
```

This will:
- Test API authentication
- Fetch data from Tandem Source API
- Analyze the data structure
- Show what sensor values can be extracted
- Save the full API response to `tandem_api_response.json` (with sensitive data redacted)

### 3. Review Home Assistant Logs

After enabling debug logging and restarting Home Assistant, look for these log messages:

#### During Integration Setup
```
TandemCoordinator created with update interval: X seconds
Performing first coordinator refresh...
First coordinator refresh completed successfully
Coordinator data keys after first refresh: [...]
```

#### During Data Updates
```
TandemCoordinator: Starting _async_update_data
TandemCoordinator: Login successful
TandemCoordinator: API data fetch completed
TandemCoordinator: Data dictionary populated with X keys
```

#### In Sensor Platform
```
Setting up sensor platform for tandem
Creating X sensor entities for tandem
Sensor setup completed - X entities added
```

## Understanding the Logs

### Expected Flow (Working)

1. **Setup**: "Setting up Tandem entry"
2. **First Refresh**: "First coordinator refresh completed successfully"
3. **Data Keys**: "Coordinator data keys after first refresh: ['tandem_last_sg_mmol', ...]"
4. **Sensor Creation**: "Creating 18 sensor entities for tandem"

### Problem Indicators

#### API Issues
```
TandemCoordinator: Login failed: [error]
TandemCoordinator: Failed to fetch data from API: [error]
```
→ **Problem**: Cannot connect to Tandem API
→ **Solution**: Check credentials, network connectivity

#### Empty Data
```
TandemCoordinator: get_recent_data() returned None!
TandemCoordinator: Data dictionary populated with 0 keys
```
→ **Problem**: API returns no data
→ **Solution**: Check API endpoint, data availability

#### Missing Data Sources
```
Tandem data sources: pump_metadata=MISSING, therapy_timeline=MISSING, ...
```
→ **Problem**: API response missing expected fields
→ **Solution**: Check API response structure with diagnostic script

#### Parsing Errors
```
TandemCoordinator: Error parsing therapy timeline: [error]
TandemCoordinator: Error parsing dashboard summary: [error]
```
→ **Problem**: Data parsing failed
→ **Solution**: Check error details, may need code fix

#### Sensor Value Issues
```
Sensor Last glucose level mmol has None value (key: tandem_last_sg_mmol not in coordinator.data)
```
→ **Problem**: Sensor key not populated in coordinator.data
→ **Solution**: Check why that specific key wasn't set during parsing

## Key Code Locations

### Tandem Setup
- **File**: `custom_components/carelink/__init__.py`
- **Function**: `_async_setup_tandem_entry()` (line ~268)
- **What it does**: Creates TandemCoordinator and performs first refresh

### Data Coordinator
- **File**: `custom_components/carelink/__init__.py`
- **Class**: `TandemCoordinator` (line ~666)
- **Method**: `_async_update_data()` (line ~680)
- **What it does**: Fetches data from API and populates coordinator.data dict

### Data Parsing
- **File**: `custom_components/carelink/__init__.py`
- **Method**: `_parse_therapy_timeline()` (line ~766)
- **Method**: `_parse_dashboard_summary()` (line ~944)
- **What they do**: Extract sensor values from API response

### Sensor Entities
- **File**: `custom_components/carelink/sensor.py`
- **Function**: `async_setup_entry()` (line ~33)
- **Property**: `native_value` (line ~84)
- **What it does**: Creates sensor entities and retrieves values from coordinator.data

## Common Issues and Solutions

### Issue: Sensors show "Unknown"

**Diagnostic Steps:**
1. Check logs for "First coordinator refresh completed successfully"
2. Check logs for "Coordinator data keys after first refresh"
3. Run `diagnostic_tandem.py` to verify API returns data
4. Check for parsing errors in logs

**Possible Causes:**
- Coordinator.data dict is empty (API issue)
- Sensor keys don't match coordinator.data keys (code issue)
- First refresh failed silently (exception handling issue)

### Issue: "Login failed"

**Diagnostic Steps:**
1. Verify credentials are correct
2. Check region setting (US vs EU)
3. Run `diagnostic_tandem.py` with same credentials
4. Check network connectivity to Tandem servers

### Issue: "Data sources MISSING"

**Diagnostic Steps:**
1. Run `diagnostic_tandem.py` to see actual API response
2. Check `tandem_api_response.json` for structure
3. Verify Tandem account has recent pump data

**Possible Causes:**
- Pump hasn't uploaded data recently
- API endpoint changed
- Account has no associated pump

## Next Steps

After reviewing logs and running diagnostics:

1. **If API connection fails**: Check credentials and network
2. **If API returns no data**: Verify pump uploads are working
3. **If data is present but sensors are Unknown**: Check parsing logic
4. **If specific sensors are Unknown**: Check sensor key mappings

## Contributing Findings

When reporting issues, please include:

1. Relevant log excerpts (with sensitive data removed)
2. Output from `diagnostic_tandem.py`
3. Which sensors are affected (all or specific ones)
4. Your Home Assistant version
5. Integration version/branch

See [ISSUE_SENSOR_POPULATION.md](ISSUE_SENSOR_POPULATION.md) for detailed technical analysis.
