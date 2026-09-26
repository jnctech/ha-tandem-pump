# Changelog

All notable changes to the Tandem Source / Carelink integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - develop

## [2.2.1] - 2026-09-09

### Fixed
- **CGM glucose over-read on Dexcom G7 (safety).** When the CGM reports out of range
  (`glucoseValueStatus` High/Low), the Source BFF `currentGlucoseDisplayValue` is not a valid
  display reading — G7 (event 399) sends a large raw estimate (observed 400–1200 mg/dL at
  status=High) while G6 (event 256) sends a ~0 sentinel. The integration surfaced that raw value
  verbatim, so a genuine high could display as 33–66 mmol/L as a live reading (with
  `data_stale` off). Glucose is now clamped to the sensor's reportable bound (High → 400 mg/dL /
  22.2 mmol, Low → 40 mg/dL / 2.2 mmol) at the source, so the latest-glucose sensor **and** all
  derived stats (average / TIR / GMI / SG-delta) use the bounded value; in-range (Normal)
  readings are unchanged. Each clamp is logged, with a warning on a decode-fault signature. (#85)

## [2.2.0] - 2026-09-07

### Added
- **Four new sensors** read from fields already present on existing pump events
  (no extra API calls):
  - **CGM signal strength** (`rssi`) from CGM events (256/399) — diagnostic. Confirmed
    present on G6/GXB (256); may read unavailable on G7 (399) until confirmed live.
  - **Insulin on board — hours** and **minutes** (`iobHours` / `iobMinutes`) from the
    pump status event (9), giving the remaining IOB duration — diagnostic.
  - **Closed loop preferred** (`closedLoopPreferred`) from the PCM event (230), the
    Control-IQ closed-loop preference — diagnostic.
  - Sensor count is now 73.

## [2.1.1] - 2026-09-07

### Added
- **Local brand icon** — bundled `custom_components/tandem/brand/icon.png` so the
  integration provides its own brand assets. Since Home Assistant 2026.3, custom
  integrations serve brand images from a local `brand/` directory (brands proxy API),
  which takes precedence over the `home-assistant/brands` repository. This satisfies the
  HACS validation `brands` check without an external brands-repository PR, unblocking a
  HACS default-store submission. No functional change to the integration.

## [2.1.0] - 2026-09-07

### Added
- **CGM sensor session expiry** — three new sensors from the CGM session events
  (212/213/214): `cgm_session_start`, `cgm_session_expiry` (session start + duration,
  10 days on a G7), and `cgm_sensor_days_remaining`. Answers the "when does my sensor
  expire" request (discussion #67). The wall-clock start is derived from the pump /
  transmitter clock (`pumpDateTime - (currentTransmitterTime - sessionStartTime)`), so it
  needs no epoch assumption. The sensors read unavailable between sessions and until the
  active session's start event uploads (null-not-guess).
- **Pump alert / alarm sensors now populate** — the BFF alert/alarm lifecycle events
  (4/5/6/26/28) are now mapped, so `last_pump_alert`, `last_pump_alarm` and
  `active_pump_alerts` report live values with human-readable names (previously always
  unavailable). Event codes 8 and 27 appear live but are absent from the tconnectsync
  catalog and remain unmapped pending identification.

Sensor count is now 69.

## [2.0.1] - 2026-09-06

Battery-level fix and battery-sensor cleanup on top of the v2.0.0 BFF migration.

### Fixed
- **Pump battery level always "unavailable"** — the level was sourced from events 81
  (DailyBasal) / 53 (ShelfMode), which carry no battery data under the BFF (81 has none;
  53 is absent on current firmware). The level is now read from the pump-status /
  battery-detail events (9 / 34 / 35) via their `abc` (actual battery charge) field,
  validated live against the physical charge ratio. Value is guarded to 0-100.

### Removed
- **Pump battery voltage, remaining (mAh), and charging-status sensors** — these had no
  populated source under the BFF and reported only "unavailable". Removed along with the
  now-unused USB charge-event handling; the pump battery **level** sensor remains. Sensor
  count is now 66.

### Docs
- Fixed the `info.md` "Upgrading from …" section to match the README's v2 clean-install model
  (v2.0.0 is a clean install; it does not migrate the old `carelink` entry or its statistics).

## [2.0.0] - 2026-09-06

First stable release of the Tandem-only v2 rewrite. Restores full sensor data after
Tandem migrated the Source Reports API to new endpoints, which had left the integration
reporting "all sensors unknown".

### Fixed
- **All sensors "unknown" / "Failed to fetch pump metadata"** (#71, #69) — Tandem migrated the
  Source Reports API from the `reportsfacade` paths to new `bff` endpoints (~June 2026); the old
  paths now return 403/404. The client was migrated to the BFF endpoints, including the
  `Origin`/`Referer` headers the BFF's WAF requires. Both EU and US accounts are restored.
- **Pump settings sensors "unknown"** — the BFF renamed the `settings.details` sub-blocks, so the
  ten settings sensors (Control-IQ enabled/weight/TDI, max bolus, basal rate limit, CGM high/low
  alert, high/low BG threshold, low-insulin alert) stopped populating. All remapped to the new schema.
- **Bolus detail and CGM sensor type "unknown"** — mapped the BFF bolus-calculator and daily-status
  events, restoring last-bolus BG / carbs / correction / food-portion and the CGM sensor-type sensor.
- **Multiple-pump accounts showed a retired pump's data** (#65) — the integration now selects the
  most-recently-active pump instead of an arbitrary one.

### Changed
- **Long-term statistics** now pass `mean_type` (`StatisticMeanType.ARITHMETIC`) for forward
  compatibility with the Home Assistant 2026.11 recorder change (#22).

### Known limitations
- Pump battery, alert/alarm history, and USB-charging sensors remain unavailable pending BFF event
  mapping (they report `unavailable` rather than a fabricated value).

## [2.0.0-rc.2] - 2026-07-13

### Fixed
- **Live authentication in Home Assistant** (`invalid_auth` on setup) — the OAuth authorize
  request now follows the redirect that carries the authorization code
  (`follow_redirects=True`). Home Assistant's injected httpx client defaults to
  `follow_redirects=False`, so rc.1 never captured the code and login failed on real setups.
  The `inject-websession` change in rc.1 had dropped the redirect-following the previous
  standalone client did by default. Fix validated end-to-end against a live pump.
- **Config-flow error text** — replaced unresolved `[%key:common::config_flow::…]` references
  in `translations/en.json` with literal strings, so Home Assistant no longer renders the raw
  `[%key:common::config_flow::error::invalid_auth%]` key to the user.

## [2.0.0-rc.1] - 2026-07-11

> ### ⚠️ Breaking change — this is a ground-up rewrite
> The integration has moved to the **`tandem`** domain and is now **Tandem t:slim only**.
> The Medtronic CareLink path and the Nightscout uploader have been **removed**. There is
> **no automatic migration** from the old `carelink`-domain config entry — you must remove the
> old integration and add **Tandem t:slim Pump** fresh. See
> [Upgrading](README.md#upgrading-from-the-old-carelink-domain-releases). This supersedes the
> entire `carelink`-era 1.x line; the major version bump reflects the incompatible domain change.

### Added
- **"Data stale" health binary sensor** (`binary_sensor.tandem_data_stale`) — surfaces sync
  freshness as a first-class, fail-visible health signal instead of silently blanking sensors.
- **Entity golden snapshot tests** (syrupy) paired with invariant assertions, locking the full
  entity surface (140 snapshots) against regression.

### Changed
- **Domain renamed `carelink` → `tandem`**; all entities are now `sensor.tandem_*` /
  `number.tandem_*` / `binary_sensor.tandem_*`.
- **Uses Home Assistant's managed httpx client** instead of constructing its own — aligns with
  HA's connection lifecycle and the Quality Scale `inject-websession` rule.
- **Modern toolchain** — targets Home Assistant 2026.2 on **Python 3.13**; CI, dev container,
  and pre-commit pinned to 3.13.

### Removed
- **Medtronic CareLink** integration path (coordinator, API, config flow, translations).
- **Nightscout uploader** and all associated configuration.

### Internal / Quality (Platinum hardening — in progress)
- **Strict typing** — `mypy --strict` clean across all modules; per-entry state moved to
  `entry.runtime_data`.
- **Test-double fidelity** — statistics tests now patch only the real `async_import_statistics`
  boundary and keep HA's real `StatisticMetaData`/`StatisticData` types (previously faked the
  whole recorder module, masking the TypedDict contract).
- **Supply-chain** — `GITHUB_TOKEN` permissions restricted in CI (OpenSSF Scorecard).
- **376 unit tests + 140 entity snapshots** green on Python 3.13.
- `quality_scale` remains **bronze** for this RC; reconfigure/repair polish is the remaining
  gate before the Platinum flip.

## [1.4.0] - 2026-03-07

> **Breaking change** — entity IDs now use a `tandem_` prefix (e.g. `sensor.last_glucose_level_mmol`
> → `sensor.tandem_last_glucose_level_mmol`). Update dashboards and automations after upgrading.
> Statistics Graph cards using `sensor.carelink_*` statistic IDs are **not** affected.
> Re-run `carelink.import_history` to backfill statistics under the new entity IDs.

### Added
- **4 new live sensors** populated from decoded pump events:
  - `CGM rate of change` (mg/dL/min) — from `EVT_CGM_DATA_GXB` events
  - `CGM status` (Normal / High / Low) — signal quality from `EVT_CGM_DATA_GXB` events
  - `Last cartridge fill amount` (units) — fill volume from `EVT_CARTRIDGE_FILLED`; shows
    Unknown when the API returns 0 (common Tandem API limitation)
  - `Pump suspend reason` (User / Alarm / Malfunction / Auto-PLGS) — from `EVT_PUMPING_SUSPENDED`
    events; shows Unknown when pump is currently active
- **Correction bolus long-term statistic** — `sensor.carelink_correction_bolus` (units) imported
  from `EVT_BOLUS_DELIVERY` events (delivery_status=0, correction_mu>0); automatically included
  in `carelink.import_history` backfill runs
- **Upgrade documentation** — new `## Upgrading` section in README covering HACS update,
  manual update, and clean reinstall paths
- **Duplicate device troubleshooting** — new section in TROUBLESHOOTING.md explaining how to
  delete the phantom v1.2.x device left after the v1.3.0 device-identifier change (correct
  delete path: open the device detail page via the `›` arrow, not the three-dot menu)

### Changed
- **Entity IDs include `tandem_` prefix** — all 50 entities now use `sensor.tandem_*` /
  `number.tandem_*` IDs so sensors are easy to find and filter in Settings → Entities. The
  device name in Settings → Devices is now consistently "Tandem" for all users.

## [1.3.0] - 2026-03-06

### Added
- **Carb and bolus long-term statistics** — two new statistic entities that appear in the
  Statistics Graph card for trend analysis:
  - `sensor.carelink_meal_carbs` (grams) — hourly carb intake from `EVT_CARBS_ENTERED` events
  - `sensor.carelink_total_bolus` (units) — hourly completed bolus delivery from
    `EVT_BOLUS_COMPLETED` / `EVT_BOLEX_COMPLETED` events (completion_status=3 only)
  - Both stat types are automatically included when running `carelink.import_history` for
    historical backfill — no extra steps required

### Changed
- **Stable device identifiers** — all 46 entities (45 sensors + cartridge fill volume number)
  now use the config entry ID as the device identifier instead of the pump serial number;
  this eliminates phantom/split devices when the serial is temporarily unavailable during
  early setup or after an API failure
- **Device info enriched** — device panel in Settings → Devices & Services now shows:
  serial number, firmware version, and a direct link to Tandem Source or Carelink portal

## [1.2.3] - 2026-03-06

### Added
- **`carelink.import_history` service action** — recover missed pump statistics from
  Developer Tools → Actions; specify a date range to backfill CGM glucose, IOB, and
  basal rate long-term statistics; fetches in 7-day chunks; idempotent and safe to re-run

### Changed
- **Sensors always show last-known value** — removed 30-minute staleness timeout;
  sensors no longer go "unavailable" when the app hasn't synced recently; use the
  `Last pump upload` timestamp to see when data was last refreshed
- **Integration display name** updated to "Tandem t:slim Pump" in Settings → Devices & Services
  (was showing the internal domain name "carelink")
- **Poll log moved to DEBUG** — routine "no new data" message was firing 288×/day at INFO
  level; now only appears when debug logging is explicitly enabled

## [1.2.2] - 2026-03-02

### Fixed
- **Sensors showing "unknown" when pump not syncing recently**: When no pump events were returned for the current date range, four sensor keys (`last_carbs_timestamp`, `last_cartridge_change`, `last_site_change`, `last_tubing_change`) were missing entirely from the coordinator data dict, causing sensors to show "unknown" instead of "unavailable" (#17)
  - `_parse_therapy_timeline()` now always initialises these four keys to `UNAVAILABLE` before processing
- **No sensor data after extended sync gap**: When the current date range contains no pump events (e.g. pump hasn't synced in several days), the integration now fetches events from the last-known date range (`maxDateWithEvents`) as a fallback, restoring display of last-known pump state instead of all sensors going blank (#17)
- **Base64 decode exception too broad**: Tightened exception handling in `decode_pump_events()` to catch only `ValueError` and `binascii.Error` instead of bare `Exception`
- **Bearer None on 401 re-login**: Added guard to raise `TandemAuthError` if re-login succeeds but no token is obtained, preventing a second API call with `Authorization: Bearer None`

### Changed
- Internal code simplification and cleanup across all integration files (no behaviour changes)

## [1.2.1] - 2026-02-14

### Added
- **Cartridge fill volume input**: New number entity (`number.carelink_cartridge_fill_volume`) allows users to manually set cartridge fill volume when changing cartridges, since the Tandem API does not report this value (#14)

### Fixed
- **Glucose timestamp showing future time**: Fixed two independent timezone bugs (#13)
  - `parse_dotnet_date()` now returns UTC-aware datetimes; therapy timeline timestamps use `.astimezone()` for correct UTC-to-local conversion
  - Binary event decoder timestamps are **local pump time**, not UTC — decoder now creates naive datetimes, callers use `.replace(tzinfo=tz)` to label them correctly (previously stamped UTC onto local values, shifting data by the UTC offset)
- **Cartridge insulin showing 0**: Sensor now shows "Unknown" instead of misleading "0" when the Tandem API returns 0.0 for insulin volume (#14)
- **Software version not populated**: Added fallback to `partNumber` metadata field and debug logging when `softwareVersion` is missing from the API response (#15)
- **Last carb entry high y-axis**: Removed `state_class=MEASUREMENT` from the "Last carb entry" sensor to prevent HA from tracking it as long-term statistics, which caused misleading y-axis scaling on graphs (#16)

### Changed
- Added `Platform.NUMBER` to integration platforms for the cartridge fill volume entity

## [1.2.0] - 2026-02-14

### Added
- **Expanded data sources**: Decode 10 new pump event types (15 total, up from 5)
  - Pump suspend/resume state, activity mode (Sleep/Exercise/Eating Soon), Control-IQ mode (Open/Closed Loop)
  - Cartridge, cannula (site), and tubing change timestamps for infusion set tracking
  - Carb entries, manual BG readings, extended bolus completion, cartridge insulin level
- **Computed CGM summary**: Average glucose, Time in Range (70-180), time below/above range, SD, CV, GMI, CGM usage %
  - Fixes the 3 sensors (avg glucose, TIR, CGM usage) that were permanently unavailable due to dashboard_summary API returning 404
  - All stats computed locally from CGM pump events
- **Computed insulin summary**: Total Daily Insulin (TDI), daily bolus/basal totals, basal/bolus split %, daily carbs, daily bolus count
- **Pump settings extraction**: 11 new sensors from pump metadata upload settings
  - Active basal profile name (with full schedule as attributes: rates, ISF, carb ratio, target BG per segment)
  - Control-IQ settings: enabled status, configured weight, configured TDI
  - Pump limits: max bolus, basal rate limit
  - CGM alert thresholds: high/low glucose alerts
  - BG alert thresholds: low/high BG alerts, low insulin alert
- 27 new sensors total (45 Tandem sensors, up from 18)
- 48 new unit tests (236 total, up from 188)

### Changed
- API now requests 15 event types instead of 5 (adds events 11, 12, 16, 21, 33, 48, 61, 63, 229, 230)
- Dashboard summary API call only used as fallback when pump events are unavailable
- Daily insulin/carb summaries now filter events to "today" in pump timezone (previously summed full 2-day fetch window)

### Fixed
- **CRITICAL**: Fixed `lastUpload` parsing bug — field is a dict `{uploadId, lastUploadedAt, settings}`, not a timestamp string
  - `sensor.last_pump_upload` and `sensor.last_update` now show real timestamps (were stuck on "unknown")
- **CRITICAL**: Fixed timestamp timezone handling — API returns UTC timestamps, not local time
  - `.replace(tzinfo=tz)` was stamping local timezone onto UTC clock values, shifting all data by the UTC offset (e.g. 10.5 hours for Adelaide)
  - Decoder now uses `fromtimestamp(tz=timezone.utc)`, coordinator uses `.astimezone(tz)` for all conversions
- **CRITICAL**: Fixed CARBS_ENTERED binary decoder — payload is float32, not uint16
  - Was reading IEEE 754 float bytes as raw integer (e.g. 16,800 instead of 20g)
  - Verified correct format via live API binary decode in browser
- Fixed statistics import "Invalid timestamp" error — HA requires timestamps at top of hour (minute=0)
  - Statistics now importing successfully (CGM, IOB, basal)
- Fixed site change sensor — CANNULA_FILLED (event 61) never returned by API
  - Now derives from CARTRIDGE_FILLED (event 33) as fallback
- Fixed manifest.json key ordering for hassfest validation (alphabetical after domain/name)

## [1.1.0] - 2026-02-14

### Added
- **Stale data detection** (#11): Sensors now report `unavailable` when pump data is older than 30 minutes
  - Prevents misleading flat lines in glucose history graphs when the pump hasn't uploaded recent data
  - Timestamp and diagnostic sensors (last glucose update, last upload, serial, model, etc.) remain available so users can see when data was last received
  - Pattern adapted from upstream yo-han/Home-Assistant-Carelink staleness system

### Changed
- **API optimisation**: Coordinator now checks `maxDateWithEvents` from lightweight metadata endpoint before fetching full pump events
  - If no new data since last poll, skips the expensive `pumpevents` API call entirely
  - Reduces unnecessary API traffic and auth token usage when pump hasn't uploaded
- Added `helpers.py` with `is_data_stale()` utility function
- Sensor entity now tracks `platform_type` to apply staleness checks only to Tandem sensors (Carelink behaviour unchanged)

## [1.0.0] - 2026-02-14

### Added
- **Historical data import**: Import ALL pump events between polls instead of only the latest reading
  - Long-term statistics: CGM, IOB, and basal rate imported via `async_import_statistics()` with correct timestamps
  - Entity attributes: Recent readings arrays (24 CGM, 10 bolus, 10 basal) available for custom cards (e.g., ApexCharts)
- **Carelink coordinator**: Process ALL valid SG readings from API polls, not just the latest two
  - Import correctly-timestamped long-term statistics for Statistics Graph cards
  - Store reading history in sensor attributes for custom cards
- Event sequence number tracking to deduplicate events across polls
- Compact attribute keys to stay within Home Assistant's 16KB attribute limit
- Added `recorder` to manifest `after_dependencies` (ensures recorder loads first for `async_import_statistics`)

### Changed
- `_parse_pump_events()` now processes ALL events in the fetch window, not just the latest of each type

### Fixed
- **CRITICAL**: Fixed glucose graph spikes caused by historical replay mechanism (#9)
  - `async_set_updated_data()` replaced entire coordinator data dict during replay, causing sensors to oscillate between real values and `None` when dashboard keys were missing
  - Removed replay infrastructure entirely; historical data now handled solely via long-term statistics import
- Fixed `sensor.py` `setdefault` → `.get()` to prevent mutation of coordinator.data during sensor reads
- Glucose history graphs no longer show staircase pattern between polls
- Intermediate CGM readings, boluses, and basal changes between syncs are no longer discarded

### Housekeeping
- Removed untested Medtronic token tools (carelink-token-generator/, token-tool/, utils/)
- Removed fork template boilerplate (.devcontainer.json, .prettierrc, dependabot.yml, repository.yaml)
- Removed diagnostic/troubleshooting docs and scripts from repository
- Fixed remaining yo-han repo references → jnctech
- Fixed CODEOWNERS: updated from upstream author to @jnctech
- Fixed HACS custom repository URL in README
- Added Tandem-tested disclaimer to README and info.md
- Updated info.md to reflect Tandem Source scope and proper attribution

## [0.1.4-beta] - 2026-02-13

### Fixed
- **Sensor update timing**: Improved data fetch performance and reliability
  - Parallelised independent API calls (metadata + pumper_info concurrent, ControlIQ fallback concurrent)
  - Added retry with exponential backoff (2s, 4s) for transient network errors (connection reset, timeout, DNS)
  - Wrapped errors with Home Assistant `UpdateFailed` for proper coordinator backoff and entity unavailable marking
  - Fixed timezone mismatch: API date range now uses pump timezone instead of server local time
  - Demoted per-cycle INFO logs to DEBUG to reduce log noise (~288 lines/day at 5-min intervals)
- **CRITICAL**: Fixed sensor population - all Tandem pump sensors stuck in "Unknown" state (#3)
  - ControlIQ API endpoints (`tdcservices.eu.tandemdiabetes.com`) return 404 errors
  - Switched to Source Reports pumpevents API as primary data source (same endpoint the Tandem Source web UI uses)
  - Implemented binary event decoder for Tandem's proprietary 26-byte record format (base64-encoded)
  - Sensors now populate: glucose (mg/dL & mmol/L), active insulin (IOB), basal rate, last bolus, meal bolus, Control-IQ status

### Added
- `decode_pump_events()` binary decoder for Tandem pump event records
  - Supports CGM readings (event 256), bolus completed (event 20), bolus delivery (event 280), basal rate change (event 3), basal delivery (event 279)
  - Tandem epoch (2008-01-01) timestamp conversion
- `get_pump_events()` method targeting Source Reports API (`/api/reports/reportsfacade/pumpevents/`)
- `_parse_pump_events()` coordinator method to extract sensor values from decoded binary events

### Changed
- `get_recent_data()` now uses pump_events as primary data source, falling back to ControlIQ endpoints only when unavailable
- `get_recent_data()` accepts `pump_timezone` parameter for timezone-aware date ranges
- `_api_get()` retries transient network errors up to 2 times with exponential backoff
- Data coordinator prioritises pump_events over therapy_timeline for sensor value extraction
- Data coordinator raises `UpdateFailed` on errors instead of returning empty dict

### Technical Notes
- Binary format reference: [tconnectsync](https://github.com/jwoglom/tconnectsync) event parser
- Each record: 2-byte header (4-bit source + 12-bit event ID), 4-byte timestamp, 4-byte sequence, 16-byte payload
- Dashboard-dependent sensors (average glucose, CGM usage, time in range) still require ControlIQ endpoints

## [0.1.3-beta] - 2026-02-11

### Fixed
- **CRITICAL**: Fixed blocking SSL call in TandemSourceClient that prevented integration from loading
  - Moved SSL context creation to executor using `asyncio.run_in_executor()`
  - Resolves "Detected blocking call to load_verify_locations" error
  - Integration now loads successfully in Home Assistant 2024.1+

### Added
- Comprehensive test suite with 143 new tests using pytest-homeassistant-custom-component
  - 31 tests for TandemSourceClient (PKCE flow, authentication, data parsing)
  - 11 tests for Tandem config flow (setup, validation, error handling)
  - 19 tests for data coordinator (sensor data parsing, dashboard integration)
- Added `certifi>=2023.0.0` to requirements for explicit SSL certificate management
- Improved logging for ControlIQ API availability (Source OIDC tokens may not work with ControlIQ endpoints)

### Changed
- Updated repository references from yo-han to jnctech organization
- Updated codeowner to @jnctech
- Migrated test infrastructure from sys.modules mocking to real HA runtime fixtures
- Updated pytest configuration with pytest-homeassistant-custom-component==0.13.80

### Technical Notes
- The v0.1.0.beta branch attempted to fix the SSL issue using `create_async_httpx_client` from Home Assistant, but this approach broke the integration with "Invalid handler specified" errors
- The proper fix uses the standard httpx.AsyncClient with SSL context creation offloaded to an executor

## [0.1.1-beta] - 2024-XX-XX

### Added
- Initial Tandem t:slim pump integration support
- Support for EU and US Tandem Source regions
- README documentation for Tandem setup and configuration

## [2024.1.0] - 2024-XX-XX

### Added
- Initial Medtronic Carelink integration
- Support for MiniMed 770G/780G pumps
- Support for Guardian Connect CGM
- Nightscout upload capability

[2.0.0-rc.1]: https://github.com/jnctech/ha-tandem-pump/compare/v1.6.0...v2.0.0-rc.1
[1.2.3]: https://github.com/jnctech/ha-tandem-pump/compare/v1.2.2...v1.2.3
[1.2.2]: https://github.com/jnctech/ha-tandem-pump/compare/v1.2.1...v1.2.2
[1.2.1]: https://github.com/jnctech/ha-tandem-pump/compare/v1.2.0...v1.2.1
[1.2.0]: https://github.com/jnctech/ha-tandem-pump/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/jnctech/ha-tandem-pump/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/jnctech/ha-tandem-pump/compare/v0.1.4-beta...v1.0.0
[0.1.4-beta]: https://github.com/jnctech/ha-tandem-pump/compare/v0.1.3-beta...v0.1.4-beta
[0.1.3-beta]: https://github.com/jnctech/ha-tandem-pump/compare/v0.1.1-beta...v0.1.3-beta
[0.1.1-beta]: https://github.com/jnctech/ha-tandem-pump/compare/2024.1.0...v0.1.1-beta
[2024.1.0]: https://github.com/jnctech/ha-tandem-pump/releases/tag/2024.1.0
