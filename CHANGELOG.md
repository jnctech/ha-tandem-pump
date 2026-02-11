# Changelog

All notable changes to the Tandem Source / Carelink integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.1.3-beta]: https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink/compare/v0.1.1-beta...v0.1.3-beta
[0.1.1-beta]: https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink/compare/2024.1.0...v0.1.1-beta
[2024.1.0]: https://github.com/jnctech/Home-Assistant-Tandem-Source-Carelink/releases/tag/2024.1.0
