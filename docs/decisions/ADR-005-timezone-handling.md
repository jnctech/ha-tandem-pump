# ADR-005: Pump Timestamp and Timezone Handling

**Date:** 2026-03-13
**Status:** Accepted

## Context

The Tandem Source API returns pump event timestamps as **naive datetimes** (no timezone offset). These timestamps represent the time on the pump's internal clock, which is set to the user's local timezone.

The API also returns `timezone` metadata (e.g., `"Australia/Adelaide"`) in the device/metadata response, representing the timezone the pump was configured in.

Baseline review finding L-4 noted this timezone attachment pattern.

## Decision

Timestamps are treated as **naive local time** during API parsing in `tandem_api.py`, then the pump's configured timezone is **attached at import time** in `_import_statistics()`.

Specifically (`__init__.py:2072-2076`):
```python
if ts.tzinfo is None:
    ts = ts.replace(tzinfo=tz)  # attach pump TZ
else:
    ts = ts.astimezone(tz)  # normalise if somehow aware
```

Where `tz = ZoneInfo(self.timezone)` uses the pump's configured timezone from the coordinator.

## Alternatives Considered

**Convert to UTC at parse time in `tandem_api.py`**
Rejected. UTC conversion at parse time requires knowing the UTC offset *at the moment of each event*. For historical events across DST transitions, the offset differs event-by-event. Applying a single current offset to all historical timestamps would produce incorrect UTC values for events that occurred under a different DST offset. Keeping timestamps naive and attaching the timezone (via `ZoneInfo`) allows Python's timezone library to resolve DST correctly per-event.

**Store all timestamps as UTC internally**
Rejected for the same reason. The API does not provide UTC offsets per event — only the pump timezone name. Naive → UTC conversion with historical DST accuracy requires the timezone rule database (ZoneInfo), which is what we use.

**Use a hardcoded timezone offset**
Rejected. Australia/Adelaide (UTC+9:30/+10:30) and other half-hour/DST timezones require full tz database support, not a fixed offset.

## Consequences

- `tzdata` Python package is required (added to `requirements.txt`) to provide ZoneInfo timezone rules in environments that don't include system tzdata (e.g., some Docker containers)
- The coordinator stores `self.timezone` (string, IANA format) fetched from API metadata
- The pump's configured timezone must be a valid IANA timezone name — if the API returns an unrecognised string, `ZoneInfo()` raises `ZoneInfoNotFoundError` (logged, falls back gracefully)
- Statistics Graph cards display times in HA's configured timezone — HA handles the final conversion from pump-TZ-aware timestamps to display timezone
