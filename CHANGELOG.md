# Changelog

All notable changes to the Tandem Source / Carelink integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0-rc2] - 2026-02-14

### Fixed
- **Carelink coordinator**: Added historical SG replay and statistics import (Issue #9, PR #8)
  - Process ALL valid SG readings from API polls, not just the latest two
  - Replay intermediate readings so HA's recorder captures full glucose history
  - Import correctly-timestamped long-term statistics for Statistics Graph cards
  - Store reading history in sensor attributes for custom cards (e.g. ApexCharts)

### Housekeeping
- Removed untested Medtronic token tools (carelink-token-generator/, token-tool/, utils/)
- Removed fork template boilerplate (.devcontainer.json, .prettierrc, dependabot.yml, repository.yaml)
- Fixed remaining yo-han repo references → jnctech
- Added Tandem-tested disclaimer to README and info.md

## [0.2.0-rc1] - 2026-02-14

### Added
- **Historical data import**: Import ALL pump events between polls instead of only the latest reading
  - State replay: Intermediate events replayed through coordinator so recorder captures each state change
  - Long-term statistics: CGM, IOB, and basal rate imported via `async_import_statistics()` with correct 5-minute timestamps
  - Entity attributes: Recent readings arrays (24 CGM, 10 bolus, 10 basal) available for custom cards (e.g., ApexCharts)
- Event sequence number tracking to deduplicate events across polls
- Compact attribute keys to stay within Home Assistant's 16KB attribute limit

### Changed
- `_parse_pump_events()` now processes ALL events in the fetch window, not just the latest of each type
- Data coordinator schedules replay and statistics import tasks after each update cycle

### Fixed
- Glucose history graphs no longer show staircase pattern between polls
- Intermediate CGM readings, boluses, and basal changes between syncs are no longer discarded

### Housekeeping
- Removed diagnostic/troubleshooting docs and scripts from repository (archived to dev-notes/)
- Fixed CODEOWNERS: updated from upstream author to @jnctech
- Fixed HACS custom repository URL in README
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

[0.2.0-rc2]: https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink/compare/v0.2.0-rc1...v0.2.0-rc2
[0.2.0-rc1]: https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink/compare/v0.1.4-beta...v0.2.0-rc1
[0.1.4-beta]: https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink/compare/v0.1.3-beta...v0.1.4-beta
[0.1.3-beta]: https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink/compare/v0.1.1-beta...v0.1.3-beta
[0.1.1-beta]: https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink/compare/2024.1.0...v0.1.1-beta
[2024.1.0]: https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink/releases/tag/2024.1.0
