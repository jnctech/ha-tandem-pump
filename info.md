# Tandem t:slim Pump for Home Assistant

> **Medical Disclaimer:** This integration is for **informational and home automation purposes only**.
> It is not a medical device and must not be used to make treatment decisions.
> Always refer to your pump, CGM receiver, or a fingerstick meter before acting on any reading.
> This software is provided as-is with no warranty.

The only Home Assistant integration for the **Tandem t:slim X2** insulin pump.
Connect to your existing **Tandem Source** account and get **73 sensors** covering every
metric your pump reports — glucose, insulin on board, Control-IQ status, battery, alerts, and more.

**No extra hardware. No developer account. Just your Tandem Source login.**

---

## What you get

**Glucose Monitoring (12 sensors)**
Live CGM in mg/dL and mmol/L, rate of change, delta, time in range, GMI, SD, CV, predicted glucose (PLGS)

**Insulin Delivery (14 sensors)**
IOB, current basal rate, last bolus, TDI, daily totals, carb intake, bolus calculator details, estimated remaining insulin

**Pump Battery (1 sensor)**
Battery level (%)

**Alerts & Alarms (3 sensors)**
Last alert, last alarm, active alert count — with human-readable names for ~65 alert/alarm types

**Pump Status (10 sensors)**
Control-IQ mode, activity mode (Normal / Sleep / Exercise / Eating Soon), cartridge insulin
remaining, CGM sensor type (G6/G7/Libre 2), suspend state + reason, site age, cartridge age, tubing age

**Pump Settings (11 sensors)**
Active basal profile + full hourly schedule, max bolus, CIQ weight/TDI, alert thresholds

**Device & Timestamps (7 sensors)**
Serial, firmware, last sync, last glucose update, CGM usage

**Long-Term Statistics (6)**
CGM, IOB, basal, carbs, correction bolus — works with the Statistics Graph card.
Backfill months of data: **Developer Tools → Actions → tandem.import_history**

**Example Dashboard**
A quick-start dashboard is included in `examples/` — early mock-up, future releases will
include more templates and dashboarding guidance.

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
3. **Settings → Devices & Services → Add Integration → search "Tandem t:slim"**

---

## Upgrading from a pre-2.0 (`carelink`) release?

**v2.0.0 is a clean install, not an in-place upgrade.** The integration moved to
the `tandem` domain and dropped the Medtronic CareLink path, so it does **not**
migrate the old `carelink` config entry or its statistics history.

1. Note your Tandem Source credentials (email, region, scan interval).
2. Remove the old integration and delete the stale `config/custom_components/carelink/` folder.
3. Install v2.0.0 and add **Tandem t:slim Pump** fresh.

Entities are `sensor.tandem_*` — update any dashboards/automations that referenced the old ids.
See the [README](https://github.com/jnctech/ha-tandem-pump#upgrading-from-the-old-carelink-domain-releases) for full details.

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

AI is used as a tool. The engineering standards are not negotiable.

Have questions, ideas, or want to contribute? [Open an issue](https://github.com/jnctech/ha-tandem-pump/issues) or
[start a discussion](https://github.com/jnctech/ha-tandem-pump/discussions) — feedback from the community helps shape this project.
