# Troubleshooting Guide

Common issues and solutions for the Tandem t:slim Pump integration.

> **New installation?** The most common setup issue is the Tandem app running with battery
> optimisation enabled. If sensors show Unknown or data is stale, fix this first:
> [Mobile App Settings →](#mobile-app-settings)

---

## Mobile App Settings {#mobile-app-settings}

This integration reads from the **Tandem Source cloud** — it cannot communicate with your pump directly. The **Tandem t:slim mobile app** must be running in the background and connected to your pump via Bluetooth for uploads to occur.

When unrestricted, the app uploads pump data approximately **every 60 minutes**. HA picks up new data within minutes of each upload.

### Android — Battery Settings

Modern Android aggressively restricts background apps. The Tandem app **must** be set to unrestricted battery usage:

**1. Set battery mode to Unrestricted**
- Go to **Settings → Apps → Tandem t:slim → Battery**
- Set to **Unrestricted** (the default "Optimised" mode pauses background sync)

**2. Disable battery optimisation**
- Go to **Settings → Battery → Battery optimisation**
- Find Tandem t:slim and set to **Don't optimise**

**3. Manufacturer-specific restrictions**

Many manufacturers add extra battery management on top of Android defaults:

| Manufacturer | Setting to change |
|---|---|
| Samsung (One UI) | Settings → Battery → Background usage limits → ensure Tandem is not "sleeping" or "deep sleeping" |
| Xiaomi / MIUI | Settings → Battery → App battery saver → set Tandem to "No restrictions" |
| OnePlus / OxygenOS | Settings → Battery → Battery optimisation → Tandem → Don't optimise |
| Huawei / EMUI | Phone Manager → Power saving → Protected apps → enable Tandem |
| Google Pixel | Settings → Apps → Tandem t:slim → Battery → Unrestricted |

> **Tip:** If data gaps still appear after applying these settings, check if **Adaptive Battery** is re-restricting the app. On some devices you may need to disable Adaptive Battery entirely.

### iOS — Background App Refresh

**1. Enable Background App Refresh**
- Go to **Settings → General → Background App Refresh**
- Ensure it is **On** globally, and that **Tandem t:slim** is enabled in the list

**2. Avoid Low Power Mode during monitoring periods**
- **Settings → Battery → Low Power Mode** — when enabled, iOS pauses background refresh for all apps
- Disable Low Power Mode when continuous syncing is needed (e.g. overnight)

**3. Do not force-quit the app**
- Force-quitting from the app switcher prevents iOS from ever waking the app in the background
- Lock the screen instead and let iOS manage it

> iOS is generally more reliable for background sync than Android once Background App Refresh is enabled.

### If data gaps appear

Use the `carelink.import_history` action (Developer Tools → Actions) to backfill any missed statistics. The action is idempotent — running it over a range that already has partial data fills the gaps without overwriting existing values.

---

## Installation Issues

### Integration Not Appearing in HACS

**Symptoms**: Can't find "Tandem t:slim Pump" or "Carelink" in HACS integration list

**Solutions**:
1. Ensure custom repository is added correctly:
   - URL: `https://github.com/jnctech/ha-tandem-pump`
   - Category: Integration
2. Restart Home Assistant after adding repository
3. Clear HACS cache: HACS → 3-dot menu → Custom repositories → Reload

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
2. Check Home Assistant logs: Settings → System → Logs — look for errors mentioning "carelink"
3. Restart Home Assistant fully (not just reload)

---

## Duplicate Device After Upgrading {#duplicate-device-after-upgrade}

**Symptoms:** Two devices with the same name appear in Settings → Devices & Services after upgrading to v1.3.0+. One has all your entities, the other has 0 entities.

**Cause:** v1.3.0 changed the internal device identifier from the pump serial number to the integration's config entry ID. All entities moved to the new device, leaving the old entry empty.

**How to delete the old device:**

> **Note:** The three-dot menu on the integration page only shows "Enable/Disable" for devices with 0 entities — it does not show a Delete option there.

1. Find the device with **0 entities** in Settings → Devices & Services
2. **Click the `›` arrow** next to it (or click its name) to open the device detail page
3. Scroll to the bottom of the page — click **Delete Device**

Alternatively:
1. Go to **Settings → Devices & Services → Devices** tab (at the top of the page)
2. Search for your pump name
3. Open the device showing **0 entities**
4. Scroll to the bottom → **Delete Device**

No data is lost. All entities remain under the active device. If both devices show entities, use a [Clean Reinstall](README.md#upgrading).

---

## Configuration Issues

### Authentication Fails

**Symptoms**: "Invalid credentials" or "Login failed" errors

**Tandem Source**:
1. Verify credentials work at https://source.tandemdiabetes.com (US) or https://source.eu.tandemdiabetes.com (EU)
2. Ensure correct region selected (US/EU)
3. Check for typos in email/password
4. MFA/2FA not supported — ensure it is disabled on your Tandem Source account

**Medtronic Carelink**:
1. Verify credentials work at https://carelink.minimed.eu
2. MFA must be disabled
3. Must use care partner account for pumps

### Wrong Region Selected

**Symptoms**: Authentication fails, or no data appears

**Solution**:
1. Remove integration: Settings → Devices & Services → Carelink → Delete
2. Re-add with correct region:
   - US: source.tandemdiabetes.com
   - EU: source.eu.tandemdiabetes.com

---

## Data Issues

### All Sensors Show "Unknown" or "Unavailable"

**Possible causes**:

1. **No recent data from pump** — ensure pump has synced to Tandem Source recently (check the Source website). See [Mobile App Settings](#mobile-app-settings) above.

2. **API authentication expired** — wait for next polling cycle (default 5 minutes) or restart the integration

3. **Missing tconnectDeviceId** (Tandem only) — if pump metadata doesn't contain a `tconnectDeviceId`, the integration cannot fetch pump events. Usually means the pump hasn't uploaded to Tandem Source yet. Check logs for "No tconnectDeviceId in metadata".

### Sensors Not Updating / Delayed Updates

**Expected behaviour**:
- Integration polls every 5 minutes (configurable)
- Not real-time — depends on pump sync frequency via the Tandem t:slim app
- Sensors always show the **last known value** — they do not go unavailable between syncs

**If updates are slower than expected**:
1. Check [Mobile App Settings](#mobile-app-settings) — battery restrictions are the most common cause
2. Enable debug logging and look for transient error messages (see [Enable Debug Logging](#enable-debug-logging))
3. Use `carelink.import_history` to backfill any statistics gaps after fixing the app settings

### Missing Sensors

**Symptoms**: Some expected sensors not appearing

**Tandem Pumps**:
- All 49 sensors are populated from the Tandem Source Reports API — no ControlIQ API access required
- If sensors are missing, check HA logs for parsing errors and ensure the pump has recent data on Tandem Source

**Medtronic Pumps**:
- Ensure pump model is supported (770G, 780G)
- Guardian Connect CGM users may have a limited sensor set

---

## Nightscout Integration

### Nightscout Upload Not Working

**Symptoms**: Data not appearing in Nightscout

**Solutions**:

1. **Verify Nightscout is accessible** — open Nightscout URL in browser; you should see the dashboard

2. **Check API Secret**
   - Must be at least 12 characters, case-sensitive, no spaces or special characters

3. **Verify URL format**
   - Must include protocol: `http://` or `https://`
   - No trailing slash — example: `http://192.168.1.100:1337`

4. **Network connectivity** — if HA is in Docker, use the container name: `http://nightscout:1337`

5. Check Home Assistant logs for Nightscout upload errors

---

## Performance Issues

### High CPU Usage

**Solutions**:
1. Increase scan interval: Settings → Devices & Services → Carelink → Configure → increase to 600 or 900 seconds
2. Remove debug logging if enabled

---

## Diagnostic Steps

### Enable Debug Logging {#enable-debug-logging}

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

1. HACS → Integrations → Carelink — version shown at bottom
2. Or check `custom_components/carelink/manifest.json`

---

## Getting Help

If issues persist:

1. **Check existing issues**: https://github.com/jnctech/ha-tandem-pump/issues
2. **Create new issue** — include:
   - HA version and integration version
   - Platform (Tandem/Carelink) and region (US/EU)
   - Pump model
   - Relevant logs (remove sensitive data)
   - Diagnostic report download
