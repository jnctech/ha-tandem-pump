# Tandem t:slim Pump for Home Assistant

[![release](https://img.shields.io/github/v/release/jnctech/ha-tandem-pump)](https://github.com/jnctech/ha-tandem-pump/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![build](https://img.shields.io/github/actions/workflow/status/jnctech/ha-tandem-pump/ci.yml?branch=develop&label=build)](https://github.com/jnctech/ha-tandem-pump/actions/workflows/ci.yml)
[![License](https://img.shields.io/github/license/jnctech/ha-tandem-pump)](LICENSE)

**49+ sensors from your Tandem t:slim X2 insulin pump — live glucose, IOB, Control-IQ status, basal profile, and long-term statistics — directly in Home Assistant.** No Nightscout relay required.

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jnctech&repository=ha-tandem-pump&category=integration)

---

## Features

- 🩸 **Live CGM readings** — glucose (mmol/L + mg/dL), delta, Time in Range, GMI, SD, CV
- 💉 **Insulin delivery** — IOB, basal rate, last bolus, TDI, daily bolus/basal totals
- ⚙️ **Control-IQ status** — open/closed loop mode, activity mode (Sleep/Exercise), pump suspended
- 📋 **Full pump settings** — active basal profile with schedule, CIQ config, alert thresholds
- 📈 **Long-term statistics** — CGM glucose, IOB, and basal rate in HA's statistics engine for Statistics Graph cards
- 🕐 **Last-known value** — sensors always show the most recent reading; no "unavailable" gaps between syncs
- ⚡ **Smart polling** — skips the full API fetch when the pump hasn't uploaded since last poll
- 🔄 **Manual backfill** — `carelink.import_history` action recovers missed statistics for any date range

---

## Sensors (49)

| Category | Count | Includes |
|---|---|---|
| Glucose Monitoring | 12 | CGM readings, delta, rate of change, CGM status, avg glucose, TIR, time below/above range, SD, CV, GMI |
| Insulin Delivery | 10 | IOB, basal rate, last bolus/meal, TDI, daily totals, carbs, bolus count |
| Pump Status | 9 | Control-IQ mode, activity mode, suspended state + reason, cartridge level + fill amount, site/cartridge/tubing changes |
| Pump Settings | 11 | Active basal profile + schedule, CIQ config, max bolus/basal limits, CGM + BG alert thresholds |
| Device & Timestamps | 7 | Last glucose update, last upload, serial, model, software version, CGM usage |

<details>
<summary>Full sensor list</summary>

### Glucose Monitoring (12)
| Sensor | Description |
|---|---|
| Last glucose (mmol/L) | Latest CGM reading in mmol/L |
| Last glucose (mg/dL) | Latest CGM reading in mg/dL |
| Glucose delta | Change since previous reading |
| CGM rate of change | Rate of glucose change (mg/dL/min) |
| CGM status | Sensor signal quality (Normal / High / Low) |
| Average glucose (mmol/L) | Daily average computed from CGM events |
| Average glucose (mg/dL) | Daily average computed from CGM events |
| Time in Range | % of readings 70–180 mg/dL |
| Time below range | % of readings below 70 mg/dL |
| Time above range | % of readings above 180 mg/dL |
| Glucose SD / CV | Standard deviation and coefficient of variation |
| GMI | Glucose Management Indicator |

### Insulin Delivery (10)
| Sensor | Description |
|---|---|
| Active insulin (IOB) | Insulin on board |
| Basal rate | Current basal rate (U/hr) |
| Last bolus | Most recent bolus amount and timestamp |
| Last meal bolus | Most recent meal bolus (units) |
| Total daily insulin | TDI for today |
| Daily bolus / basal totals | Split with basal percentage |
| Daily bolus count | Number of boluses today |
| Daily carbs | Total carbs entered today |
| Last carb entry | Most recent carb entry with timestamp |

### Pump Status (9)
| Sensor | Description |
|---|---|
| Control-IQ status | Open Loop / Closed Loop |
| Activity mode | Normal / Sleep / Exercise / Eating Soon |
| Pump suspended | Suspended / Active |
| Pump suspend reason | User / Alarm / Malfunction / Auto-PLGS |
| Cartridge insulin | Remaining insulin (units) |
| Last cartridge fill amount | Fill volume from API (units; often Unknown — see below) |
| Last cartridge change | Timestamp of last cartridge fill |
| Last site change | Timestamp (derived from cartridge fill) |
| Last tubing change | Timestamp of last tubing prime |

### Pump Settings (11)
| Sensor | Description |
|---|---|
| Active basal profile | Profile name with full schedule as attributes |
| Control-IQ enabled | On / Off |
| Control-IQ weight | Configured weight (kg) |
| Control-IQ TDI | Configured total daily insulin |
| Max bolus | Maximum bolus limit (units) |
| Basal rate limit | Maximum basal rate (U/hr) |
| CGM high/low alerts | Alert thresholds (mg/dL) |
| BG high/low thresholds | BG alert thresholds (mg/dL) |
| Low insulin alert | Low reservoir threshold (units) |

### Device Info & Timestamps (7)
| Sensor | Description |
|---|---|
| Last glucose update | When the last CGM reading was received |
| Last pump upload | When the pump last uploaded to Tandem Source |
| Last update | Integration data refresh timestamp |
| Pump serial number | Device serial |
| Pump model | Model name |
| Software version | Firmware version |
| CGM usage | Percentage of time CGM was active |

</details>

**Long-term statistics** — CGM glucose, IOB, basal rate, meal carbs, total bolus, and correction bolus are imported into HA's statistics engine on every sync. Use native Statistics Graph cards for daily/weekly/monthly trends, or backfill gaps with [`carelink.import_history`](#actions).

> **Note on "Last cartridge fill amount":** The Tandem Source API typically returns 0 for the fill volume, so this sensor usually shows Unknown. Set the **Cartridge fill volume** number entity manually when you change your cartridge — the integration uses that value to estimate remaining insulin.

---

## Installation

### HACS (Recommended)

Click the button above, or manually:
1. HACS → Integrations → ⋮ → **Custom repositories** → add `https://github.com/jnctech/ha-tandem-pump` (category: Integration)
2. Find **"Tandem t:slim Pump"**, click **Download**, then restart Home Assistant

### Manual

Copy `custom_components/carelink/` into your HA `config/custom_components/` directory and restart.

---

## Upgrading

### HACS
1. HACS → Integrations → find **"Tandem t:slim Pump"** → **Update**
2. Restart Home Assistant
3. Your pump device and all entities continue working normally

> **Upgrading from v1.2.x?** v1.3.0 changed the internal device identifier used by HA.
> You may see a duplicate "Tandem Pump" device with 0 entities after restarting.
> See [Duplicate Device After Upgrading](TROUBLESHOOTING.md#duplicate-device-after-upgrade) for how to remove it.

### Manual
Replace `custom_components/carelink/` in `config/custom_components/` with the new version, then restart.

### Clean Reinstall
Use this if entities do not appear after an update:
1. Note your credentials (email, region, scan interval)
2. **Settings → Devices & Services → Carelink → Delete**
3. Update (HACS or manual) and restart Home Assistant
4. **Settings → Devices & Services → Add Integration → search "Carelink"**
5. Re-enter your credentials

> **New in v1.4.0:** Four new sensors (CGM rate of change, CGM status, last cartridge fill amount, pump suspend reason) and a correction bolus long-term statistic appear automatically after upgrading. Backfill historical correction bolus data with **Developer Tools → Actions → carelink.import_history**.

---

## Configuration

1. **Settings → Devices & Services → Add Integration**
2. Search for **"Carelink"**
3. Select **Tandem t:slim** as the platform
4. Enter your **Tandem Source** email, password, and region (EU / US)
5. Set scan interval (default: 300 seconds)

**Prerequisites:** A Tandem t:slim X2 pump syncing to [Tandem Source](https://source.tandemdiabetes.com) via the Tandem t:slim mobile app, and Home Assistant **2023.1.0+**.

---

## Mobile App & Sync

Data flows: **Pump → Tandem t:slim app → Tandem Source cloud → This integration → HA**

The app uploads pump data approximately **every 60 minutes** when unrestricted. HA picks up new data within minutes of each upload.

- **Android:** Set Tandem t:slim to **Unrestricted** battery usage (Settings → Apps → Tandem t:slim → Battery). Most manufacturers add extra restrictions — [full per-manufacturer settings →](TROUBLESHOOTING.md#mobile-app-settings)
- **iOS:** Enable **Background App Refresh** (Settings → General → Background App Refresh → Tandem t:slim: On). Avoid Low Power Mode. Do not force-quit the app.
- **Data gaps:** Use `carelink.import_history` to recover missed statistics after fixing app settings.

---

## Actions

### `carelink.import_history`

Backfill long-term statistics (CGM glucose, IOB, basal rate) for any date range where the Tandem app was not syncing.

**Developer Tools → Actions → search `carelink.import_history`**

| Field | Required | Description |
|---|---|---|
| `start_date` | ✅ | First date to import (date picker or YYYY-MM-DD) |
| `end_date` | — | Last date to import. Defaults to today |

- Fetches in 7-day chunks — safe on large date ranges
- **Idempotent** — running the same range twice is safe; gaps are filled, existing data is unchanged
- Recommended max per run: **1 month**

| Scenario | Suggested range |
|---|---|
| App backgrounded for a day | yesterday → today |
| App not syncing for a week | 7 days ago → today |
| First install — full backfill | integration start date → today (run in monthly chunks) |

---

## Dashboard

A starter dashboard with ApexCharts glucose and insulin graphs is at [`examples/dashboard.yaml`](examples/dashboard.yaml).

---

## Troubleshooting & Support

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for installation issues, authentication errors, missing sensors, Nightscout setup, and debug logging.

Open an issue: https://github.com/jnctech/ha-tandem-pump/issues

---

## Credits

- Tandem Source integration by [@jnctech](https://github.com/jnctech)
- Original Carelink integration by [@yo-han](https://github.com/yo-han/Home-Assistant-Carelink)
- Binary event format reference from [tconnectsync](https://github.com/jwoglom/tconnectsync) by [@jwoglom](https://github.com/jwoglom)

> **Medtronic Carelink:** The Medtronic code path is preserved from the original fork but has not been tested under this fork. For verified Medtronic support use the [original repository](https://github.com/yo-han/Home-Assistant-Carelink).
