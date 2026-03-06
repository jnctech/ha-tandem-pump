# Tandem t:slim Pump for Home Assistant

[![release](https://img.shields.io/github/v/release/jnctech/ha-tandem-pump)](https://github.com/jnctech/ha-tandem-pump/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![project stage](https://img.shields.io/badge/project%20stage-production%20ready-brightgreen.svg)](https://github.com/jnctech/ha-tandem-pump)
[![downloads](https://img.shields.io/github/downloads/jnctech/ha-tandem-pump/total)](https://github.com/jnctech/ha-tandem-pump/releases)

[![commits since latest release](https://img.shields.io/github/commits-since/jnctech/ha-tandem-pump/latest)](https://github.com/jnctech/ha-tandem-pump/commits/develop)
[![commit activity](https://img.shields.io/github/commit-activity/m/jnctech/ha-tandem-pump)](https://github.com/jnctech/ha-tandem-pump/commits/develop)
[![build](https://img.shields.io/github/actions/workflow/status/jnctech/ha-tandem-pump/ci.yml?branch=develop&label=build)](https://github.com/jnctech/ha-tandem-pump/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/jnctech/ha-tandem-pump)](LICENSE)

**The most comprehensive Tandem insulin pump integration for Home Assistant.** Monitor your Tandem t:slim X2 pump with **45+ sensors**, long-term statistics, glucose history graphs, insulin delivery tracking, pump settings, and full basal profile visibility — all directly in your smart home.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jnctech&repository=ha-tandem-pump&category=integration)

---

## Why This Integration?

If you use a **Tandem t:slim X2** insulin pump with Home Assistant, this is the only integration that gives you direct access to your pump data. No Nightscout relay, no third-party cloud — just your Tandem Source account connected straight to HA.

- **45 sensors** covering glucose, insulin delivery, pump status, CGM stats, and pump settings
- **Long-term statistics** — glucose, IOB, and basal rate imported into HA's statistics engine for native Statistics Graph cards
- **Last-known value** — sensors always show the most recent reading, even if the pump hasn't synced recently
- **Smart polling** — skips expensive API calls when no new data exists, reducing token usage
- **Computed summaries** — TIR, average glucose, GMI, daily insulin totals all computed locally from your pump events
- **Full pump settings** — see your active profile, basal schedule, Control-IQ config, alert thresholds
- **Manual backfill** — `carelink.import_history` action lets you fill gaps if the mobile app was not syncing

---

## Sensors at a Glance

### Glucose Monitoring (10 sensors)
| Sensor | Description |
|--------|-------------|
| Last glucose (mmol/L) | Latest CGM reading in mmol/L |
| Last glucose (mg/dL) | Latest CGM reading in mg/dL |
| Glucose delta | Change since previous reading |
| Average glucose (mmol/L) | Daily average (computed from CGM events) |
| Average glucose (mg/dL) | Daily average (computed from CGM events) |
| Time in Range | % of readings 70–180 mg/dL |
| Time below range | % of readings below 70 mg/dL |
| Time above range | % of readings above 180 mg/dL |
| Glucose SD / CV | Standard deviation and coefficient of variation |
| GMI | Glucose Management Indicator |

### Insulin Delivery (10 sensors)
| Sensor | Description |
|--------|-------------|
| Active insulin (IOB) | Insulin on board |
| Basal rate | Current basal rate (U/hr) |
| Last bolus | Most recent bolus amount and timestamp |
| Last meal bolus | Most recent meal bolus (units) |
| Total daily insulin | TDI for today |
| Daily bolus / basal totals | Split with basal percentage |
| Daily bolus count | Number of boluses today |
| Daily carbs | Total carbs entered today |
| Last carb entry | Most recent carb entry with timestamp |

### Pump Status (7 sensors)
| Sensor | Description |
|--------|-------------|
| Control-IQ status | Open Loop / Closed Loop |
| Activity mode | Normal / Sleep / Exercise / Eating Soon |
| Pump suspended | Suspended / Active |
| Cartridge insulin | Remaining insulin (units) |
| Last cartridge change | Timestamp of last cartridge fill |
| Last site change | Timestamp (derived from cartridge fill) |
| Last tubing change | Timestamp of last tubing prime |

### Pump Settings (11 sensors)
| Sensor | Description |
|--------|-------------|
| Active basal profile | Profile name with full schedule as attributes |
| Control-IQ enabled | On / Off |
| Control-IQ weight | Configured weight (kg) |
| Control-IQ TDI | Configured total daily insulin |
| Max bolus | Maximum bolus limit (units) |
| Basal rate limit | Maximum basal rate (U/hr) |
| CGM high/low alerts | Alert thresholds (mg/dL) |
| BG high/low thresholds | BG alert thresholds (mg/dL) |
| Low insulin alert | Low reservoir threshold (units) |

### Device Info & Timestamps (7 sensors)
| Sensor | Description |
|--------|-------------|
| Last glucose update | When the last CGM reading was received |
| Last pump upload | When the pump last uploaded to Tandem Source |
| Last update | Integration data refresh timestamp |
| Pump serial number | Device serial |
| Pump model | Model name |
| Software version | Firmware version |
| CGM usage | Percentage of time CGM was active |

### Long-Term Statistics
Three metrics are imported into HA's statistics engine on every poll cycle that contains new data:
- **CGM glucose** — for native Statistics Graph cards
- **Insulin on board (IOB)** — track IOB trends over days/weeks
- **Basal rate** — monitor basal delivery patterns

Use the [`carelink.import_history` action](#actions) to backfill statistics for any days where the app was not syncing.

---

## Installation

### HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jnctech&repository=ha-tandem-pump&category=integration)

Or manually:
1. Open **HACS** in Home Assistant
2. Go to **Integrations** > **3-dot menu** > **Custom repositories**
3. Add: `https://github.com/jnctech/ha-tandem-pump`
4. Category: **Integration**
5. Click **Add**, find **"Tandem t:slim Pump"** and click **Download**
6. Restart Home Assistant

### Manual Installation

Copy `custom_components/carelink/` to your HA `config/custom_components/` directory and restart.

---

## Configuration

1. **Settings** > **Devices & Services** > **Add Integration**
2. Search for **"Carelink"**
3. Select **Tandem t:slim** as platform
4. Enter your **Tandem Source** email, password, and region (EU/US)
5. Set scan interval (default: 300 seconds)

### Prerequisites
- A **Tandem t:slim X2** pump syncing to [Tandem Source](https://source.tandemdiabetes.com)
- The **Tandem t:slim mobile app** installed, paired to your pump, and running with background activity permitted (see below)
- Home Assistant **2023.1.0** or later

---

## Mobile App & Sync Reliability

**This integration depends entirely on the Tandem t:slim mobile app** to upload pump data to Tandem Source. The integration reads from Tandem Source — it cannot talk to your pump directly. If the app is restricted by battery management, your HA sensors will continue showing the last known values but will not update until the app syncs again.

### How often does data sync?

Based on real-world observation, when the app is unrestricted:

- The app uploads pump data to Tandem Source approximately **every 60 minutes**
- HA polls every 5 minutes and detects new data within a few minutes of each upload
- A typical sync cycle produces ~600–1,000 CGM readings and ~1,000 basal statistics entries

> The app must be **connected to your pump via Bluetooth** for uploads to occur. Keep the phone nearby with Bluetooth on.

### Android — Recommended Settings

Modern Android aggressively restricts background apps to save battery. The Tandem app **must** be set to unrestricted battery usage:

**1. Set battery mode to Unrestricted**
- Go to **Settings → Apps → Tandem t:slim → Battery**
- Set to **Unrestricted** (the default is "Optimised" which will pause background sync)

**2. Check manufacturer-specific restrictions**

Many Android manufacturers add their own battery management on top of Android's defaults:

| Manufacturer | Where to look |
|-------------|---------------|
| Samsung (One UI) | Settings → Battery → Background usage limits → ensure Tandem is not listed as "sleeping" or "deep sleeping" |
| Xiaomi / MIUI | Settings → Battery → App battery saver → set Tandem to "No restrictions" |
| OnePlus / OxygenOS | Settings → Battery → Battery optimisation → Tandem → Don't optimise |
| Huawei / EMUI | Phone Manager → Power saving → Protected apps → enable Tandem |
| Google Pixel | Settings → Apps → Tandem t:slim → Battery → Unrestricted |

**3. Disable battery optimisation (all Android)**
- Go to **Settings → Battery → Battery optimisation** (or search "Battery optimisation")
- Find Tandem t:slim and set to **Don't optimise**

> **Tip:** If data gaps still appear after applying these settings, check if **Adaptive Battery** or **Device Health Services** is re-restricting the app. On some devices you may need to disable adaptive battery entirely.

### iOS — Recommended Settings

**1. Enable Background App Refresh**
- Go to **Settings → General → Background App Refresh**
- Ensure it is **On** globally, and that **Tandem t:slim** is enabled in the list

**2. Avoid Low Power Mode during critical periods**
- **Settings → Battery → Low Power Mode** — when enabled, iOS pauses background refresh for all apps
- Disable Low Power Mode when you need continuous syncing (e.g. overnight monitoring)

**3. Do not force-quit the app**
- Force-quitting an app from the app switcher prevents iOS from ever waking it in the background
- Instead, just lock the screen and let iOS manage it

> **Note:** iOS is generally more reliable for background sync than Android once Background App Refresh is enabled.

### If data gaps appear

Use the [`carelink.import_history` action](#actions) to backfill any days where the app was not syncing. The action is idempotent — running it for a range that partially has data will fill the gaps without affecting what is already there.

---

## Actions

### `carelink.import_history`

Manually imports pump events for a specified date range as long-term statistics (CGM glucose, active insulin, and basal rate). This is the primary recovery tool for periods when the Tandem app was not syncing in the background.

**To use:** Go to **Developer Tools → Actions** in Home Assistant, search for `carelink.import_history`, set your date range, and click **Perform action**.

| Field | Required | Description |
|-------|----------|-------------|
| `start_date` | ✅ Yes | First date to import (date picker or YYYY-MM-DD) |
| `end_date` | No | Last date to import (date picker or YYYY-MM-DD). Defaults to today if not set |

**How it works:**
- The date range is fetched in 7-day chunks to avoid API timeouts on large requests
- Each chunk calls the Tandem Source pump events API and imports any CGM, IOB, and basal rate statistics found
- If a chunk fails (e.g. network timeout), it is logged and skipped — remaining chunks continue
- Running the same range multiple times is **safe and idempotent** — existing statistics are updated with the same values, missing hours are filled in

**Recommended usage:**

| Scenario | Suggested range |
|----------|----------------|
| App was backgrounded for a day | yesterday → today |
| App not syncing for a week | 7 days ago → today |
| Initial backfill after first install | integration start date → today (run in monthly chunks for best reliability) |
| First install — fill all available history | Use `minDateWithEvents` from pump metadata as start date; run 1 month at a time |

> **Maximum single run:** Up to **1 month** is recommended per action call. Larger ranges will work but take longer. There is no HA session timeout — the action runs in the background.

---

## Dashboard

A starter dashboard YAML with ApexCharts glucose and insulin graphs is included at [`examples/dashboard.yaml`](examples/dashboard.yaml). It provides:
- Live glucose display with trend arrow
- 24-hour glucose history graph (pump CGM overlay)
- Insulin delivery graph (bolus + basal)
- All sensor values in a grid

---

## How It Works

This integration connects to the **Tandem Source Reports API** — the same API that powers the Tandem Source website. It decodes the proprietary binary pump event format (26-byte records with Tandem epoch timestamps) to extract all sensor data.

**Data flow:** Pump → Tandem t:slim mobile app → Tandem Source cloud → This integration → Home Assistant

The integration polls every 5 minutes (configurable) and:
1. Checks lightweight metadata to see if new data exists (skips the full fetch if the pump hasn't uploaded since last poll)
2. Fetches binary pump events (15 event types) when new data is available
3. Decodes events, computes daily summaries, extracts pump settings
4. Imports long-term statistics for HA's native graph cards
5. Sensors always show the most recent value received — use the `Last pump upload` sensor to see when data was last refreshed

---

## Medtronic Carelink Support

This integration was forked from [@yo-han's Carelink integration](https://github.com/yo-han/Home-Assistant-Carelink). The Medtronic Carelink code path is preserved but **has not been tested** under this fork. If you use a Medtronic pump, please use the [original repository](https://github.com/yo-han/Home-Assistant-Carelink) for verified support.

---

## Optional: Nightscout

The integration can optionally upload glucose data to a [Nightscout](http://www.nightscout.info/) instance. Configure the Nightscout URL and API secret in the integration options. See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for Nightscout setup details.

---

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues including:
- Integration not loading
- Authentication failures
- Sensors stuck on "Unknown"
- Data not updating

---

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, branch strategy, and testing requirements.

---

## Credits

- Tandem Source integration by [@jnctech](https://github.com/jnctech)
- Original Carelink integration by [@yo-han](https://github.com/yo-han/Home-Assistant-Carelink)
- Carelink API based on work by [@ondrej1024](https://github.com/ondrej1024)
- Binary event format reference from [tconnectsync](https://github.com/jwoglom/tconnectsync) by [@jwoglom](https://github.com/jwoglom)
