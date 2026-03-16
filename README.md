# Tandem t:slim Pump for Home Assistant

> **Medical Disclaimer:** This integration is for **informational and home automation purposes only**.
> It is not a medical device and must not be used to make treatment decisions.
> Always refer to your pump, CGM receiver, or a fingerstick blood glucose meter before acting
> on any glucose reading or insulin value. For reliable real-time glucose monitoring, use your
> Dexcom/Libre receiver or compatible CGM app — this integration relies on cloud uploads which
> can be delayed by minutes to hours. If in doubt, use a fingerstick meter.
> This software is provided as-is with no warranty. See [LICENSE](LICENSE).

The only Home Assistant integration for the **Tandem t:slim X2** insulin pump.
Get CGM readings, insulin on board, Control-IQ status, and 69 sensors —
using your existing Tandem Source account. No extra hardware required.

[![release](https://img.shields.io/github/v/release/jnctech/ha-tandem-pump)](https://github.com/jnctech/ha-tandem-pump/releases)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![build](https://img.shields.io/github/actions/workflow/status/jnctech/ha-tandem-pump/ci.yml?branch=develop&label=build)](https://github.com/jnctech/ha-tandem-pump/actions/workflows/ci.yml)
[![Reliability](https://sonarcloud.io/api/project_badges/measure?project=jnctech_ha-tandem-pump&metric=reliability_rating)](https://sonarcloud.io/summary/new_code?id=jnctech_ha-tandem-pump)
[![Security](https://sonarcloud.io/api/project_badges/measure?project=jnctech_ha-tandem-pump&metric=security_rating)](https://sonarcloud.io/summary/new_code?id=jnctech_ha-tandem-pump)
[![Maintainability](https://sonarcloud.io/api/project_badges/measure?project=jnctech_ha-tandem-pump&metric=sqale_rating)](https://sonarcloud.io/summary/new_code?id=jnctech_ha-tandem-pump)
[![Coverage](https://sonarcloud.io/api/project_badges/measure?project=jnctech_ha-tandem-pump&metric=coverage)](https://sonarcloud.io/summary/new_code?id=jnctech_ha-tandem-pump)
[![Duplicated Lines](https://sonarcloud.io/api/project_badges/measure?project=jnctech_ha-tandem-pump&metric=duplicated_lines_density)](https://sonarcloud.io/summary/new_code?id=jnctech_ha-tandem-pump)
[![License](https://img.shields.io/github/license/jnctech/ha-tandem-pump)](LICENSE)

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=jnctech&repository=ha-tandem-pump&category=integration)

---

## What you can do

- Display your current glucose reading and trend arrow on any Home Assistant dashboard
- Automate alerts: notify when cartridge insulin drops below 20 u, page family when the pump is suspended
- Track time-in-range, GMI, and long-term insulin trends over weeks with the Statistics Graph card
- Know your active basal profile, Control-IQ mode, and IOB — everything your pump reports, visible in your smart home

## 69 sensors across 7 categories

| Category | Sensors | Highlights |
|---|---|---|
| Glucose Monitoring | 12 | CGM mg/dL + mmol/L, rate of change, TIR, GMI, SD, CV, predicted glucose (PLGS) |
| Insulin Delivery | 14 | IOB, basal rate, last bolus, TDI, daily totals, carbs, bolus calculator details, estimated remaining insulin |
| Pump Battery | 4 | Battery %, voltage (mV), remaining capacity (mAh), charging status |
| Alerts & Alarms | 3 | Last alert, last alarm, active alert count |
| Pump Status | 10 | Control-IQ mode, activity mode, cartridge insulin, CGM sensor type, suspend reason, site/cartridge/tubing age |
| Pump Settings | 11 | Active profile + hourly schedule, max bolus, CIQ limits, alert thresholds |
| Device & Timestamps | 7 | Serial, firmware, last sync, last glucose update |

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
| Predicted glucose | Control-IQ PLGS predicted value (mg/dL; shows when PLGS activates) |

### Insulin Delivery (14)
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
| Last bolus BG | BG at time of bolus request (+ calculator details as attributes) |
| Last bolus carbs entered | Carbs entered into bolus calculator |
| Last bolus correction | Correction portion (units) |
| Last bolus food portion | Food portion (units) |
| Estimated insulin remaining | Fill volume minus cumulative deliveries (units) |

### Pump Battery (4)
| Sensor | Description |
|---|---|
| Battery percentage | Current battery level (%) |
| Battery voltage | Battery voltage (mV) |
| Battery remaining | Remaining capacity (mAh) |
| Charging status | Charging / Not charging |

### Alerts & Alarms (3)
| Sensor | Description |
|---|---|
| Last pump alert | Most recent alert (human-readable name) |
| Last pump alarm | Most recent alarm (human-readable name) |
| Active pump alerts | Count of uncleared alerts + alarms |

### Pump Status (10)
| Sensor | Description |
|---|---|
| Control-IQ status | Open Loop / Closed Loop |
| Activity mode | Normal / Sleep / Exercise / Eating Soon |
| Pump suspended | Suspended / Active |
| Pump suspend reason | User / Alarm / Malfunction / Auto-PLGS |
| Cartridge insulin | Remaining insulin (units) |
| Last cartridge fill amount | Fill volume from API (units) |
| Last cartridge change | Timestamp of last cartridge fill |
| Last site change | Timestamp (derived from cartridge fill) |
| Last tubing change | Timestamp of last tubing prime |
| CGM sensor type | G6 / G7 / Libre 2 / None |

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

**Plus 6 long-term statistics** (CGM, IOB, basal, carbs, total bolus, correction bolus) compatible with
HA's Statistics Graph card. Import months of history with `carelink.import_history`.

---

## Requirements

- Tandem t:slim X2 with an active [Tandem Source](https://source.tandemdiabetes.com) account
- Tandem mobile app installed on Android or iOS and syncing regularly
- Home Assistant 2023.1.0+ with HACS installed

---

## Install

### Via HACS (recommended)

1. HACS → Integrations → ⋮ → **Custom repositories** →
   add `https://github.com/jnctech/ha-tandem-pump` (category: Integration)
2. Find **Tandem t:slim Pump** → **Download** → restart Home Assistant
3. **Settings → Devices & Services → Add Integration** → search **Carelink** →
   enter your Tandem Source email, password, and region

That's it. No developer account. Your pump's data starts flowing within minutes.

Or click the **Add to HACS** button at the top of this page.

### Manual

Download the [latest release](https://github.com/jnctech/ha-tandem-pump/releases/latest).
**Delete** the existing `config/custom_components/carelink/` folder first (removes stale files
from previous versions), then copy the new `custom_components/carelink/` into place.
Restart Home Assistant and add the integration as above.

---

## How it works

```
Tandem t:slim X2  →  Tandem mobile app  →  Tandem Source cloud  →  Home Assistant (polls every 5 min)
```

The Tandem app uploads roughly once per hour when running unrestricted.
New data appears in Home Assistant within minutes of each upload.

> **Keep the Tandem app running unrestricted on your phone.**
> Battery optimisation on Android or Low Power Mode on iOS will delay or stop uploads.
> This is the most common cause of stale readings.
> [Fix it now →](TROUBLESHOOTING.md#mobile-app-settings)

---

## Backfill historical data

Import months of CGM, insulin, carb, and correction bolus history into the Statistics Graph:

**Developer Tools → Actions → `carelink.import_history`** → set a start and end date → Call Action

| Field | Required | Description |
|---|---|---|
| `start_date` | Yes | First date to import (date picker or YYYY-MM-DD) |
| `end_date` | No | Last date to import — defaults to today |

Data is fetched in 7-day chunks. The action is idempotent — safe to run multiple times.

| Scenario | Suggested range |
|---|---|
| App backgrounded for a day | yesterday → today |
| App not syncing for a week | 7 days ago → today |
| First install — full history | earliest date → today (run in monthly chunks) |

---

## Example dashboard

A quick-start dashboard is included in [`examples/`](examples/) to get you up and running.
This is an early mock-up — future releases will include more templates and dashboarding guidance.

**Requires** (install via HACS → Frontend):
- [Mushroom](https://github.com/piitaya/lovelace-mushroom) — card layout
- [ApexCharts Card](https://github.com/RomRider/apexcharts-card) — glucose graph
- [card-mod](https://github.com/thomasloven/lovelace-card-mod) — colour-coded glucose hero card

See [`examples/simple-dashboard.yaml`](examples/simple-dashboard.yaml) and
[`examples/template_sensors.yaml`](examples/template_sensors.yaml) for details.

## Upgrading

<details>
<summary>From v1.3.x</summary>

Entity IDs now include a `tandem_` prefix.

| Before | After |
|---|---|
| `sensor.last_glucose_level_mmol` | `sensor.tandem_last_glucose_level_mmol` |

Update dashboards and automations after upgrading.
Statistics Graph entities (`sensor.carelink_*`) are **not** affected.

</details>

<details>
<summary>From v1.2.x or earlier</summary>

You may see a phantom **Tandem Pump** device with 0 entities — safe to delete.
See [Duplicate Device →](TROUBLESHOOTING.md#duplicate-device-after-upgrade)

If entities do not appear after upgrading, do a clean reinstall:
1. Note your credentials (email, region, scan interval)
2. Settings → Devices & Services → Carelink → Delete
3. Update the integration and restart HA
4. Re-add and enter your credentials

</details>

---

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for the full guide.

| Symptom | Most likely cause | Fix |
|---|---|---|
| Sensors show Unknown / data is stale | Tandem app battery-optimised | [Mobile App Settings →](TROUBLESHOOTING.md#mobile-app-settings) |
| Authentication failure | Wrong region, or MFA enabled | [Configuration Issues →](TROUBLESHOOTING.md#configuration-issues) |
| Sensors missing | Wrong platform selected at setup | [Missing Sensors →](TROUBLESHOOTING.md#missing-sensors) |

Open an issue: https://github.com/jnctech/ha-tandem-pump/issues

---

## Development approach

This project is built with AI assistance (Claude) operating under strict engineering constraints:

- All code passes **SonarCloud** quality analysis — reliability, security, maintainability, coverage, and duplication tracked per-PR
- **Ruff** lint and format checks enforced in CI — no merge without passing
- **Bandit** static security analysis runs on every push
- **pytest** test suite with coverage reporting on every push
- **hassfest** and **HACS** validation ensure Home Assistant compatibility
- **OpenSSF Scorecard** supply chain security assessment
- Structured AI code review on each PR: logic correctness, silent failure detection, and code simplification
- Git Flow branching with conventional commits

AI is used as a tool. The engineering standards are not negotiable.

Have questions, ideas, or want to contribute? [Open an issue](https://github.com/jnctech/ha-tandem-pump/issues) or
[start a discussion](https://github.com/jnctech/ha-tandem-pump/discussions) — feedback from the community helps shape this project.

---

## Credits

Built and maintained by [@jnctech](https://github.com/jnctech).
Original Carelink integration by [@yo-han](https://github.com/yo-han/Home-Assistant-Carelink).
Tandem API research: [jwoglom/tconnectsync](https://github.com/jwoglom/tconnectsync) by [@jwoglom](https://github.com/jwoglom).

---

> **Medtronic CareLink users:** This integration also supports Medtronic CareLink (limited sensors).
> Use your CareLink credentials when adding the integration.
