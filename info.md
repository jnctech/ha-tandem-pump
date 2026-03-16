# Tandem t:slim Pump for Home Assistant

> **Medical Disclaimer:** This integration is for **informational and home automation purposes only**.
> It is not a medical device and must not be used to make treatment decisions.
> Always refer to your pump, CGM receiver, or a fingerstick meter before acting on any reading.
> This software is provided as-is with no warranty.

The only Home Assistant integration for the **Tandem t:slim X2** insulin pump.
Connect to your existing **Tandem Source** account and get **69 sensors** covering every
metric your pump reports — glucose, insulin on board, Control-IQ status, battery, alerts, and more.

**No extra hardware. No developer account. Just your Tandem Source login.**

---

## What you get

**Glucose Monitoring (12 sensors)**
Live CGM in mg/dL and mmol/L, rate of change, delta, time in range, GMI, SD, CV, predicted glucose (PLGS)

**Insulin Delivery (14 sensors)**
IOB, current basal rate, last bolus, TDI, daily totals, carb intake, bolus calculator details, estimated remaining insulin

**Pump Battery (4 sensors)**
Battery %, voltage (mV), remaining capacity (mAh), charging status

**Alerts & Alarms (3 sensors)**
Last alert, last alarm, active alert count — with human-readable names for ~65 alert/alarm types

**Pump Status (10 sensors)**
Control-IQ mode, activity mode (Normal / Sleep / Exercise / Eating Soon), cartridge insulin
remaining, CGM sensor type (G6/G7/Libre 2), suspend state + reason, site age, cartridge age, tubing age

**Pump Settings (11 sensors)**
Active basal profile + full hourly schedule, max bolus, CIQ weight/TDI, alert thresholds

**Long-Term Statistics (6)**
CGM, IOB, basal, carbs, correction bolus — works with the Statistics Graph card.
Backfill months of data: **Developer Tools → Actions → carelink.import_history**

**Example Dashboard**
A starter Lovelace dashboard with Mushroom cards, ApexCharts glucose graph, and template sensors.
Copy the YAML from `examples/` and customise to taste.

---

## How it works

```
Tandem t:slim X2  →  Tandem mobile app  →  Tandem Source cloud  →  Home Assistant (polls every 5 min)
```

The Tandem app uploads roughly once per hour when running unrestricted.

> **Keep the Tandem app running unrestricted on your phone.**
> Battery optimisation on Android or Low Power Mode on iOS is the most common cause of stale data.

---

## Requirements

- Tandem t:slim X2 with [Tandem Source](https://source.tandemdiabetes.com) account
- Tandem mobile app (Android or iOS), syncing regularly
- Home Assistant 2023.1.0+ with HACS

---

## Quick install

1. HACS → Custom repositories → add `https://github.com/jnctech/ha-tandem-pump` (category: Integration)
2. Install **Tandem t:slim Pump** → restart HA
3. **Settings → Devices & Services → Add Integration → search "Carelink"**

---

## Upgrading from v1.3.x?

Entity IDs now include a `tandem_` prefix (e.g. `sensor.tandem_last_glucose_level_mmol`).
Update dashboards and automations after upgrading.
Statistics Graph entities (`sensor.carelink_*`) are **not** affected.

---

## Development approach

This project is built with AI assistance (Claude) operating under strict engineering constraints:

- All code passes **SonarCloud** quality analysis — reliability, security, maintainability, coverage, and duplication tracked per-PR
- **Ruff** lint and format checks enforced in CI — no merge without passing
- **Bandit** static security analysis runs on every push
- **pytest** test suite with coverage reporting on every push
- **hassfest** and **HACS** validation ensure Home Assistant compatibility
- Structured AI code review on each PR: logic correctness, silent failure detection, and code simplification

AI is used as a tool. The engineering standards are not negotiable.

Have questions, ideas, or want to contribute? [Open an issue](https://github.com/jnctech/ha-tandem-pump/issues) or
[start a discussion](https://github.com/jnctech/ha-tandem-pump/discussions) — feedback from the community helps shape this project.

---

> **Medtronic CareLink:** This integration also supports legacy Medtronic CareLink (limited sensors).
> Use your CareLink credentials when adding the integration.
