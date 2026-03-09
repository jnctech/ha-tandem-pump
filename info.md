# Tandem t:slim Pump for Home Assistant

The only Home Assistant integration for the **Tandem t:slim X2** insulin pump.
Connect to your existing **Tandem Source** account and get **49+ sensors** covering every
metric your pump reports — glucose, insulin on board, Control-IQ status, and more.

**No extra hardware. No developer account. Just your Tandem Source login.**

---

## What you get

**Glucose Monitoring (12 sensors)**
Live CGM in mg/dL and mmol/L, rate of change, delta, time in range, GMI, SD, CV

**Insulin Delivery (10 sensors)**
IOB, current basal rate, last bolus, TDI, daily totals, carb intake, bolus count

**Pump Status (9 sensors)**
Control-IQ mode, activity mode (Normal / Sleep / Exercise / Eating Soon), cartridge insulin
remaining, suspend state + reason, site age, cartridge age, tubing age

**Pump Settings (11 sensors)**
Active basal profile + full hourly schedule, max bolus, CIQ weight/TDI, alert thresholds

**Long-Term Statistics (6)**
CGM, IOB, basal, carbs, correction bolus — works with the Statistics Graph card.
Backfill months of data: **Developer Tools → Actions → carelink.import_history**

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

> **Medtronic CareLink:** This integration also supports legacy Medtronic CareLink (limited sensors).
> Use your CareLink credentials when adding the integration.
