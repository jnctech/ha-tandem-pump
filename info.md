# Tandem t:slim Pump for Home Assistant

The most comprehensive Tandem insulin pump integration for Home Assistant. Monitor your **Tandem t:slim X2** pump with **45+ sensors**, long-term statistics, glucose history, insulin delivery tracking, and full pump settings visibility.

## What You Get

**Glucose Monitoring** — Live CGM readings (mg/dL + mmol/L), glucose delta, daily average, Time in Range, time below/above range, standard deviation, CV, and GMI. All computed locally from your pump's CGM events.

**Insulin Delivery** — Active insulin (IOB), current basal rate, last bolus details, daily totals (TDI, bolus, basal, split %), daily carbs, and bolus count.

**Pump Status** — Control-IQ mode (Open/Closed Loop), activity mode (Normal/Sleep/Exercise), pump suspended state, cartridge level, and infusion set change timestamps (cartridge, site, tubing).

**Pump Settings** — Active basal profile with full schedule (rates, ISF, carb ratio, target BG per time segment), Control-IQ configuration, max bolus/basal limits, CGM and BG alert thresholds.

**Long-Term Statistics** — CGM glucose, IOB, and basal rate imported into HA's statistics engine. Use native Statistics Graph cards for daily/weekly/monthly trends.

**Smart Polling** — Checks for new data before fetching, skips expensive API calls when nothing has changed. Sensors always show the **last known value** — no confusing "unavailable" gaps just because the phone was out of range briefly.

**Manual Backfill** — The `carelink.import_history` action (Developer Tools → Actions) lets you recover statistics for any period when the Tandem app wasn't syncing — even weeks or months of missed data.

## How Sync Works

This integration reads from the **Tandem Source cloud** — it cannot talk to your pump directly. The Tandem t:slim mobile app must be running and connected to your pump via Bluetooth for uploads to occur.

When unrestricted, the app uploads pump data to Tandem Source approximately **every 60 minutes**. HA then picks up the new data within minutes of each upload.

> **Android users:** Set the Tandem app to **Unrestricted** battery usage (Settings → Apps → Tandem t:slim → Battery). The default "Optimised" setting pauses background sync.
>
> **iOS users:** Enable **Background App Refresh** for the Tandem app (Settings → General → Background App Refresh) and avoid Low Power Mode during monitoring periods.

If the app wasn't syncing for a period, use `carelink.import_history` to backfill the missing statistics.

## Requirements

- Tandem t:slim X2 pump syncing to Tandem Source via the Tandem t:slim mobile app
- Tandem Source account credentials (email + password)
- Home Assistant 2023.1.0+

## Installation

1. Add this repository as a custom repository in HACS
2. Download the integration
3. Restart Home Assistant
4. Add the integration via Settings > Devices & Services
5. Select "Tandem t:slim" and enter your credentials

A starter dashboard with ApexCharts glucose and insulin graphs is included at `examples/dashboard.yaml`.

## Credits

- Tandem Source integration by [@jnctech](https://github.com/jnctech)
- Forked from [@yo-han's Carelink integration](https://github.com/yo-han/Home-Assistant-Carelink)
- Binary event format reference from [tconnectsync](https://github.com/jwoglom/tconnectsync) by [@jwoglom](https://github.com/jwoglom)

> **Note:** Medtronic Carelink support is inherited from the original integration but has not been tested under this fork. For verified Medtronic support, use the [original repo](https://github.com/yo-han/Home-Assistant-Carelink).
