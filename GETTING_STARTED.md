# Getting Started - Troubleshooting Tandem Sensors

**Issue**: Tandem sensors stuck in "Unknown" state
**Home Assistant**: http://192.168.88.43:8123

## Prerequisites

You'll need to provide credentials in a secure file. These credentials will **never be uploaded** to GitHub (protected by `.gitignore`).

### Required Credentials:

1. **Tandem Source API credentials** (for diagnostic script)
   - Email
   - Password
   - Region (US/EU)

2. **Home Assistant Long-Lived Access Token** (for checking sensor states)
   - Create at: http://192.168.88.43:8123/profile
   - Scroll to "Long-Lived Access Tokens"
   - Click "Create Token"

## Setup Instructions

### Step 1: Create Your Credentials File

```bash
cd Home-Assistant-Tandem-Source-Carelink

# Copy the template
cp test_credentials.json.template test_credentials.json

# Edit with your actual credentials
# Use any text editor (notepad, vim, nano, etc.)
notepad test_credentials.json
```

**Format** (replace with your actual values):
```json
{
  "tandem_email": "your.email@example.com",
  "tandem_password": "YourActualPassword",
  "tandem_region": "EU",
  "ha_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Security Note**: This file is gitignored and will NEVER be committed. ✅

### Step 2: Verify Security

```bash
# Verify the file is gitignored
git check-ignore test_credentials.json

# Should output: test_credentials.json
# If it doesn't, STOP and report this issue!
```

## Diagnostic Steps

Run these scripts in order to diagnose the issue:

### Script 1: Check Home Assistant Sensor States

```bash
python check_ha_sensors.py
```

**What it does**:
- Shows which sensors are "Unknown"
- Shows which sensors are working
- Displays recent errors from HA logs

**Expected output**:
```
❌ Sensors in UNKNOWN state (18):
  - Last glucose level mmol
  - Last glucose level mg/dl
  - ...

✅ Sensors with values (0):

Summary:
  Total sensors: 18
  Unknown: 18
  Working: 0
```

### Script 2: Test Tandem API Connection

```bash
python diagnostic_tandem.py
```

**What it does**:
- Tests Tandem Source API authentication
- Fetches data from API
- Shows data structure
- Saves API response to file (for analysis)

**Expected output**:
```
Step 1: Creating Tandem client
✓ Tandem client created successfully (Region: EU)

Step 2: Testing API login
✓ Login successful!

Step 3: Fetching recent data
✓ Data fetched successfully (type: <class 'dict'>)

Step 4: Analyzing data structure
Data sources present:
  pump_metadata: ✓ PRESENT
  therapy_timeline: ✓ PRESENT
  dashboard_summary: ✓ PRESENT
...
```

### Script 3: Check Home Assistant Debug Logs

After enabling debug logging (see below), check the Home Assistant logs:

```bash
# If you have access to the HA server
ssh homeassistant@192.168.88.43
tail -f /config/home-assistant.log | grep -i tandem
```

Or view in the UI:
- Go to http://192.168.88.43:8123
- Settings → System → Logs
- Filter for "carelink" or "tandem"

## Enable Debug Logging

### Option A: Via Home Assistant UI

1. Go to http://192.168.88.43:8123/config/logs
2. Set log level to "Debug" for `custom_components.carelink`
3. Restart Home Assistant

### Option B: Via Configuration File

Add to `/config/configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.carelink: debug
```

Then restart Home Assistant:
- Settings → System → Restart

## What to Look For

### In Home Assistant Logs

**✅ Good signs (integration working)**:
```
TandemCoordinator: Login successful
TandemCoordinator: API data fetch completed
TandemCoordinator: Data dictionary populated with 20+ keys
First coordinator refresh completed successfully
Coordinator data keys after first refresh: ['tandem_last_sg_mmol', ...]
```

**❌ Problem signs (integration failing)**:
```
TandemCoordinator: Login failed: [error]
TandemCoordinator: get_recent_data() returned None!
TandemCoordinator: Data dictionary populated with 0 keys
First coordinator refresh FAILED: [error]
Tandem data sources: pump_metadata=MISSING
```

### In Diagnostic Script

**✅ API is working**:
- All steps show ✓ checkmarks
- Data sources all show "PRESENT"
- Sensor values extracted successfully

**❌ API not working**:
- Login fails
- Data fetch returns None
- Data sources show "MISSING"

## Next Steps Based on Results

### Scenario 1: API Works, HA Sensors Don't

If `diagnostic_tandem.py` succeeds but sensors are Unknown:
- **Issue**: Problem in Home Assistant integration
- **Action**: Check HA logs for errors during coordinator refresh
- **Location**: Issue in `__init__.py` coordinator or sensor setup

### Scenario 2: API Fails

If `diagnostic_tandem.py` fails:
- **Issue**: Tandem API connection problem
- **Check**: Credentials, region setting, network connectivity
- **Action**: Fix API connection first before debugging HA

### Scenario 3: API Works, But Missing Data

If API succeeds but shows data sources "MISSING":
- **Issue**: Tandem account has no recent pump data
- **Check**: When was the last pump upload?
- **Action**: Verify pump is uploading to Tandem Source

### Scenario 4: Everything Appears to Work

If both API and HA logs look good but sensors still Unknown:
- **Issue**: Sensor key mismatch or timing issue
- **Check**: Verify `coordinator.data` keys match `TANDEM_SENSORS` keys
- **Action**: We'll need to dig deeper into the code

## Reporting Findings

When you report back, please include:

1. **Output from `check_ha_sensors.py`**
   - How many sensors are Unknown?
   - Are any sensors working?

2. **Output from `diagnostic_tandem.py`**
   - Did login succeed?
   - Were data sources present?
   - Were sensor values extracted?

3. **Relevant log excerpts** (with sensitive data removed)
   - From Home Assistant logs
   - Look for ERROR or WARNING messages

4. **File created**: `tandem_api_response.json`
   - This file has PII redacted
   - Can share for structure analysis

## Getting Help

- **GitHub Issue**: #3
- **Branch**: `bugfix/sensor-population-unknown-state`
- Include outputs from all diagnostic scripts
- Attach (redacted) log excerpts

---

**Remember**: All credential files are gitignored. You can safely create and use `test_credentials.json` for testing.
