# Troubleshooting Guide

Common issues and solutions for the Tandem Source / Carelink integration.

## Installation Issues

### Integration Not Appearing in HACS

**Symptoms**: Can't find "Carelink" in HACS integration list

**Solutions**:
1. Ensure custom repository is added correctly:
   - URL: `https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink`
   - Category: Integration

2. Restart Home Assistant after adding repository

3. Clear HACS cache:
   - HACS → 3-dot menu → Custom repositories → Reload

### Integration Won't Load After Installation

**Symptoms**: No "Carelink" option in Add Integration dialog

**Solutions**:
1. Verify files are in correct location:
```
config/
└── custom_components/
    └── carelink/
        ├── __init__.py
        ├── manifest.json
        └── [other files]
```

2. Check Home Assistant logs:
   - Settings → System → Logs
   - Look for errors mentioning "carelink"

3. Restart Home Assistant fully (not just reload)

## Configuration Issues

### "Invalid handler specified" Error (v0.1.0.beta only)

**Symptoms**: Config flow crashes with "Invalid handler specified"

**Solution**: This was a bug in v0.1.0.beta. Upgrade to v0.1.3-beta or later.

### SSL Certificate Errors

**Symptoms**: Integration fails to load with SSL or certificate errors

**Solution**:
- Fixed in v0.1.3-beta
- Ensure you're running v0.1.3-beta or later
- Check `custom_components/carelink/manifest.json` contains `"certifi>=2023.0.0"` in requirements

### Authentication Fails

**Symptoms**: "Invalid credentials" or "Login failed" errors

**Tandem Source**:
1. Verify credentials work at https://source.tandemdiabetes.com (US) or https://source.eu.tandemdiabetes.com (EU)
2. Ensure correct region selected (US/EU)
3. Check for typos in email/password
4. MFA/2FA not supported - ensure it's disabled

**Medtronic Carelink**:
1. Verify credentials work at https://carelink.minimed.eu
2. MFA must be disabled
3. Must use care partner account for pumps
4. Guardian Connect may work with patient account

### Wrong Region Selected

**Symptoms**: Authentication fails, or no data appears

**Solution**:
1. Remove integration: Settings → Devices & Services → Carelink → Delete
2. Re-add with correct region:
   - US: source.tandemdiabetes.com
   - EU: source.eu.tandemdiabetes.com

## Data Issues

### All Sensors Show "Unknown"

**Symptoms**: Integration loads, but all sensors show "Unknown" or "Unavailable"

**Most Likely Cause** (Tandem, v0.1.3-beta and earlier):
The ControlIQ API endpoints return 404 errors, leaving all sensors unpopulated. **Upgrade to the latest version** which uses the Source Reports pumpevents API instead.

**Other Possible Causes**:

1. **No recent data from pump**
   - Ensure pump has synced to Source recently (check Source website)
   - Tandem pumps sync when connected to phone with t:connect app

2. **API authentication expired**
   - Wait for next polling cycle (default: 5 minutes)
   - Or restart integration

3. **Missing tconnectDeviceId** (Tandem only)
   - If pump_metadata doesn't contain a `tconnectDeviceId`, the integration cannot fetch pump events
   - Check logs for "No tconnectDeviceId in metadata"
   - This usually means the pump hasn't uploaded to Tandem Source yet

### Sensors Not Updating / Delayed Updates

**Symptoms**: Sensors show old data, updates take longer than the configured scan interval

**Expected Behavior**:
- Integration polls API every 5 minutes (default scan interval)
- Not real-time — depends on pump sync frequency via t:connect mobile app
- Adjust scan interval in configuration if needed (60–900 seconds)

**If updates are slower than expected**:
1. **Check logs for transient errors**: Enable debug logging and look for `Tandem: transient error` messages. The integration retries failed API calls automatically (up to 2 retries with 2s/4s backoff).
2. **Check for `UpdateFailed` messages**: If the coordinator reports `UpdateFailed`, Home Assistant will use exponential backoff before retrying. This is normal recovery behaviour after network issues.
3. **Timezone mismatch**: If your HA server is in a different timezone to your pump, ensure the integration's configured timezone matches the pump's timezone. The API date range uses this to avoid missing recent data.
4. **Network stability**: Unstable connections can trigger retries. Check your HA server's network connectivity to `source.eu.tandemdiabetes.com` (EU) or `source.tandemdiabetes.com` (US).

