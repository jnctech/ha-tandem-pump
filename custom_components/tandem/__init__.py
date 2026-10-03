"""Tandem t:slim integration for Home Assistant.

Thin setup shell: builds the Source API client, wires the coordinator, forwards
the sensor/binary_sensor platforms, and registers the import_history /
capture_diagnostics services. All parsing/compute lives in coordinator.py.
"""

from __future__ import annotations

import functools
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REGION,
    DOMAIN,
    PLATFORMS,
    SCAN_INTERVAL,
)
from .coordinator import TandemConfigEntry, TandemCoordinator, TandemRuntimeData
from .exceptions import TandemAuthError
from .tandem_api import TandemSourceClient
from .util import convert_date_to_isodate, sanitize_for_logging

__all__ = [
    "TandemCoordinator",
    "TandemSourceClient",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
    "convert_date_to_isodate",
    "sanitize_for_logging",
]

_LOGGER = logging.getLogger(__name__)

SERVICE_IMPORT_HISTORY = "import_history"
SERVICE_CAPTURE_DIAGNOSTICS = "capture_diagnostics"


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_ENTRY_FIELD = {vol.Optional("config_entry_id"): cv.string}
IMPORT_HISTORY_SCHEMA = vol.Schema(
    {vol.Required("start_date"): cv.date, vol.Optional("end_date"): cv.date, **_ENTRY_FIELD}
)
CAPTURE_DIAGNOSTICS_SCHEMA = vol.Schema(_ENTRY_FIELD)


