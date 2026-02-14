# Tandem t:slim Pump for Home Assistant

The most comprehensive Tandem insulin pump integration for Home Assistant. Monitor your **Tandem t:slim X2** pump with **45+ sensors**, long-term statistics, glucose history, insulin delivery tracking, and full pump settings visibility.

## What You Get

**Glucose Monitoring** — Live CGM readings (mg/dL + mmol/L), glucose delta, daily average, Time in Range, time below/above range, standard deviation, CV, and GMI. All computed locally from your pump's CGM events.

**Insulin Delivery** — Active insulin (IOB), current basal rate, last bolus details, daily totals (TDI, bolus, basal, split %), daily carbs, and bolus count.

**Pump Status** — Control-IQ mode (Open/Closed Loop), activity mode (Normal/Sleep/Exercise), pump suspended state, cartridge level, and infusion set change timestamps (cartridge, site, tubing).

**Pump Settings** — Active basal profile with full schedule (rates, ISF, carb ratio, target BG per time segment), Control-IQ configuration, max bolus/basal limits, CGM and BG alert thresholds.

**Long-Term Statistics** — CGM glucose, IOB, and basal rate imported into HA's statistics engine. Use native Statistics Graph cards for daily/weekly/monthly trends.

**Smart Polling** — Checks for new data before fetching, skips expensive API calls when nothing has changed. Stale data detection marks sensors `unavailable` after 30 minutes to prevent misleading flat lines.

## Requirements

- Tandem t:slim X2 pump syncing to Tandem Source via the t:connect app
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
