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
- **Stale data detection** — sensors go `unavailable` when your pump hasn't synced, preventing misleading flat lines
- **Smart polling** — skips expensive API calls when no new data exists, reducing token usage
- **Computed summaries** — TIR, average glucose, GMI, daily insulin totals all computed locally from your pump events
- **Full pump settings** — see your active profile, basal schedule, Control-IQ config, alert thresholds

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
Three metrics are imported into HA's statistics engine every poll cycle:
- **CGM glucose** — for native Statistics Graph cards
- **Insulin on board (IOB)** — track IOB trends over days/weeks
- **Basal rate** — monitor basal delivery patterns

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
- The **Tandem t:slim mobile app** connected to your pump (this is how data reaches Tandem Source)
- Home Assistant **2023.1.0** or later

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
1. Checks lightweight metadata to see if new data exists (skip if unchanged)
2. Fetches binary pump events (15 event types) when new data is available
3. Decodes events, computes summaries, extracts settings
4. Imports long-term statistics for HA's native graph cards
5. Marks sensors as `unavailable` if data is older than 30 minutes

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