def _get_tandem_data(hass: HomeAssistant, call: ServiceCall) -> TandemRuntimeData:
    """Resolve the loaded Tandem entry a service call targets.

    Uses ``config_entry_id`` when given, otherwise the only loaded entry.
    """
    entry_id = call.data.get("config_entry_id")
    if entry_id:
        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            raise ServiceValidationError(f"Config entry '{entry_id}' is not a Tandem entry")
        entries = [entry]
    else:
        entries = hass.config_entries.async_entries(DOMAIN)
    loaded = [
        d
        for e in entries
        if e.state is ConfigEntryState.LOADED and isinstance(d := getattr(e, "runtime_data", None), TandemRuntimeData)
    ]
    if not loaded:
        raise ServiceValidationError("The Tandem integration is not loaded; set it up or wait for it to finish loading")
    if len(loaded) > 1:
        raise ServiceValidationError("More than one Tandem account is loaded; set config_entry_id")
    return loaded[0]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the service actions once, independent of any entry being loaded."""
    hass.services.async_register(
        DOMAIN, SERVICE_IMPORT_HISTORY, functools.partial(_handle_import_history, hass), IMPORT_HISTORY_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CAPTURE_DIAGNOSTICS,
        functools.partial(_handle_capture_diagnostics, hass),
        CAPTURE_DIAGNOSTICS_SCHEMA,
    )
    return True


async def _login(hass: HomeAssistant, coordinator: TandemCoordinator) -> None:
    """Log in for a service action; a rejected login also starts the reauth flow."""
    try:
        await coordinator.client.login()
    except TandemAuthError as err:
        coordinator.config_entry.async_start_reauth(hass)
        raise HomeAssistantError(f"Tandem rejected the login; reauthenticate the integration: {err}") from err
    except Exception as err:
        raise HomeAssistantError(f"Tandem login failed: {err}") from err


async def async_setup_entry(hass: HomeAssistant, entry: TandemConfigEntry) -> bool:
    """Set up Tandem from a config entry."""
    config = entry.data

    try:
        client = TandemSourceClient(
            email=config[CONF_EMAIL],
            password=config[CONF_PASSWORD],
            region=config.get(CONF_REGION, "EU"),
            session=get_async_client(hass),
        )
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to initialise Tandem client: {err}") from err

    coordinator = TandemCoordinator(hass, entry, client, update_interval=timedelta(seconds=config[SCAN_INTERVAL]))
    # The first refresh fetches only a short history window so entry setup stays
    # fast; the full window (trend stats + long-term statistics) is backfilled
    # immediately afterwards on a background task, off the setup critical path.
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = TandemRuntimeData(client=client, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_create_background_task(
        hass,
        coordinator.async_backfill_full_history(),
        name=f"tandem_backfill_{entry.entry_id}",
    )

    _LOGGER.info("Tandem entry setup completed: %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TandemConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        client = entry.runtime_data.client
        try:
            await client.close()
        except Exception as error:  # noqa: BLE001 - close must not raise during unload
            _LOGGER.warning("Failed to close Tandem client: %s", error)
        # runtime_data is dropped by Home Assistant automatically on unload.
    return unload_ok


async def _handle_import_history(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the tandem.import_history service call.

    Fetches pump events for the requested date range in 7-day chunks and imports
    them as long-term statistics (CGM glucose, active insulin, basal rate).
    """
    coordinator = _get_tandem_data(hass, call).coordinator

    try:
        start = date.fromisoformat(str(call.data["start_date"]))
        end_raw = call.data.get("end_date")
        end = date.fromisoformat(str(end_raw)) if end_raw else datetime.now(timezone.utc).date()
    except ValueError as err:
        raise ServiceValidationError(f"Invalid date: {err}") from err
    if end < start:
        raise ServiceValidationError(f"end_date {end} is before start_date {start}")

    _LOGGER.info("[Tandem] import_history: importing events %s → %s", start, end)

    await _login(hass, coordinator)

    # Retrieve tconnectDeviceId from pump metadata
    try:
        metadata_list = await coordinator.client.get_pump_event_metadata()
    except Exception as err:
        raise HomeAssistantError(f"Tandem pump metadata fetch failed: {err}") from err
    metadata_entry = None
    if isinstance(metadata_list, list) and metadata_list:
        metadata_entry = metadata_list[0]
    elif isinstance(metadata_list, dict):
        metadata_entry = metadata_list
    device_id = metadata_entry.get("tconnectDeviceId") if metadata_entry else None
    if not device_id:
        raise HomeAssistantError("Tandem pump metadata has no tconnectDeviceId")

    # Fetch events in 7-day chunks to avoid API timeouts on large date ranges
    chunk_start = start
    all_events: list[dict[str, Any]] = []
    failed: list[str] = []

    while chunk_start <= end:
        chunk_end = min(chunk_start + timedelta(days=6), end)
        try:
            events = await coordinator.client.get_pump_events(
                device_id,
                chunk_start.isoformat(),
                chunk_end.isoformat(),
            )
            if events:
                all_events.extend(events)
        except Exception as err:
            _LOGGER.warning("[Tandem] import_history: chunk %s → %s failed: %s", chunk_start, chunk_end, err)
            failed.append(f"{chunk_start} → {chunk_end}")
        chunk_start = chunk_end + timedelta(days=1)

    _LOGGER.info("[Tandem] import_history: fetched %d events total", len(all_events))

    # Import what was fetched even when a chunk failed, then say what is missing.
    problems: list[str] = []
    if failed:
        problems.append(f"these date ranges failed to fetch: {', '.join(failed)} (run the action again for them)")
    if not all_events:
        _LOGGER.warning("[Tandem] import_history: no events returned for %s → %s", start, end)
    else:
        try:
            failed_stats = await coordinator._import_statistics(all_events)
        except Exception as err:
            raise HomeAssistantError(f"Statistics import failed: {err}. {'; '.join(problems)}".rstrip(". ")) from err
        if failed_stats:
            problems.append(f"these statistics failed to write: {', '.join(failed_stats)} (see the log)")
    if problems:
        raise HomeAssistantError(f"Fetched {len(all_events)} events, but " + "; ".join(problems))


