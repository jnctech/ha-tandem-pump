# ADR-003: Polling Interval and Data Freshness

**Date:** 2026-03-13
**Status:** Accepted

## Context

The integration polls the Tandem Source cloud API on a fixed interval via HA's `DataUpdateCoordinator`. The data freshness chain is:

```
Pump → Bluetooth → Tandem mobile app → Tandem Source cloud → HA polling → Sensors
```

Each hop introduces latency. The integration controls only the last hop (HA poll interval).

## Decision

**5-minute polling interval** (300 seconds), matching the upstream default.

The coordinator uses `update_interval=timedelta(minutes=5)` in `__init__.py`.

## Alternatives Considered

**Shorter interval (e.g., 1 minute)**
Rejected. The Tandem Source cloud only receives data when the pump syncs to the mobile app, which itself happens approximately every 5 minutes via Bluetooth. Polling more frequently would return the same stale data while increasing API call volume and risk of rate limiting.

**Longer interval (e.g., 15 minutes)**
Rejected. Would degrade dashboard responsiveness — glucose readings would be 15-20 minutes old by the time HA shows them, reducing clinical utility for monitoring.

**Webhook/push model**
Not available. The Tandem Source API is a polling API with no webhook or push notification capability. Real-time push would require a separate Nightscout integration (supported separately).

## Consequences

- Dashboard data is typically 5-10 minutes stale (pump sync latency + poll interval combined)
- Users should not rely on this integration for real-time clinical decisions — it is a monitoring/dashboard tool
- `sensor.tandem_data_age` reports the age of the last successful data fetch, making staleness visible to users
- The `tandem_last_pump_upload` and `tandem_last_glucose_update` timestamps allow users to detect when the pump has stopped syncing
- LTS statistics imported via `_import_statistics()` use the actual event timestamps from the API — poll timing does not affect historical accuracy