### Missing Sensors

**Symptoms**: Some expected sensors not appearing

**Tandem Pumps**:
- If ControlIQ sensors (basal rate, IOB) are missing, this is expected
- Source OIDC tokens may not grant access to ControlIQ API
- Check logs for "ControlIQ therapy timeline not available"

**Medtronic Pumps**:
- Ensure pump model is supported (770G, 780G)
- Guardian Connect CGM users may have limited sensor set

## Nightscout Integration

### Nightscout Upload Not Working

**Symptoms**: Data not appearing in Nightscout

**Solutions**:

1. **Verify Nightscout is accessible**
   - Open Nightscout URL in browser
   - Should see dashboard

2. **Check API Secret**
   - Must be at least 12 characters
   - Case-sensitive
   - No spaces or special characters

3. **Verify URL format**
   - Must include protocol: `http://` or `https://`
   - No trailing slash
   - Example: `http://192.168.1.100:1337`

4. **Network connectivity**
   - If HA is in Docker, ensure containers can communicate
   - Use container name if on same Docker network: `http://nightscout:1337`
   - Use host IP for external access

5. **Check Home Assistant logs**
   - Look for Nightscout upload errors
   - May show authentication or network issues

## Performance Issues

### High CPU Usage

**Symptoms**: Home Assistant slow, high CPU usage when integration is active

**Solutions**:
1. Increase scan interval (default 300s):
   - Settings → Devices & Services → Carelink → Configure
   - Increase to 600 or 900 seconds

2. Check for excessive logging:
   - Remove debug logging if enabled
   - Settings → System → Logs

### Blocking Call Warning (Pre-v0.1.3-beta)

**Symptoms**: Log shows "Detected blocking call to load_verify_locations"

**Solution**: Upgrade to v0.1.3-beta or later. This was fixed in v0.1.3-beta.

## Diagnostic Steps

### Enable Debug Logging

Add to `configuration.yaml`:

```yaml
logger:
  default: warning
  logs:
    custom_components.carelink: debug
```

Restart Home Assistant, then check logs for detailed information.

### Generate Diagnostic Report

1. Settings → Devices & Services → Carelink
2. Click on device (pump)
3. Three-dot menu → Download Diagnostics
4. Share with support (remove sensitive data first)

### Check Integration Version

1. HACS → Integrations → Carelink
2. Version shown at bottom
3. Or check `custom_components/carelink/manifest.json`

### Verify Installation Integrity

```bash
# Check all required files exist
ls config/custom_components/carelink/
# Should show: __init__.py, manifest.json, api.py, tandem_api.py, etc.

# Check manifest version
cat config/custom_components/carelink/manifest.json | grep version
```

## Getting Help

If issues persist:

1. **Check existing issues**: https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink/issues
2. **Create new issue**:
   - Include HA version
   - Include integration version
   - Include relevant logs (remove sensitive data)
   - Include diagnostic report
3. **Provide details**:
   - Platform type (Tandem/Carelink)
   - Region (US/EU)
   - Pump model
   - When issue started
   - What you've already tried

## Known Issues

### v0.2.0-rc1

**Resolved**: Primary sensor population now works via Source Reports pumpevents API.

**Added**: Historical data import with state replay and long-term statistics.

**Remaining** (Issue #5): The following sensors still show "Unknown":
- **Average Glucose, Time in Range, CGM Usage**: Require dashboard_summary from ControlIQ API (returns 404). Planned fix: compute from CGM event history.
- **Last Pump Upload, Last Update**: Metadata timestamp parsing not yet implemented. Quick fix available.
- **Last Glucose Delta**: Self-resolving - requires two update cycles to calculate.

### v0.1.3-beta

- ControlIQ API (`tdcservices.eu.tandemdiabetes.com`) returns 404 with Source OIDC tokens
- All Tandem sensors stuck in "Unknown" state (fixed in unreleased - PR #4)
- Fix switches to Source Reports pumpevents API as primary data source

### v0.1.0.beta (DEPRECATED - DO NOT USE)

- Critical bug: "Invalid handler specified" error
- Integration fails to load
- Use v0.1.3-beta instead