async def _handle_capture_diagnostics(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the tandem.capture_diagnostics service call.

    Fetches raw API responses and writes a sanitised diagnostic snapshot to
    /config/tandem_diagnostics_<timestamp>.json for schema documentation
    and troubleshooting.
    """
    coordinator = _get_tandem_data(hass, call).coordinator

    await _login(hass, coordinator)

    snapshot: dict[str, Any] = {"captured_at": datetime.now(timezone.utc).isoformat()}

    # 1. Raw pump metadata (contains schema fields we need to document)
    try:
        metadata_list = await coordinator.client.get_pump_event_metadata()
        snapshot["pump_event_metadata"] = sanitize_for_logging(metadata_list)
    except Exception as err:
        snapshot["pump_event_metadata_error"] = str(err)

    # 2. Pumper info
    try:
        pumper_info = await coordinator.client.get_pumper_info()
        snapshot["pumper_info"] = sanitize_for_logging(pumper_info)
    except Exception as err:
        snapshot["pumper_info_error"] = str(err)

    # 3. Pump events — decode and summarise (full events too large)
    device_id = None
    if snapshot.get("pump_event_metadata"):
        meta = snapshot["pump_event_metadata"]
        if isinstance(meta, list) and meta:
            device_id = meta[0].get("tconnectDeviceId")
        elif isinstance(meta, dict):
            device_id = meta.get("tconnectDeviceId")

    if device_id:
        from zoneinfo import ZoneInfo

        tz_name = coordinator.timezone or "UTC"
        try:
            tz = ZoneInfo(tz_name)
        except (KeyError, TypeError):
            tz = ZoneInfo("UTC")

        now_pump = datetime.now(tz)
        start = (now_pump - timedelta(days=7)).strftime("%Y-%m-%d")
        end = now_pump.strftime("%Y-%m-%d")

        try:
            events = await coordinator.client.get_pump_events(device_id, start, end)
            if events:
                # Event ID distribution
                id_counts: dict[str, int] = {}
                for evt in events:
                    name = evt.get("event_name", f"Event_{evt.get('event_id')}")
                    id_counts[name] = id_counts.get(name, 0) + 1
                snapshot["pump_events_summary"] = {
                    "date_range": f"{start} to {end}",
                    "total_events": len(events),
                    "event_counts": dict(sorted(id_counts.items())),
                }
                # Include sample of each event type (first occurrence)
                seen_types: set[str] = set()
                samples: list[dict[str, Any]] = []
                for evt in events:
                    name = evt.get("event_name", "unknown")
                    if name not in seen_types:
                        seen_types.add(name)
                        sample = dict(evt)
                        # Convert datetime to string for JSON
                        if "timestamp" in sample:
                            sample["timestamp"] = str(sample["timestamp"])
                        samples.append(sample)
                snapshot["pump_events_samples"] = samples
            else:
                snapshot["pump_events_summary"] = {"total_events": 0}
        except Exception as err:
            snapshot["pump_events_error"] = str(err)
    else:
        snapshot["pump_events_skipped"] = "no tconnectDeviceId in pump metadata"

    # 4. Current sensor state (keys and their types/values)
    if coordinator.data:
        sensor_state: dict[str, Any] = {}
        for k, v in coordinator.data.items():
            if v is None:
                sensor_state[k] = "UNAVAILABLE"
            elif hasattr(v, "isoformat"):
                sensor_state[k] = v.isoformat()
            else:
                sensor_state[k] = v
        snapshot["current_sensor_state"] = sanitize_for_logging(sensor_state)

    # Write to HA config directory
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = hass.config.path(f"tandem_diagnostics_{ts_str}.json")

    def _write() -> None:
        with open(out_path, "w") as f:
            json.dump(snapshot, f, indent=2, default=str)

    try:
        await hass.async_add_executor_job(_write)
    except OSError as err:
        raise HomeAssistantError(f"Could not write diagnostic snapshot to {out_path}: {err}") from err
    _LOGGER.info("[Tandem] Diagnostic snapshot written to %s", out_path)
    if "pump_event_metadata_error" in snapshot and "pumper_info_error" in snapshot:
        raise HomeAssistantError(f"Every Tandem fetch failed; the snapshot at {out_path} holds only the errors")
