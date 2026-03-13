"""Medtronic Carelink / Tandem t:slim integration."""

from __future__ import annotations

import functools
import json
import logging
import math
import os
import re
import shutil

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.util.dt import DEFAULT_TIME_ZONE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import CarelinkClient, LEGACY_AUTH_FILE, AUTH_FILE_PREFIX, SHARED_AUTH_FILE
from .tandem_api import (
    TandemSourceClient,
    TandemAuthError,
    TandemApiError,
    parse_dotnet_date,
    EVT_CGM_DATA_GXB,
    EVT_CGM_DATA_G7,
    EVT_CGM_DATA_FSL2,
    EVT_AA_DAILY_STATUS,
    EVT_BOLUS_COMPLETED,
    EVT_BOLEX_COMPLETED,
    EVT_BOLUS_DELIVERY,
    EVT_BASAL_RATE_CHANGE,
    EVT_BASAL_DELIVERY,
    EVT_PUMPING_SUSPENDED,
    EVT_PUMPING_RESUMED,
    EVT_BG_READING_TAKEN,
    EVT_CARTRIDGE_FILLED,
    EVT_CARBS_ENTERED,
    EVT_CANNULA_FILLED,
    EVT_TUBING_FILLED,
    EVT_AA_USER_MODE_CHANGE,
    EVT_AA_PCM_CHANGE,
    EVT_DAILY_BASAL,
    EVT_SHELF_MODE,
    EVT_USB_CONNECTED,
    EVT_USB_DISCONNECTED,
    EVT_ALERT_ACTIVATED,
    EVT_ALERT_CLEARED,
    EVT_ALARM_ACTIVATED,
    EVT_MALFUNCTION_ACTIVATED,
    EVT_ALARM_CLEARED,
)
from .nightscout_uploader import NightscoutUploader
from .helpers import is_data_stale

from .const import (
    CLIENT,
    TANDEM_CLIENT,
    UPLOADER,
    DOMAIN,
    SCAN_INTERVAL,
    COORDINATOR,
    UNAVAILABLE,
    PLATFORM_TYPE,
    PLATFORM_CARELINK,
    PLATFORM_TANDEM,
    DEVICE_PUMP_MODEL,
    DEVICE_PUMP_NAME,
    DEVICE_PUMP_SERIAL,
    DEVICE_PUMP_MANUFACTURER,
    SENSOR_KEY_PUMP_BATTERY_LEVEL,
    SENSOR_KEY_CONDUIT_BATTERY_LEVEL,
    SENSOR_KEY_SENSOR_BATTERY_LEVEL,
    SENSOR_KEY_SENSOR_DURATION_HOURS,
    SENSOR_KEY_SENSOR_DURATION_MINUTES,
    SENSOR_KEY_LASTSG_MGDL,
    SENSOR_KEY_LASTSG_MMOL,
    SENSOR_KEY_UPDATE_TIMESTAMP,
    SENSOR_KEY_LASTSG_TIMESTAMP,
    SENSOR_KEY_LASTSG_TREND,
    SENSOR_KEY_SG_DELTA,
    SENSOR_KEY_RESERVOIR_LEVEL,
    SENSOR_KEY_RESERVOIR_AMOUNT,
    SENSOR_KEY_RESERVOIR_REMAINING_UNITS,
    SENSOR_KEY_ACTIVE_INSULIN,
    SENSOR_KEY_ACTIVE_INSULIN_ATTRS,
    SENSOR_KEY_LAST_ALARM,
    SENSOR_KEY_LAST_ALARM_ATTRS,
    SENSOR_KEY_ACTIVE_BASAL_PATTERN,
    SENSOR_KEY_AVG_GLUCOSE_MMOL,
    SENSOR_KEY_AVG_GLUCOSE_MGDL,
    SENSOR_KEY_BELOW_HYPO_LIMIT,
    SENSOR_KEY_ABOVE_HYPER_LIMIT,
    SENSOR_KEY_TIME_IN_RANGE,
    SENSOR_KEY_MAX_AUTO_BASAL_RATE,
    SENSOR_KEY_SG_BELOW_LIMIT,
    SENSOR_KEY_LAST_MEAL_MARKER,
    SENSOR_KEY_LAST_MEAL_MARKER_ATTRS,
    SENSOR_KEY_ACTIVE_NOTIFICATION,
    SENSOR_KEY_ACTIVE_NOTIFICATION_ATTRS,
    SENSOR_KEY_LAST_INSULIN_MARKER,
    SENSOR_KEY_LAST_INSULIN_MARKER_ATTRS,
    SENSOR_KEY_LAST_AUTO_BASAL_DELIVERY_MARKER,
    SENSOR_KEY_LAST_AUTO_BASAL_DELIVERY_MARKER_ATTRS,
    SENSOR_KEY_LAST_AUTO_MODE_STATUS_MARKER,
    SENSOR_KEY_LAST_AUTO_MODE_STATUS_MARKER_ATTRS,
    SENSOR_KEY_LAST_LOW_GLUCOSE_SUSPENDED_MARKER,
    SENSOR_KEY_LAST_LOW_GLUCOSE_SUSPENDED_MARKER_ATTRS,
    BINARY_SENSOR_KEY_PUMP_COMM_STATE,
    BINARY_SENSOR_KEY_SENSOR_COMM_STATE,
    BINARY_SENSOR_KEY_CONDUIT_IN_RANGE,
    BINARY_SENSOR_KEY_CONDUIT_PUMP_IN_RANGE,
    BINARY_SENSOR_KEY_CONDUIT_SENSOR_IN_RANGE,
    SENSOR_KEY_CLIENT_TIMEZONE,
    SENSOR_KEY_APP_MODEL_TYPE,
    SENSOR_KEY_MEDICAL_DEVICE_MANUFACTURER,
    SENSOR_KEY_MEDICAL_DEVICE_MODEL_NUMBER,
    SENSOR_KEY_MEDICAL_DEVICE_HARDWARE_REVISION,
    SENSOR_KEY_MEDICAL_DEVICE_FIRMWARE_REVISION,
    SENSOR_KEY_MEDICAL_DEVICE_SYSTEM_ID,
    MS_TIMEZONE_TO_IANA_MAP,
    SENSOR_KEY_TIME_TO_NEXT_CALIB_HOURS,
    CARELINK_CODE_MAP,
    # Tandem sensor keys
    TANDEM_SENSOR_KEY_LASTSG_MMOL,
    TANDEM_SENSOR_KEY_LASTSG_MGDL,
    TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP,
    TANDEM_SENSOR_KEY_SG_DELTA,
    TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS,
    TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP,
    TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS,
    TANDEM_SENSOR_KEY_BASAL_RATE,
    TANDEM_SENSOR_KEY_ACTIVE_INSULIN,
    TANDEM_SENSOR_KEY_LAST_UPLOAD,
    TANDEM_SENSOR_KEY_SOFTWARE_VERSION,
    TANDEM_SENSOR_KEY_PUMP_SERIAL_INFO,
    TANDEM_SENSOR_KEY_PUMP_MODEL_INFO,
    TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL,
    TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL,
    TANDEM_SENSOR_KEY_TIME_IN_RANGE as TANDEM_TIME_IN_RANGE,
    TANDEM_SENSOR_KEY_CGM_USAGE,
    TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS,
    TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP,
    TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS,
    TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS,
    # Computed CGM summary
    TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV,
    TANDEM_SENSOR_KEY_GLUCOSE_CV,
    TANDEM_SENSOR_KEY_GMI,
    TANDEM_SENSOR_KEY_TIME_BELOW_RANGE,
    TANDEM_SENSOR_KEY_TIME_ABOVE_RANGE,
    # New event-derived sensors
    TANDEM_SENSOR_KEY_ACTIVITY_MODE,
    TANDEM_SENSOR_KEY_CONTROL_IQ_MODE,
    TANDEM_SENSOR_KEY_PUMP_SUSPENDED,
    TANDEM_SENSOR_KEY_LAST_CARBS,
    TANDEM_SENSOR_KEY_LAST_CARBS_TIMESTAMP,
    TANDEM_SENSOR_KEY_LAST_CARTRIDGE_CHANGE,
    TANDEM_SENSOR_KEY_LAST_SITE_CHANGE,
    TANDEM_SENSOR_KEY_LAST_TUBING_CHANGE,
    TANDEM_SENSOR_KEY_CARTRIDGE_INSULIN,
    TANDEM_SENSOR_KEY_LAST_BG_READING,
    TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE,
    TANDEM_SENSOR_KEY_CGM_STATUS,
    TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL,
    TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON,
    # Event-derived lookup maps
    CGM_STATUS_MAP,
    TANDEM_ALERT_MAP,
    TANDEM_ALARM_MAP,
    # Computed insulin summary
    TANDEM_SENSOR_KEY_TOTAL_DAILY_INSULIN,
    TANDEM_SENSOR_KEY_DAILY_BOLUS_TOTAL,
    TANDEM_SENSOR_KEY_DAILY_BASAL_TOTAL,
    TANDEM_SENSOR_KEY_BASAL_BOLUS_SPLIT,
    TANDEM_SENSOR_KEY_DAILY_CARBS,
    TANDEM_SENSOR_KEY_DAILY_BOLUS_COUNT,
    # Pump settings (from metadata.lastUpload.settings)
    TANDEM_SENSOR_KEY_ACTIVE_PROFILE,
    TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS,
    TANDEM_SENSOR_KEY_CONTROL_IQ_ENABLED,
    TANDEM_SENSOR_KEY_CONTROL_IQ_WEIGHT,
    TANDEM_SENSOR_KEY_CONTROL_IQ_TDI,
    TANDEM_SENSOR_KEY_MAX_BOLUS,
    TANDEM_SENSOR_KEY_BASAL_LIMIT,
    TANDEM_SENSOR_KEY_CGM_HIGH_ALERT,
    TANDEM_SENSOR_KEY_CGM_LOW_ALERT,
    TANDEM_SENSOR_KEY_LOW_BG_THRESHOLD,
    TANDEM_SENSOR_KEY_HIGH_BG_THRESHOLD,
    TANDEM_SENSOR_KEY_LOW_INSULIN_ALERT,
    # Battery monitoring (Phase 1)
    TANDEM_SENSOR_KEY_BATTERY_PERCENT,
    TANDEM_SENSOR_KEY_BATTERY_VOLTAGE,
    TANDEM_SENSOR_KEY_BATTERY_REMAINING_MAH,
    TANDEM_SENSOR_KEY_CHARGING_STATUS,
    # Alerts & Alarms (Phase 2)
    TANDEM_SENSOR_KEY_LAST_ALERT,
    TANDEM_SENSOR_KEY_LAST_ALARM,
    TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT,
    # CGM sensor type (Phase 3)
    TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE,
)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.NUMBER]

_LOGGER = logging.getLogger(__name__)

SERVICE_IMPORT_HISTORY = "import_history"
SERVICE_CAPTURE_DIAGNOSTICS = "capture_diagnostics"


# Fields containing personally identifiable information that should be redacted.
# Note: "name" is intentionally broad — it catches pumper_info.name (full name)
# and profile[].name (often the patient's first name). This over-redacts
# non-PII profile names like "Sick" or "Active", but PII protection takes
# priority.  Profile idp index is sufficient for debugging.
PII_FIELDS = {
    "firstName",
    "lastName",
    "name",
    "birthdate",
    "username",
    "patientId",
    "conduitSerialNumber",
    "medicalDeviceSerialNumber",
    "systemId",
    "email",
    "phone",
    "emailAddress",
    "phoneNumber",
    "address",
    "dateOfBirth",
    "dob",
    "deviceSerialNumber",
    "patientName",
    "patientDateOfBirth",
    "patientCareGiver",
}


def sanitize_for_logging(data, depth=0):
    """Recursively sanitize data by redacting PII fields for safe logging."""
    if depth > 10:  # Prevent infinite recursion
        return "[MAX_DEPTH]"
    if isinstance(data, dict):
        return {k: "[REDACTED]" if k in PII_FIELDS else sanitize_for_logging(v, depth + 1) for k, v in data.items()}
    if isinstance(data, list):
        return [sanitize_for_logging(item, depth + 1) for item in data]
    return data


def convert_date_to_isodate(date):
    date_iso = re.sub(r"\.\d{3}Z$", "+00:00", date)
    dt = datetime.fromisoformat(date_iso)
    # Normalize any UTC offset to UTC before stripping tzinfo so the resulting
    # naive datetime always represents UTC, regardless of what offset the API sent.
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _migrate_legacy_logindata(config_path: str, entry_id: str) -> None:
    """Migrate logindata.json from old location to new entry-specific location.

    Priority order for source:
    1. Shared location: {config_path}/carelink_logindata.json (token generator add-on)
    2. Legacy location: custom_components/carelink/logindata.json

    Target: {config_path}/carelink_logindata_{entry_id}.json

    Note: Source files are NOT deleted after migration to serve as fallback
    if the entry-specific location becomes unavailable.
    """
    new_filename = f"{AUTH_FILE_PREFIX}_{entry_id}.json"
    new_path = os.path.join(config_path, new_filename)

    # If entry-specific file already exists, no migration needed
    if os.path.exists(new_path):
        _LOGGER.debug("Entry-specific logindata already exists: %s", new_path)
        return

    shared_path = os.path.join(config_path, SHARED_AUTH_FILE)
    legacy_path = os.path.join(config_path, LEGACY_AUTH_FILE)

    # Try shared location first (token generator add-on writes here)
    if os.path.exists(shared_path):
        try:
            shutil.copy(shared_path, new_path)
            _LOGGER.info("Copied logindata from shared location %s to %s", shared_path, new_path)
            return
        except OSError as error:
            _LOGGER.warning(
                "Failed to copy logindata from %s to %s: %s. Will use fallback location at runtime.",
                shared_path,
                new_path,
                error,
            )

    # Try legacy location (old installations)
    if os.path.exists(legacy_path):
        try:
            shutil.copy(legacy_path, new_path)
            _LOGGER.info("Migrated logindata from legacy location %s to %s", legacy_path, new_path)
            return
        except OSError as error:
            _LOGGER.warning(
                "Failed to migrate logindata from %s to %s: %s. Will use fallback location at runtime.",
                legacy_path,
                new_path,
                error,
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up carelink from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    config = entry.data
    platform_type = config.get(PLATFORM_TYPE, PLATFORM_CARELINK)

    if platform_type == PLATFORM_TANDEM:
        return await _async_setup_tandem_entry(hass, entry, config)
    return await _async_setup_carelink_entry(hass, entry, config)


async def _async_setup_carelink_entry(hass: HomeAssistant, entry: ConfigEntry, config: dict) -> bool:
    """Set up a Medtronic Carelink config entry."""
    # Migrate logindata from old location if needed
    _migrate_legacy_logindata(hass.config.path(), entry.entry_id)

    carelink_client = CarelinkClient(
        config["cl_refresh_token"],
        config["cl_token"],
        config["cl_client_id"],
        config["cl_client_secret"],
        config["cl_mag_identifier"],
        config["patientId"],
        config_path=hass.config.path(),
        entry_id=entry.entry_id,
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        CLIENT: carelink_client,
        PLATFORM_TYPE: PLATFORM_CARELINK,
    }

    if config.get("nightscout_url") and config.get("nightscout_api"):
        nightscout_uploader = NightscoutUploader(config["nightscout_url"], config["nightscout_api"])
        hass.data[DOMAIN][entry.entry_id][UPLOADER] = nightscout_uploader

    coordinator = CarelinkCoordinator(hass, entry, update_interval=timedelta(seconds=config[SCAN_INTERVAL]))

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id][COORDINATOR] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _handle_import_history(hass: HomeAssistant, entry_id: str, call: ServiceCall) -> None:
    """Handle the carelink.import_history service call.

    Fetches pump events for the requested date range in 7-day chunks and imports
    them as long-term statistics (CGM glucose, active insulin, basal rate).
    """
    coordinator = hass.data[DOMAIN][entry_id][COORDINATOR]

    start_str: str = call.data["start_date"]
    end_str: str = call.data.get("end_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    _LOGGER.info("[Tandem] import_history: importing events %s → %s", start_str, end_str)

    try:
        await coordinator.client.login()
    except Exception as err:
        _LOGGER.error("[Tandem] import_history: authentication failed: %s", err)
        return

    # Retrieve tconnectDeviceId from pump metadata
    try:
        metadata_list = await coordinator.client.get_pump_event_metadata()
        metadata_entry = None
        if isinstance(metadata_list, list) and metadata_list:
            metadata_entry = metadata_list[0]
        elif isinstance(metadata_list, dict):
            metadata_entry = metadata_list
        device_id = metadata_entry.get("tconnectDeviceId") if metadata_entry else None
    except Exception as err:
        _LOGGER.error("[Tandem] import_history: metadata fetch failed: %s", err)
        return

    if not device_id:
        _LOGGER.error("[Tandem] import_history: no tconnectDeviceId found in pump metadata")
        return

    # Fetch events in 7-day chunks to avoid API timeouts on large date ranges
    chunk_start = date.fromisoformat(start_str)
    chunk_end_limit = date.fromisoformat(end_str)
    all_events: list[dict] = []

    while chunk_start <= chunk_end_limit:
        chunk_end = min(chunk_start + timedelta(days=6), chunk_end_limit)
        try:
            events = await coordinator.client.get_pump_events(
                device_id,
                chunk_start.isoformat(),
                chunk_end.isoformat(),
            )
            if events:
                all_events.extend(events)
        except Exception as err:
            _LOGGER.warning(
                "[Tandem] import_history: chunk %s → %s failed: %s",
                chunk_start.isoformat(),
                chunk_end.isoformat(),
                err,
            )
        chunk_start = chunk_end + timedelta(days=1)

    _LOGGER.info("[Tandem] import_history: fetched %d events total", len(all_events))

    if all_events:
        await coordinator._import_statistics(all_events)
    else:
        _LOGGER.warning(
            "[Tandem] import_history: no events returned for %s → %s",
            start_str,
            end_str,
        )


async def _handle_capture_diagnostics(hass: HomeAssistant, entry_id: str, call: ServiceCall) -> None:
    """Handle the carelink.capture_diagnostics service call.

    Fetches raw API responses and writes a sanitised diagnostic snapshot to
    /config/carelink_diagnostics_<timestamp>.json for schema documentation
    and troubleshooting.
    """
    coordinator = hass.data[DOMAIN][entry_id][COORDINATOR]

    try:
        await coordinator.client.login()
    except Exception as err:
        _LOGGER.error("[Tandem] capture_diagnostics: authentication failed: %s", err)
        return

    snapshot: dict = {"captured_at": datetime.now(timezone.utc).isoformat()}

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
                samples: list[dict] = []
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

    # 4. Current sensor state (keys and their types/values)
    if coordinator.data:
        sensor_state: dict = {}
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
    out_path = hass.config.path(f"carelink_diagnostics_{ts_str}.json")

    try:
        import aiofiles

        async with aiofiles.open(out_path, "w") as f:
            await f.write(json.dumps(snapshot, indent=2, default=str))
        _LOGGER.info("[Tandem] Diagnostic snapshot written to %s", out_path)
    except ImportError:
        # aiofiles not available — fall back to sync write in executor
        import asyncio

        def _write():
            with open(out_path, "w") as f:
                json.dump(snapshot, f, indent=2, default=str)

        await asyncio.get_running_loop().run_in_executor(None, _write)
        _LOGGER.info("[Tandem] Diagnostic snapshot written to %s", out_path)


async def _async_setup_tandem_entry(hass: HomeAssistant, entry: ConfigEntry, config: dict) -> bool:
    """Set up a Tandem t:slim Source config entry."""
    _LOGGER.info("Setting up Tandem entry: %s", entry.entry_id)

    tandem_client = TandemSourceClient(
        email=config["tandem_email"],
        password=config["tandem_password"],
        region=config.get("tandem_region", "EU"),
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        TANDEM_CLIENT: tandem_client,
        PLATFORM_TYPE: PLATFORM_TANDEM,
    }

    if config.get("nightscout_url") and config.get("nightscout_api"):
        nightscout_uploader = NightscoutUploader(config["nightscout_url"], config["nightscout_api"])
        hass.data[DOMAIN][entry.entry_id][UPLOADER] = nightscout_uploader

    coordinator = TandemCoordinator(hass, entry, update_interval=timedelta(seconds=config[SCAN_INTERVAL]))

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id][COORDINATOR] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ── Register service actions (Tandem platform only) ────────────────
    if not hass.services.has_service(DOMAIN, SERVICE_IMPORT_HISTORY):
        hass.services.async_register(
            DOMAIN,
            SERVICE_IMPORT_HISTORY,
            functools.partial(_handle_import_history, hass, entry.entry_id),
        )
    if not hass.services.has_service(DOMAIN, SERVICE_CAPTURE_DIAGNOSTICS):
        hass.services.async_register(
            DOMAIN,
            SERVICE_CAPTURE_DIAGNOSTICS,
            functools.partial(_handle_capture_diagnostics, hass, entry.entry_id),
        )

    _LOGGER.info("Tandem entry setup completed")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        if hass.services.has_service(DOMAIN, SERVICE_IMPORT_HISTORY):
            hass.services.async_remove(DOMAIN, SERVICE_IMPORT_HISTORY)
        entry_data = hass.data[DOMAIN].pop(entry.entry_id)
        # Close HTTP clients to prevent memory leaks
        if CLIENT in entry_data:
            try:
                await entry_data[CLIENT].close()
            except Exception as error:
                _LOGGER.warning("Failed to close Carelink client: %s", error)
        if TANDEM_CLIENT in entry_data:
            try:
                await entry_data[TANDEM_CLIENT].close()
            except Exception as error:
                _LOGGER.warning("Failed to close Tandem client: %s", error)
        if UPLOADER in entry_data:
            try:
                await entry_data[UPLOADER].close()
            except Exception as error:
                _LOGGER.warning("Failed to close Nightscout uploader: %s", error)

    return unload_ok


# ═══════════════════════════════════════════════════════════════════════════
# Carelink (Medtronic) Coordinator
# ═══════════════════════════════════════════════════════════════════════════


class CarelinkCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Carelink API."""

    def __init__(self, hass: HomeAssistant, entry, update_interval: timedelta):

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

        self.entry_id = entry.entry_id
        self.configuration_url = "https://carelink.minimed.eu"
        self.uploader = None
        self.client = hass.data[DOMAIN][entry.entry_id][CLIENT]
        self.timezone = hass.config.time_zone
        self._last_sg_timestamp: str | None = None

        if UPLOADER in hass.data[DOMAIN][entry.entry_id]:
            self.uploader = hass.data[DOMAIN][entry.entry_id][UPLOADER]

    async def _async_update_data(self):

        data = {}
        client_timezone = DEFAULT_TIME_ZONE

        try:
            await self.client.login()
            recent_data = await self.client.get_recent_data()
        except Exception as err:
            raise UpdateFailed(f"Carelink data fetch failed: {err}") from err

        if recent_data is None:
            recent_data = {}
        if recent_data and "patientData" in recent_data:
            recent_data = recent_data["patientData"]

        _LOGGER.debug("Before Data parsing %s", sanitize_for_logging(recent_data))
        try:
            if recent_data is not None and "clientTimeZoneName" in recent_data:
                client_timezone = recent_data["clientTimeZoneName"]

            data[SENSOR_KEY_CLIENT_TIMEZONE] = client_timezone

            timezone_map = MS_TIMEZONE_TO_IANA_MAP.get(client_timezone, DEFAULT_TIME_ZONE)

            timezone = ZoneInfo(str(timezone_map))

        except Exception as error:
            _LOGGER.error("Can not set timezone to %s. The error was: %s", timezone_map, error)
            timezone = ZoneInfo("Europe/London")

        _LOGGER.debug("Using timezone %s", timezone)

        if self.uploader:
            await self.uploader.send_recent_data(recent_data, timezone)

        recent_data.setdefault("lastConduitDateTime", "")
        recent_data.setdefault("activeInsulin", {})
        recent_data.setdefault("therapyAlgorithmState", {})
        recent_data.setdefault("lastAlarm", {})
        recent_data.setdefault("markers", [])
        recent_data.setdefault("sgs", [])
        recent_data.setdefault("notificationHistory", {})

        # Last Update fetch

        if recent_data["lastConduitDateTime"]:
            date_time_local = convert_date_to_isodate(recent_data["lastConduitDateTime"])
            data[SENSOR_KEY_UPDATE_TIMESTAMP] = date_time_local.replace(tzinfo=timezone)

        # Last Glucose level sensors

        current_sg = get_sg(recent_data["sgs"], 0)
        prev_sg = get_sg(recent_data["sgs"], 1)

        if current_sg and "timestamp" in current_sg:
            date_time_local = convert_date_to_isodate(current_sg["timestamp"])
            data[SENSOR_KEY_LASTSG_TIMESTAMP] = date_time_local.replace(tzinfo=timezone)
            data[SENSOR_KEY_LASTSG_MMOL] = float(round(current_sg["sg"] * 0.0555, 2))
            data[SENSOR_KEY_LASTSG_MGDL] = current_sg["sg"]
            if prev_sg:
                data[SENSOR_KEY_SG_DELTA] = float(current_sg["sg"]) - float(prev_sg["sg"])

        # ── Historical SG readings for statistics ─────────────────────
        all_valid_sgs = [
            sg
            for sg in recent_data["sgs"]
            if sg.get("sensorState") == "NO_ERROR_MESSAGE"
            and sg.get("sg") is not None
            and sg.get("sg", 0) > 0
            and "timestamp" in sg
        ]
        all_valid_sgs.sort(key=lambda x: convert_date_to_isodate(x["timestamp"]))

        if all_valid_sgs:
            # Store readings history as attributes for custom cards
            _MAX_SG_HISTORY = 24  # ~2 hours of 5-min readings
            recent_sgs = all_valid_sgs[-_MAX_SG_HISTORY:]
            sg_readings_mgdl = []
            sg_readings_mmol = []
            for sg in recent_sgs:
                ts_iso = convert_date_to_isodate(sg["timestamp"]).replace(tzinfo=timezone).isoformat()
                sg_readings_mgdl.append({"t": ts_iso, "v": sg["sg"]})
                sg_readings_mmol.append({"t": ts_iso, "v": round(float(sg["sg"]) * 0.0555, 2)})
            data[f"{SENSOR_KEY_LASTSG_MGDL}_attributes"] = {
                "readings": sg_readings_mgdl,
            }
            data[f"{SENSOR_KEY_LASTSG_MMOL}_attributes"] = {
                "readings": sg_readings_mmol,
            }
        # Sensors

        data[SENSOR_KEY_PUMP_BATTERY_LEVEL] = recent_data.get("pumpBatteryLevelPercent", UNAVAILABLE)
        data[SENSOR_KEY_CONDUIT_BATTERY_LEVEL] = recent_data.get("conduitBatteryLevel", UNAVAILABLE)
        data[SENSOR_KEY_SENSOR_BATTERY_LEVEL] = recent_data.get("gstBatteryLevel", UNAVAILABLE)
        data[SENSOR_KEY_SENSOR_DURATION_HOURS] = recent_data.get("sensorDurationHours", UNAVAILABLE)
        data[SENSOR_KEY_SENSOR_DURATION_MINUTES] = recent_data.get("sensorDurationMinutes", UNAVAILABLE)
        data[SENSOR_KEY_RESERVOIR_LEVEL] = recent_data.get("reservoirLevelPercent", UNAVAILABLE)
        data[SENSOR_KEY_RESERVOIR_AMOUNT] = recent_data.get("reservoirAmount", UNAVAILABLE)
        data[SENSOR_KEY_RESERVOIR_REMAINING_UNITS] = recent_data.get("reservoirRemainingUnits", UNAVAILABLE)
        data[SENSOR_KEY_LASTSG_TREND] = recent_data.get("lastSGTrend", UNAVAILABLE)

        data[SENSOR_KEY_TIME_TO_NEXT_CALIB_HOURS] = recent_data.get("timeToNextCalibHours", UNAVAILABLE)

        if recent_data["activeInsulin"]:
            if "amount" in recent_data["activeInsulin"]:
                active_insulin = recent_data["activeInsulin"]

                amount = recent_data["activeInsulin"].get("amount")
                if amount is not None and float(amount) >= 0:
                    data[SENSOR_KEY_ACTIVE_INSULIN] = round(float(amount), 2)

                    if "datetime" in active_insulin:
                        date_time_local = convert_date_to_isodate(active_insulin["datetime"])

                        data[SENSOR_KEY_ACTIVE_INSULIN_ATTRS] = {
                            "last_update": date_time_local.replace(tzinfo=timezone)
                        }
        else:
            data[SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE
            data[SENSOR_KEY_ACTIVE_INSULIN_ATTRS] = {}

        if recent_data["lastAlarm"] and "dateTime" in recent_data["lastAlarm"]:
            # Last alarm sensor
            last_alarm = recent_data["lastAlarm"]

            date_time_local = convert_date_to_isodate(last_alarm["dateTime"])

            last_alarm["dateTime"] = date_time_local
            # Handle both numeric and string faultId values (Simplera sensor uses strings like 'alert.sg.threshold.low')
            fault_id = last_alarm.get("faultId")
            if fault_id is not None:
                try:
                    last_alarm["messageId"] = CARELINK_CODE_MAP.get(int(fault_id), "UNKNOWN")
                except (ValueError, TypeError):
                    # String faultId (e.g. 'alert.sg.threshold.low') - use as-is since it's already descriptive
                    last_alarm["messageId"] = str(fault_id)
            else:
                last_alarm["messageId"] = "UNKNOWN"

            data[SENSOR_KEY_LAST_ALARM] = date_time_local.replace(tzinfo=timezone)
            data[SENSOR_KEY_LAST_ALARM_ATTRS] = last_alarm
            active_notification = get_active_notification(last_alarm, recent_data["notificationHistory"])

            if active_notification:
                data[SENSOR_KEY_ACTIVE_NOTIFICATION] = date_time_local.replace(tzinfo=timezone)
                data[SENSOR_KEY_ACTIVE_NOTIFICATION_ATTRS] = last_alarm
            else:
                data[SENSOR_KEY_ACTIVE_NOTIFICATION] = UNAVAILABLE
                data[SENSOR_KEY_ACTIVE_NOTIFICATION_ATTRS] = {}
        else:
            data[SENSOR_KEY_LAST_ALARM] = UNAVAILABLE
            data[SENSOR_KEY_LAST_ALARM_ATTRS] = {}
            data[SENSOR_KEY_ACTIVE_NOTIFICATION] = UNAVAILABLE
            data[SENSOR_KEY_ACTIVE_NOTIFICATION_ATTRS] = {}

        if (
            recent_data["therapyAlgorithmState"] is not None
            and "autoModeShieldState" in recent_data["therapyAlgorithmState"]
        ):
            data[SENSOR_KEY_ACTIVE_BASAL_PATTERN] = recent_data["therapyAlgorithmState"].get(
                "autoModeShieldState", UNAVAILABLE
            )
        else:
            data[SENSOR_KEY_ACTIVE_BASAL_PATTERN] = UNAVAILABLE

        average_sg_raw = recent_data.get("averageSG")
        if average_sg_raw is not None:
            data[SENSOR_KEY_AVG_GLUCOSE_MMOL] = float(round(average_sg_raw * 0.0555, 2))
            data[SENSOR_KEY_AVG_GLUCOSE_MGDL] = average_sg_raw
        else:
            data[SENSOR_KEY_AVG_GLUCOSE_MMOL] = UNAVAILABLE
            data[SENSOR_KEY_AVG_GLUCOSE_MGDL] = UNAVAILABLE

        data[SENSOR_KEY_BELOW_HYPO_LIMIT] = recent_data.get("belowHypoLimit", UNAVAILABLE)
        data[SENSOR_KEY_ABOVE_HYPER_LIMIT] = recent_data.get("aboveHyperLimit", UNAVAILABLE)
        data[SENSOR_KEY_TIME_IN_RANGE] = recent_data.get("timeInRange", UNAVAILABLE)
        data[SENSOR_KEY_MAX_AUTO_BASAL_RATE] = recent_data.get("maxAutoBasalRate", UNAVAILABLE)
        data[SENSOR_KEY_SG_BELOW_LIMIT] = recent_data.get("sgBelowLimit", UNAVAILABLE)

        last_meal_marker = get_last_marker("MEAL", recent_data["markers"])

        if last_meal_marker is not None:
            data[SENSOR_KEY_LAST_MEAL_MARKER] = last_meal_marker["DATETIME"].replace(tzinfo=timezone)
            data[SENSOR_KEY_LAST_MEAL_MARKER_ATTRS] = last_meal_marker["ATTRS"]
        else:
            data[SENSOR_KEY_LAST_MEAL_MARKER] = UNAVAILABLE

        last_insuline_marker = get_last_marker("INSULIN", recent_data["markers"])

        if last_insuline_marker is not None:
            data[SENSOR_KEY_LAST_INSULIN_MARKER] = last_insuline_marker["DATETIME"].replace(tzinfo=timezone)
            data[SENSOR_KEY_LAST_INSULIN_MARKER_ATTRS] = last_insuline_marker["ATTRS"]
        else:
            data[SENSOR_KEY_LAST_INSULIN_MARKER] = UNAVAILABLE

        last_autobasal_marker = get_last_marker("AUTO_BASAL_DELIVERY", recent_data["markers"])

        if last_autobasal_marker is not None:
            data[SENSOR_KEY_LAST_AUTO_BASAL_DELIVERY_MARKER] = last_autobasal_marker["DATETIME"].replace(
                tzinfo=timezone
            )
            data[SENSOR_KEY_LAST_AUTO_BASAL_DELIVERY_MARKER_ATTRS] = last_autobasal_marker["ATTRS"]
        else:
            data[SENSOR_KEY_LAST_AUTO_BASAL_DELIVERY_MARKER] = UNAVAILABLE

        last_auto_mode_status_marker = get_last_marker("AUTO_MODE_STATUS", recent_data["markers"])

        if last_auto_mode_status_marker is not None:
            data[SENSOR_KEY_LAST_AUTO_MODE_STATUS_MARKER] = last_auto_mode_status_marker["DATETIME"].replace(
                tzinfo=timezone
            )
            data[SENSOR_KEY_LAST_AUTO_MODE_STATUS_MARKER_ATTRS] = last_auto_mode_status_marker["ATTRS"]
        else:
            data[SENSOR_KEY_LAST_AUTO_MODE_STATUS_MARKER] = UNAVAILABLE

        last_low_glucose_marker = get_last_marker("LOW_GLUCOSE_SUSPENDED", recent_data["markers"])

        if last_low_glucose_marker is not None:
            data[SENSOR_KEY_LAST_LOW_GLUCOSE_SUSPENDED_MARKER] = last_low_glucose_marker["DATETIME"].replace(
                tzinfo=timezone
            )
            data[SENSOR_KEY_LAST_LOW_GLUCOSE_SUSPENDED_MARKER_ATTRS] = last_low_glucose_marker["ATTRS"]
        else:
            data[SENSOR_KEY_LAST_LOW_GLUCOSE_SUSPENDED_MARKER] = UNAVAILABLE

        # Binary Sensors

        data[BINARY_SENSOR_KEY_PUMP_COMM_STATE] = recent_data.get("pumpCommunicationState", UNAVAILABLE)
        data[BINARY_SENSOR_KEY_SENSOR_COMM_STATE] = recent_data.get("gstCommunicationState", UNAVAILABLE)
        data[BINARY_SENSOR_KEY_CONDUIT_IN_RANGE] = recent_data.get("conduitInRange", UNAVAILABLE)
        data[BINARY_SENSOR_KEY_CONDUIT_PUMP_IN_RANGE] = recent_data.get("conduitMedicalDeviceInRange", UNAVAILABLE)
        data[BINARY_SENSOR_KEY_CONDUIT_SENSOR_IN_RANGE] = recent_data.get("conduitSensorInRange", UNAVAILABLE)

        # Device info

        data[DEVICE_PUMP_SERIAL] = recent_data.get("conduitSerialNumber", UNAVAILABLE)
        data[DEVICE_PUMP_NAME] = recent_data.get("firstName", "Name") + " " + recent_data.get("lastName", "Unavailable")
        data[DEVICE_PUMP_MODEL] = recent_data.get("pumpModelNumber", UNAVAILABLE)
        data[DEVICE_PUMP_MANUFACTURER] = "Medtronic"

        data[SENSOR_KEY_APP_MODEL_TYPE] = recent_data.get("appModelType", UNAVAILABLE)

        device_info = recent_data.get("medicalDeviceInformation")
        if device_info:
            data[SENSOR_KEY_MEDICAL_DEVICE_MANUFACTURER] = device_info.get("manufacturer", UNAVAILABLE)
            data[SENSOR_KEY_MEDICAL_DEVICE_MODEL_NUMBER] = device_info.get("modelNumber", UNAVAILABLE)
            data[SENSOR_KEY_MEDICAL_DEVICE_HARDWARE_REVISION] = device_info.get("hardwareRevision", UNAVAILABLE)
            data[SENSOR_KEY_MEDICAL_DEVICE_FIRMWARE_REVISION] = device_info.get("firmwareRevision", UNAVAILABLE)
            data[SENSOR_KEY_MEDICAL_DEVICE_SYSTEM_ID] = device_info.get("systemId", UNAVAILABLE)

        _LOGGER.debug("_async_update_data: %s", sanitize_for_logging(data))

        # Import correctly-timestamped statistics
        if all_valid_sgs:
            self.hass.async_create_task(self._import_sg_statistics(all_valid_sgs, timezone))

        return data

    # ── Long-term statistics import ─────────────────────────────────

    async def _import_sg_statistics(self, valid_sgs: list[dict], tz: ZoneInfo) -> None:
        """Import SG readings as HA long-term statistics with correct timestamps.

        Creates correctly-timestamped 5-minute statistics entries so
        Statistics Graph cards show accurate historical data.
        """
        try:
            from homeassistant.components.recorder.statistics import (
                async_import_statistics,
            )
            from homeassistant.components.recorder.models import (
                StatisticData,
                StatisticMetaData,
            )
        except ImportError:
            _LOGGER.debug("Carelink: Recorder statistics API not available, skipping")
            return

        cgm_stats_mmol: list = []
        cgm_stats_mgdl: list = []

        for sg in valid_sgs:
            try:
                ts = convert_date_to_isodate(sg["timestamp"]).replace(tzinfo=tz)
                sg_val = sg["sg"]

                # Round down to 5-minute boundary for statistics period
                minute = (ts.minute // 5) * 5
                period_start = ts.replace(minute=minute, second=0, microsecond=0)

                mmol_val = round(float(sg_val) * 0.0555, 2)
                cgm_stats_mmol.append(
                    StatisticData(
                        start=period_start,
                        mean=mmol_val,
                        min=mmol_val,
                        max=mmol_val,
                        state=mmol_val,
                    )
                )
                cgm_stats_mgdl.append(
                    StatisticData(
                        start=period_start,
                        mean=float(sg_val),
                        min=float(sg_val),
                        max=float(sg_val),
                        state=float(sg_val),
                    )
                )
            except Exception as e:
                _LOGGER.warning(
                    "Carelink: Failed to create statistic from SG entry (timestamp=%s): %s",
                    sg.get("timestamp"),
                    e,
                )

        entity_prefix = f"sensor.{DOMAIN}"

        if cgm_stats_mmol:
            try:
                mmol_meta = StatisticMetaData(
                    has_mean=True,
                    has_sum=False,
                    name="Last glucose level mmol",
                    source="recorder",
                    statistic_id=f"{entity_prefix}_last_glucose_level_mmol",
                    unit_of_measurement="mmol/L",
                )
                async_import_statistics(self.hass, mmol_meta, cgm_stats_mmol)
                _LOGGER.debug(
                    "Carelink: Imported %d mmol statistics",
                    len(cgm_stats_mmol),
                )
            except Exception as e:
                _LOGGER.warning("Carelink: Failed to import mmol statistics: %s", e)

        if cgm_stats_mgdl:
            try:
                mgdl_meta = StatisticMetaData(
                    has_mean=True,
                    has_sum=False,
                    name="Last glucose level mg/dl",
                    source="recorder",
                    statistic_id=f"{entity_prefix}_last_glucose_level_mg_dl",
                    unit_of_measurement="mg/dL",
                )
                async_import_statistics(self.hass, mgdl_meta, cgm_stats_mgdl)
                _LOGGER.debug(
                    "Carelink: Imported %d mg/dl statistics",
                    len(cgm_stats_mgdl),
                )
            except Exception as e:
                _LOGGER.warning("Carelink: Failed to import mg/dl statistics: %s", e)


# ═══════════════════════════════════════════════════════════════════════════
# Tandem t:slim Coordinator
# ═══════════════════════════════════════════════════════════════════════════


class TandemCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Tandem Source API.

    Fetches pump events from the Tandem Source Reports API and replays
    ALL intermediate events (CGM, bolus, basal) through the coordinator
    so HA's recorder captures the full history between polls. Also imports
    correctly-timestamped long-term statistics for Statistics Graph cards.
    """

    def __init__(self, hass: HomeAssistant, entry, update_interval: timedelta):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

        self.entry_id = entry.entry_id
        self.configuration_url = "https://source.tandemdiabetes.com"
        self.uploader = None
        self.client = hass.data[DOMAIN][entry.entry_id][TANDEM_CLIENT]
        self.timezone = hass.config.time_zone
        self._prev_sg_mgdl: float | None = None

        # Historical data tracking
        self._last_max_date: str | None = None  # maxDateWithEvents from metadata
        self._last_event_seq: int = 0  # Last processed event sequence number

        if UPLOADER in hass.data[DOMAIN][entry.entry_id]:
            self.uploader = hass.data[DOMAIN][entry.entry_id][UPLOADER]

    async def _async_update_data(self):
        _LOGGER.debug("TandemCoordinator: Starting _async_update_data")
        data = {}

        try:
            await self.client.login()
        except TandemAuthError as err:
            raise UpdateFailed(f"Tandem authentication failed: {err}") from err
        except Exception as err:
            _LOGGER.debug("Unexpected error during Tandem login: %s", err, exc_info=True)
            raise UpdateFailed(f"Tandem login error: {err}") from err

        # ── Lightweight metadata check: skip heavy API call if no new data ──
        # The pumpevents endpoint is expensive. Check maxDateWithEvents first
        # and skip the full fetch if nothing has changed since last poll.
        try:
            metadata_list = await self.client.get_pump_event_metadata()
            metadata_entry = None
            if isinstance(metadata_list, list) and metadata_list:
                metadata_entry = metadata_list[0]
            elif isinstance(metadata_list, dict):
                metadata_entry = metadata_list

            max_date_str = metadata_entry.get("maxDateWithEvents") if metadata_entry else None
        except Exception as err:
            _LOGGER.debug("Tandem: Metadata check failed (%s), proceeding with full fetch", err)
            max_date_str = None
            metadata_entry = None

        if max_date_str and self._last_max_date and max_date_str == self._last_max_date and self.data:
            _LOGGER.debug(
                "[Tandem] Poll: no new pump data (maxDate=%s, serving %d cached keys)",
                max_date_str,
                len(self.data),
            )
            return self.data

        _LOGGER.info(
            "[Tandem] New pump data: maxDate %s → %s — fetching events",
            self._last_max_date or "(first poll)",
            max_date_str,
        )

        try:
            recent_data = await self.client.get_recent_data(
                pump_timezone=self.timezone,
                fallback_date=max_date_str,
            )
        except TandemApiError as err:
            raise UpdateFailed(f"Tandem API error: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Tandem data fetch error: {err}") from err

        if not isinstance(recent_data, dict):
            raise UpdateFailed(f"get_recent_data() returned {type(recent_data)}, expected dict")

        # Save maxDateWithEvents for next poll comparison
        if max_date_str:
            self._last_max_date = max_date_str

        _LOGGER.debug("Tandem before data parsing: %s", sanitize_for_logging(recent_data))

        # Log what data sources are available
        _LOGGER.info(
            "[Tandem] Fetch OK — metadata=%s  pumper=%s  pump_events=%s  therapy=%s  dashboard=%s",
            "OK" if recent_data.get("pump_metadata") else "MISSING",
            "OK" if recent_data.get("pumper_info") else "MISSING",
            "OK" if recent_data.get("pump_events") else "MISSING",
            "OK" if recent_data.get("therapy_timeline") else "MISSING",
            "OK" if recent_data.get("dashboard_summary") else "MISSING",
        )

        # ── Device info from pump metadata ───────────────────────────────
        metadata = recent_data.get("pump_metadata")

        if metadata:
            _LOGGER.debug("Tandem metadata keys: %s", list(metadata.keys()))
            _LOGGER.debug(
                "Tandem metadata values: serialNumber=%s, modelNumber=%s, softwareVersion=%s, partNumber=%s",
                metadata.get("serialNumber"),
                metadata.get("modelNumber"),
                metadata.get("softwareVersion"),
                metadata.get("partNumber"),
            )
            data[DEVICE_PUMP_SERIAL] = metadata.get("serialNumber", "unknown")
            data[DEVICE_PUMP_MODEL] = metadata.get("modelNumber", "t:slim X2")
            data[DEVICE_PUMP_NAME] = metadata.get("patientName", "Tandem Pump")
            data[TANDEM_SENSOR_KEY_PUMP_SERIAL_INFO] = metadata.get("serialNumber")
            data[TANDEM_SENSOR_KEY_PUMP_MODEL_INFO] = metadata.get("modelNumber")
            sw_version = metadata.get("softwareVersion")
            if not sw_version:
                _LOGGER.debug(
                    "Tandem softwareVersion not in metadata (keys: %s), trying partNumber as fallback",
                    list(metadata.keys()),
                )
                sw_version = metadata.get("partNumber")
            data[TANDEM_SENSOR_KEY_SOFTWARE_VERSION] = sw_version or UNAVAILABLE

            # Parse last upload timestamp
            # lastUpload is a dict {uploadId, lastUploadedAt, settings}, not a string
            last_upload_obj = metadata.get("lastUpload")
            last_uploaded_at = None
            if isinstance(last_upload_obj, dict):
                last_uploaded_at = last_upload_obj.get("lastUploadedAt")
            elif isinstance(last_upload_obj, str):
                # Backwards compat: some test fixtures use a bare date string
                last_uploaded_at = last_upload_obj

            if last_uploaded_at:
                upload_dt = parse_dotnet_date(last_uploaded_at)
                if upload_dt:
                    upload_aware = upload_dt.astimezone(ZoneInfo(self.timezone))
                    data[TANDEM_SENSOR_KEY_LAST_UPLOAD] = upload_aware
                    data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] = upload_aware
                else:
                    data[TANDEM_SENSOR_KEY_LAST_UPLOAD] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] = UNAVAILABLE
            else:
                data[TANDEM_SENSOR_KEY_LAST_UPLOAD] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] = UNAVAILABLE

            # Parse pump settings from lastUpload.settings
            self._parse_pump_settings(last_upload_obj, data)
        else:
            data[DEVICE_PUMP_SERIAL] = "unknown"
            data[DEVICE_PUMP_MODEL] = "t:slim X2"
            data[DEVICE_PUMP_NAME] = "Tandem Pump"
            data[TANDEM_SENSOR_KEY_PUMP_SERIAL_INFO] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_PUMP_MODEL_INFO] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_SOFTWARE_VERSION] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_UPLOAD] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] = UNAVAILABLE
            self._parse_pump_settings(None, data)

        data[DEVICE_PUMP_MANUFACTURER] = "Tandem Diabetes Care"

        # ── Therapy data (CGM, bolus, basal) ─────────────────────────────
        pump_events = recent_data.get("pump_events")
        timeline = recent_data.get("therapy_timeline")

        try:
            if pump_events:
                _LOGGER.debug("TandemCoordinator: Parsing pump events (Source Reports API)")
                self._parse_pump_events(pump_events, data)
            elif timeline:
                _LOGGER.debug("TandemCoordinator: Parsing therapy timeline (ControlIQ API)")
                self._parse_therapy_timeline(timeline, data)
            else:
                _LOGGER.debug("TandemCoordinator: No therapy data available")
                self._parse_therapy_timeline(None, data)  # Set all to UNAVAILABLE
        except Exception as e:
            _LOGGER.error("TandemCoordinator: Error parsing therapy data: %s", e, exc_info=True)

        # ── Dashboard summary (fallback only) ──────────────────────────
        # When pump_events are available, _compute_cgm_summary() inside
        # _parse_pump_events() computes avg glucose, TIR, CGM usage locally.
        # Only fall back to the dashboard_summary API if no pump_events.
        if not pump_events:
            summary = recent_data.get("dashboard_summary")
            try:
                self._parse_dashboard_summary(summary, data)
            except Exception as e:
                _LOGGER.error("TandemCoordinator: Error parsing dashboard summary: %s", e, exc_info=True)

        # Diagnostic: show CGM reading, its age, and whether staleness would have fired
        cgm_mgdl = data.get("tandem_last_sg_mgdl")
        cgm_ts = data.get("tandem_last_sg_timestamp")
        try:
            if cgm_ts and hasattr(cgm_ts, "astimezone"):
                age_secs = (datetime.now(timezone.utc) - cgm_ts.astimezone(timezone.utc)).total_seconds()
                age_str = f"{int(age_secs / 60)}min"
            else:
                age_str = "N/A"
        except Exception:
            age_str = "?"
        _LOGGER.info(
            "[Tandem] Parse done: %d keys | CGM=%s mg/dL @ %s (age=%s) | stale_check=%s",
            len(data),
            cgm_mgdl if cgm_mgdl is not None else "N/A",
            cgm_ts.strftime("%H:%M:%S %Z") if cgm_ts and hasattr(cgm_ts, "strftime") else "N/A",
            age_str,
            is_data_stale(data),
        )

        # ── Import long-term statistics with correct timestamps ──────────
        if pump_events:
            self.hass.async_create_task(self._import_statistics(pump_events))

        return data

    def _parse_therapy_timeline(self, timeline: dict | None, data: dict) -> None:
        """Parse therapy timeline data into sensor values."""
        # Keys only populated by _parse_pump_events — always default to UNAVAILABLE
        # when falling back to this path so sensors show unavailable, not unknown.
        data[TANDEM_SENSOR_KEY_LAST_CARBS_TIMESTAMP] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_CHANGE] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_SITE_CHANGE] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_TUBING_CHANGE] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_CGM_STATUS] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_BATTERY_PERCENT] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_BATTERY_VOLTAGE] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_BATTERY_REMAINING_MAH] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_CHARGING_STATUS] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_ALERT] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_LAST_ALARM] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] = UNAVAILABLE
        data[TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE] = UNAVAILABLE

        if not timeline:
            data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {}
            data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE
            return

        # ── CGM readings ─────────────────────────────────────────────
        try:
            cgm_entries = timeline.get("cgm", [])
            if cgm_entries:
                # Find the most recent CGM reading
                latest_reading = None
                latest_dt = None
                for entry in cgm_entries:
                    readings = entry.get("Readings", [])
                    entry_dt = parse_dotnet_date(entry.get("EventDateTime"))
                    for reading in readings:
                        val = reading.get("Value")
                        rtype = reading.get("Type", "")
                        if val and val > 0 and rtype == "EGV":
                            if latest_dt is None or (entry_dt and entry_dt > latest_dt):
                                latest_reading = val
                                latest_dt = entry_dt

                if latest_reading is not None:
                    sg_mgdl = float(latest_reading)
                    data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = int(sg_mgdl)
                    data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = round(sg_mgdl * 0.0555, 2)

                    if latest_dt:
                        data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = latest_dt.astimezone(ZoneInfo(self.timezone))

                    # Calculate delta from previous reading
                    if self._prev_sg_mgdl is not None:
                        data[TANDEM_SENSOR_KEY_SG_DELTA] = sg_mgdl - self._prev_sg_mgdl
                    else:
                        data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
                    self._prev_sg_mgdl = sg_mgdl
                else:
                    data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
            else:
                data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
        except Exception as e:
            _LOGGER.warning("Error parsing CGM data: %s", e)
            data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE

        # ── Bolus events ─────────────────────────────────────────────
        try:
            bolus_entries = timeline.get("bolus", [])
            if bolus_entries:
                # Sort by completion time, most recent first
                sorted_boluses = sorted(
                    bolus_entries,
                    key=lambda b: (
                        parse_dotnet_date(b.get("CompletionDateTime") or b.get("RequestDateTime", 0)) or datetime.min
                    ),
                    reverse=True,
                )

                last_bolus = sorted_boluses[0]
                insulin = last_bolus.get("InsulinDelivered", 0)
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = round(float(insulin), 2) if insulin else UNAVAILABLE

                bolus_dt = parse_dotnet_date(last_bolus.get("CompletionDateTime") or last_bolus.get("RequestDateTime"))
                if bolus_dt:
                    data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = bolus_dt.astimezone(ZoneInfo(self.timezone))
                else:
                    data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = UNAVAILABLE

                # Extra attributes
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {
                    "description": last_bolus.get("Description", ""),
                    "requested_insulin": last_bolus.get("RequestedInsulin"),
                    "carbs": last_bolus.get("CarbSize"),
                    "bg": last_bolus.get("BG"),
                    "iob": last_bolus.get("IOB"),
                    "completion_status": last_bolus.get("CompletionStatusID", ""),
                }

                # IOB from the last bolus entry
                iob = last_bolus.get("IOB")
                if iob is not None:
                    data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = round(float(iob), 2)
                else:
                    data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE

                # Find last meal bolus (with carbs)
                meal_bolus = None
                for b in sorted_boluses:
                    carbs = b.get("CarbSize")
                    if carbs and float(carbs) > 0:
                        meal_bolus = b
                        break

                if meal_bolus:
                    meal_insulin = meal_bolus.get("InsulinDelivered", 0)
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = (
                        round(float(meal_insulin), 2) if meal_insulin else UNAVAILABLE
                    )
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {
                        "carbs": meal_bolus.get("CarbSize"),
                        "bg": meal_bolus.get("BG"),
                        "description": meal_bolus.get("Description", ""),
                    }
                else:
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}
            else:
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {}
                data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}
        except Exception as e:
            _LOGGER.warning("Error parsing bolus data: %s", e)
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {}
            data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}

        # ── Basal events ─────────────────────────────────────────────
        try:
            basal_entries = timeline.get("basal", [])
            if basal_entries:
                sorted_basals = sorted(
                    basal_entries,
                    key=lambda b: parse_dotnet_date(b.get("EventDateTime", 0)) or datetime.min,
                    reverse=True,
                )
                last_basal = sorted_basals[0]
                rate = last_basal.get("BasalRate")
                if rate is not None:
                    data[TANDEM_SENSOR_KEY_BASAL_RATE] = round(float(rate), 3)
                else:
                    data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE

                # Determine Control-IQ status from basal type
                basal_type = last_basal.get("Type", "")
                if basal_type:
                    data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = basal_type
                else:
                    data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE
            else:
                data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE
        except Exception as e:
            _LOGGER.warning("Error parsing basal data: %s", e)
            data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE

    def _parse_pump_events(self, pump_events: list[dict], data: dict) -> None:
        """Parse decoded pump events into sensor values.

        Events are pre-decoded from binary format by decode_pump_events().
        Each event dict has: event_id, event_name, timestamp (datetime),
        and event-specific fields (glucose_mgdl, insulin_delivered, etc.).

        IMPORTANT: Sensor values are ALWAYS populated from the full event
        set (latest of each type), regardless of deduplication. The sequence
        dedup only controls which events get imported as long-term statistics.
        """
        if not pump_events:
            _LOGGER.debug("No pump_events data, setting all to UNAVAILABLE")
            self._parse_therapy_timeline(None, data)
            return

        _LOGGER.debug("Tandem: Parsing %d decoded pump events", len(pump_events))

        # Categorise ALL events by type — sensor values always use full set
        cgm_readings: list[dict] = []
        bolus_completed: list[dict] = []
        bolex_completed: list[dict] = []
        bolus_delivery: list[dict] = []
        basal_rate_changes: list[dict] = []
        basal_delivery: list[dict] = []
        suspend_resume: list[dict] = []
        bg_readings: list[dict] = []
        cartridge_fills: list[dict] = []
        carbs_entered: list[dict] = []
        cannula_fills: list[dict] = []
        tubing_fills: list[dict] = []
        user_mode_changes: list[dict] = []
        pcm_changes: list[dict] = []
        daily_basal_events: list[dict] = []
        shelf_mode_events: list[dict] = []
        usb_events: list[dict] = []
        alert_events: list[dict] = []
        alarm_events: list[dict] = []
        daily_status_events: list[dict] = []

        for evt in pump_events:
            eid = evt.get("event_id")
            if eid in (EVT_CGM_DATA_GXB, EVT_CGM_DATA_G7, EVT_CGM_DATA_FSL2):
                cgm_readings.append(evt)
            elif eid == EVT_BOLUS_COMPLETED:
                bolus_completed.append(evt)
            elif eid == EVT_BOLEX_COMPLETED:
                bolex_completed.append(evt)
            elif eid == EVT_BOLUS_DELIVERY:
                bolus_delivery.append(evt)
            elif eid == EVT_BASAL_RATE_CHANGE:
                basal_rate_changes.append(evt)
            elif eid == EVT_BASAL_DELIVERY:
                basal_delivery.append(evt)
            elif eid in (EVT_PUMPING_SUSPENDED, EVT_PUMPING_RESUMED):
                suspend_resume.append(evt)
            elif eid == EVT_BG_READING_TAKEN:
                bg_readings.append(evt)
            elif eid == EVT_CARTRIDGE_FILLED:
                cartridge_fills.append(evt)
            elif eid == EVT_CARBS_ENTERED:
                carbs_entered.append(evt)
            elif eid == EVT_CANNULA_FILLED:
                cannula_fills.append(evt)
            elif eid == EVT_TUBING_FILLED:
                tubing_fills.append(evt)
            elif eid == EVT_AA_USER_MODE_CHANGE:
                user_mode_changes.append(evt)
            elif eid == EVT_AA_PCM_CHANGE:
                pcm_changes.append(evt)
            elif eid == EVT_DAILY_BASAL:
                daily_basal_events.append(evt)
            elif eid == EVT_SHELF_MODE:
                shelf_mode_events.append(evt)
            elif eid in (EVT_USB_CONNECTED, EVT_USB_DISCONNECTED):
                usb_events.append(evt)
            elif eid in (EVT_ALERT_ACTIVATED, EVT_ALERT_CLEARED):
                alert_events.append(evt)
            elif eid in (EVT_ALARM_ACTIVATED, EVT_MALFUNCTION_ACTIVATED, EVT_ALARM_CLEARED):
                alarm_events.append(evt)
            elif eid == EVT_AA_DAILY_STATUS:
                daily_status_events.append(evt)

        _LOGGER.debug(
            "Tandem: Events - CGM: %d, BolusCompleted: %d, BolexCompleted: %d, "
            "BolusDelivery: %d, BasalChange: %d, BasalDelivery: %d, "
            "Suspend/Resume: %d, BG: %d, Cartridge: %d, Carbs: %d, "
            "Cannula: %d, Tubing: %d, UserMode: %d, PCM: %d, "
            "DailyBasal: %d, ShelfMode: %d, USB: %d, "
            "Alert: %d, Alarm: %d, DailyStatus: %d",
            len(cgm_readings),
            len(bolus_completed),
            len(bolex_completed),
            len(bolus_delivery),
            len(basal_rate_changes),
            len(basal_delivery),
            len(suspend_resume),
            len(bg_readings),
            len(cartridge_fills),
            len(carbs_entered),
            len(cannula_fills),
            len(tubing_fills),
            len(user_mode_changes),
            len(pcm_changes),
            len(daily_basal_events),
            len(shelf_mode_events),
            len(usb_events),
            len(alert_events),
            len(alarm_events),
            len(daily_status_events),
        )

        # Update the last-seen sequence number for statistics deduplication
        max_seq = max((evt.get("seq", 0) for evt in pump_events), default=0)
        if max_seq > self._last_event_seq:
            self._last_event_seq = max_seq
            _LOGGER.debug("Tandem: Updated last_event_seq to %d", max_seq)

        # Sort all event lists by timestamp
        cgm_readings.sort(key=lambda e: e["timestamp"])
        bolus_completed.sort(key=lambda e: e["timestamp"])
        bolex_completed.sort(key=lambda e: e["timestamp"])
        bolus_delivery.sort(key=lambda e: e["timestamp"])
        basal_rate_changes.sort(key=lambda e: e["timestamp"])
        basal_delivery.sort(key=lambda e: e["timestamp"])
        suspend_resume.sort(key=lambda e: e["timestamp"])
        bg_readings.sort(key=lambda e: e["timestamp"])
        cartridge_fills.sort(key=lambda e: e["timestamp"])
        carbs_entered.sort(key=lambda e: e["timestamp"])
        cannula_fills.sort(key=lambda e: e["timestamp"])
        tubing_fills.sort(key=lambda e: e["timestamp"])
        user_mode_changes.sort(key=lambda e: e["timestamp"])
        pcm_changes.sort(key=lambda e: e["timestamp"])
        daily_basal_events.sort(key=lambda e: e["timestamp"])
        shelf_mode_events.sort(key=lambda e: e["timestamp"])
        usb_events.sort(key=lambda e: e["timestamp"])
        alert_events.sort(key=lambda e: e["timestamp"])
        alarm_events.sort(key=lambda e: e["timestamp"])
        daily_status_events.sort(key=lambda e: e["timestamp"])

        # ── Populate current sensor values from latest events ────────

        # ── CGM readings ─────────────────────────────────────────────
        try:
            if cgm_readings:
                latest = cgm_readings[-1]
                sg_mgdl = latest.get("glucose_mgdl", 0)

                if sg_mgdl and sg_mgdl > 0:
                    data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = int(sg_mgdl)
                    data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = round(sg_mgdl * 0.0555, 2)
                    data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = latest["timestamp"].replace(
                        tzinfo=ZoneInfo(self.timezone)
                    )

                    if self._prev_sg_mgdl is not None:
                        data[TANDEM_SENSOR_KEY_SG_DELTA] = float(sg_mgdl) - self._prev_sg_mgdl
                    else:
                        data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
                    self._prev_sg_mgdl = float(sg_mgdl)

                    roc = latest.get("rate_of_change")
                    data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] = round(roc, 1) if roc is not None else UNAVAILABLE
                    cgm_status_code = latest.get("status")
                    cgm_status = CGM_STATUS_MAP.get(cgm_status_code)
                    if cgm_status is None and cgm_status_code is not None:
                        _LOGGER.debug("Tandem: Unknown CGM status code %r — update CGM_STATUS_MAP", cgm_status_code)
                    data[TANDEM_SENSOR_KEY_CGM_STATUS] = cgm_status if cgm_status is not None else UNAVAILABLE
                else:
                    _LOGGER.warning(
                        "Tandem: CGM event has zero/missing glucose: %s",
                        latest,
                    )
                    data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_CGM_STATUS] = UNAVAILABLE
            else:
                data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_CGM_STATUS] = UNAVAILABLE
        except Exception as e:
            _LOGGER.warning("Error parsing CGM: %s", e, exc_info=True)
            data[TANDEM_SENSOR_KEY_LASTSG_MMOL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LASTSG_MGDL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_SG_DELTA] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CGM_STATUS] = UNAVAILABLE

        # ── Store recent readings history as attributes ───────────────
        # Custom Lovelace cards (e.g. ApexCharts) can use these for
        # correctly-timestamped graphs. Limited to most recent entries
        # to stay within HA's 16KB state attribute size limit.
        tz = ZoneInfo(self.timezone)
        _MAX_CGM_HISTORY = 24  # ~2 hours of 5-min readings
        _MAX_BOLUS_HISTORY = 10
        _MAX_BASAL_HISTORY = 10

        # CGM readings history (for glucose graph cards)
        recent_cgm = cgm_readings[-_MAX_CGM_HISTORY:]
        data[f"{TANDEM_SENSOR_KEY_LASTSG_MGDL}_attributes"] = {
            "readings": [
                {
                    "t": r["timestamp"].replace(tzinfo=tz).isoformat(),
                    "v": r.get("glucose_mgdl"),
                }
                for r in recent_cgm
                if r.get("glucose_mgdl")
            ],
        }

        # IOB history (from bolus completed events)
        recent_iob = bolus_completed[-_MAX_BOLUS_HISTORY:]
        data[f"{TANDEM_SENSOR_KEY_ACTIVE_INSULIN}_attributes"] = {
            "readings": [
                {
                    "t": b["timestamp"].replace(tzinfo=tz).isoformat(),
                    "v": round(float(b["iob"]), 2),
                }
                for b in recent_iob
                if b.get("iob") is not None
            ],
        }

        # Basal rate history
        all_basal_sorted = sorted(
            basal_rate_changes + basal_delivery,
            key=lambda e: e["timestamp"],
        )
        recent_basal = all_basal_sorted[-_MAX_BASAL_HISTORY:]
        data[f"{TANDEM_SENSOR_KEY_BASAL_RATE}_attributes"] = {
            "readings": [
                {
                    "t": b["timestamp"].replace(tzinfo=tz).isoformat(),
                    "v": round(float(b["commanded_rate"]), 3),
                }
                for b in recent_basal
                if b.get("commanded_rate") is not None
            ],
        }

        # ── Bolus events ─────────────────────────────────────────────
        try:
            # Prefer BOLUS_COMPLETED (has IOB), fall back to BOLUS_DELIVERY
            latest_bolus_list = bolus_completed or bolus_delivery
            if latest_bolus_list:
                last_bolus = latest_bolus_list[-1]

                insulin = last_bolus.get("insulin_delivered", 0)
                if insulin:
                    data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = round(float(insulin), 2)
                else:
                    data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = UNAVAILABLE

                data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = last_bolus["timestamp"].replace(
                    tzinfo=ZoneInfo(self.timezone)
                )

                data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {
                    "event_type": last_bolus.get("event_name", ""),
                    "insulin_requested": last_bolus.get("insulin_requested"),
                    "bolus_id": last_bolus.get("bolus_id"),
                    "completion_status": last_bolus.get("completion_status"),
                }

                # IOB from BOLUS_COMPLETED event
                iob = last_bolus.get("iob")
                if iob is not None:
                    data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = round(float(iob), 2)
                else:
                    # Try to find IOB from any completed bolus
                    for b in reversed(bolus_completed):
                        if b.get("iob") is not None:
                            data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = round(float(b["iob"]), 2)
                            break
                    else:
                        data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE

                # Meal bolus detection (bolus with carb flag)
                # In binary format, bolus_type bitmask bit 4 = Carb bolus
                meal_bolus = None
                for b in reversed(bolus_delivery):
                    btype = b.get("bolus_type", 0)
                    if btype & 0x10:  # bit 4 = Carb
                        meal_bolus = b
                        break

                if meal_bolus:
                    meal_ins = meal_bolus.get("insulin_delivered", 0)
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = round(float(meal_ins), 2) if meal_ins else UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {
                        "bolus_type": meal_bolus.get("bolus_type"),
                        "bolus_id": meal_bolus.get("bolus_id"),
                    }
                else:
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}
            else:
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {}
                data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}
        except Exception as e:
            _LOGGER.warning("Error parsing bolus: %s", e, exc_info=True)
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS] = {}
            data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS] = {}

        # ── Basal events ─────────────────────────────────────────────
        try:
            # Prefer BASAL_RATE_CHANGE (has float rate), fall back to
            # BASAL_DELIVERY (has milliunits rate)
            latest_basal_list = basal_rate_changes or basal_delivery
            if latest_basal_list:
                last_basal = latest_basal_list[-1]

                rate = last_basal.get("commanded_rate")
                if rate is not None:
                    data[TANDEM_SENSOR_KEY_BASAL_RATE] = round(float(rate), 3)
                else:
                    data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE

                # Control-IQ status from basal change type or source
                change_type = last_basal.get("change_type")
                commanded_source = last_basal.get("commanded_source")
                if commanded_source is not None:
                    source_map = {
                        0: "Suspended",
                        1: "Profile",
                        2: "Temp Rate",
                        3: "Algorithm",
                        4: "Temp + Algorithm",
                    }
                    data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = source_map.get(
                        commanded_source, f"Source_{commanded_source}"
                    )
                elif change_type is not None:
                    _LOGGER.debug(
                        "Tandem: BasalRateChange change_type=%d has no commanded_source — "
                        "raw value used as Control-IQ status (add to source_map if known)",
                        change_type,
                    )
                    data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = str(change_type)
                else:
                    data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE
            else:
                data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE
        except Exception as e:
            _LOGGER.warning("Error parsing basal: %s", e, exc_info=True)
            data[TANDEM_SENSOR_KEY_BASAL_RATE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] = UNAVAILABLE

        # ── Pump suspend/resume state ──────────────────────────────────
        try:
            if suspend_resume:
                last_sr = suspend_resume[-1]
                is_suspended = last_sr.get("event_id") == 11
                data[TANDEM_SENSOR_KEY_PUMP_SUSPENDED] = "Suspended" if is_suspended else "Active"
                suspend_reason = last_sr.get("suspend_reason") if is_suspended else None
                data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] = (
                    suspend_reason if suspend_reason is not None else UNAVAILABLE
                )
            else:
                data[TANDEM_SENSOR_KEY_PUMP_SUSPENDED] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] = UNAVAILABLE
        except Exception as e:
            _LOGGER.warning("Error parsing suspend/resume: %s", e, exc_info=True)
            data[TANDEM_SENSOR_KEY_PUMP_SUSPENDED] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] = UNAVAILABLE

        # ── Activity mode (sleep/exercise/eating soon) ─────────────────
        if user_mode_changes:
            last_mode = user_mode_changes[-1]
            data[TANDEM_SENSOR_KEY_ACTIVITY_MODE] = last_mode.get("current_mode", UNAVAILABLE)
        else:
            data[TANDEM_SENSOR_KEY_ACTIVITY_MODE] = UNAVAILABLE

        # ── Control-IQ mode (open loop / closed loop) ──────────────────
        if pcm_changes:
            last_pcm = pcm_changes[-1]
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_MODE] = last_pcm.get("current_pcm", UNAVAILABLE)
        else:
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_MODE] = UNAVAILABLE

        # ── BG readings ────────────────────────────────────────────────
        if bg_readings:
            last_bg = bg_readings[-1]
            data[TANDEM_SENSOR_KEY_LAST_BG_READING] = last_bg.get("bg_mgdl", UNAVAILABLE)
        else:
            data[TANDEM_SENSOR_KEY_LAST_BG_READING] = UNAVAILABLE

        # ── Carb entries ───────────────────────────────────────────────
        tz = ZoneInfo(self.timezone)
        if carbs_entered:
            last_carb = carbs_entered[-1]
            data[TANDEM_SENSOR_KEY_LAST_CARBS] = last_carb.get("carbs", UNAVAILABLE)
            data[TANDEM_SENSOR_KEY_LAST_CARBS_TIMESTAMP] = last_carb["timestamp"].replace(tzinfo=tz)
        else:
            data[TANDEM_SENSOR_KEY_LAST_CARBS] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_CARBS_TIMESTAMP] = UNAVAILABLE

        # ── Cartridge change ───────────────────────────────────────────
        if cartridge_fills:
            last_cart = cartridge_fills[-1]
            data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_CHANGE] = last_cart["timestamp"].replace(tzinfo=tz)
            fill_volume = last_cart.get("insulin_volume")
            # Tandem API often returns 0.0 for insulin_volume — treat as unknown.
            # Users can set the fill volume via the Cartridge Fill Volume number
            # entity, which is used to estimate remaining insulin.
            if fill_volume and fill_volume > 0:
                data[TANDEM_SENSOR_KEY_CARTRIDGE_INSULIN] = fill_volume
                data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL] = round(fill_volume, 1)
            else:
                _LOGGER.debug(
                    "Cartridge fill volume is %s — Tandem API limitation. "
                    "Set the 'Cartridge fill volume' number entity to track remaining insulin.",
                    fill_volume,
                )
                data[TANDEM_SENSOR_KEY_CARTRIDGE_INSULIN] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL] = UNAVAILABLE
        else:
            data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_CHANGE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CARTRIDGE_INSULIN] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL] = UNAVAILABLE

        # ── Site change ───────────────────────────────────────────────
        # The Tandem Source API does not return CANNULA_FILLED (event 61)
        # for cartridge/site changes. The web UI shows "Cartridge/Site Change"
        # as a single combined event. We derive site change from the cartridge
        # fill timestamp, falling back to cannula fill if present.
        if cannula_fills:
            data[TANDEM_SENSOR_KEY_LAST_SITE_CHANGE] = cannula_fills[-1]["timestamp"].replace(tzinfo=tz)
        elif cartridge_fills:
            data[TANDEM_SENSOR_KEY_LAST_SITE_CHANGE] = cartridge_fills[-1]["timestamp"].replace(tzinfo=tz)
        else:
            data[TANDEM_SENSOR_KEY_LAST_SITE_CHANGE] = UNAVAILABLE

        # ── Tubing change ──────────────────────────────────────────────
        if tubing_fills:
            data[TANDEM_SENSOR_KEY_LAST_TUBING_CHANGE] = tubing_fills[-1]["timestamp"].replace(tzinfo=tz)
        else:
            data[TANDEM_SENSOR_KEY_LAST_TUBING_CHANGE] = UNAVAILABLE

        # ── Battery monitoring (Phase 1) ─────────────────────────────────
        # Battery data comes from two event types:
        # - Event 81 (DailyBasal): battery % only (emitted daily)
        # - Event 53 (ShelfMode): battery %, voltage, mAh, current (periodic)
        # We prefer the most recent of either source for %,
        # and only ShelfMode provides voltage and mAh.
        try:
            battery_pct = UNAVAILABLE
            battery_mv = UNAVAILABLE
            battery_mah = UNAVAILABLE

            # DailyBasal provides battery % (voltage only from ShelfMode)
            if daily_basal_events:
                latest_db = daily_basal_events[-1]
                battery_pct = latest_db.get("battery_percent", UNAVAILABLE)

            # ShelfMode provides voltage and mAh (always used when available)
            # and battery % (used if newer than DailyBasal)
            if shelf_mode_events:
                latest_sm = shelf_mode_events[-1]
                sm_pct = latest_sm.get("battery_percent", UNAVAILABLE)
                battery_mv = latest_sm.get("battery_voltage_mv", UNAVAILABLE)
                battery_mah = latest_sm.get("battery_remaining_mah", UNAVAILABLE)

                # Use ShelfMode % if no DailyBasal or if ShelfMode is newer
                if not daily_basal_events or latest_sm["timestamp"] > daily_basal_events[-1]["timestamp"]:
                    battery_pct = sm_pct

            data[TANDEM_SENSOR_KEY_BATTERY_PERCENT] = battery_pct
            data[TANDEM_SENSOR_KEY_BATTERY_VOLTAGE] = battery_mv
            data[TANDEM_SENSOR_KEY_BATTERY_REMAINING_MAH] = battery_mah

            # Charging status from USB connect/disconnect events
            if usb_events:
                latest_usb = usb_events[-1]
                if latest_usb.get("event_name") == "USBConnected":
                    data[TANDEM_SENSOR_KEY_CHARGING_STATUS] = "Charging"
                else:
                    data[TANDEM_SENSOR_KEY_CHARGING_STATUS] = "Not Charging"
            else:
                data[TANDEM_SENSOR_KEY_CHARGING_STATUS] = UNAVAILABLE
        except Exception as e:
            _LOGGER.warning("Error parsing battery data: %s", e, exc_info=True)
            data[TANDEM_SENSOR_KEY_BATTERY_PERCENT] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_BATTERY_VOLTAGE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_BATTERY_REMAINING_MAH] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CHARGING_STATUS] = UNAVAILABLE

        # ── Alerts & Alarms (Phase 2) ─────────────────────────────────
        try:
            self._parse_alert_alarm_events(alert_events, alarm_events, data)
        except Exception as e:
            _LOGGER.error(
                "Error parsing alert/alarm events (%d alert, %d alarm events): %s",
                len(alert_events),
                len(alarm_events),
                e,
                exc_info=True,
            )
            data[TANDEM_SENSOR_KEY_LAST_ALERT] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_ALARM] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] = UNAVAILABLE

        # ── CGM Sensor Type (Phase 3) ────────────────────────────────
        try:
            if daily_status_events:
                latest_status = daily_status_events[-1]
                sensor_type = latest_status.get("sensor_type", UNAVAILABLE)
                if sensor_type != UNAVAILABLE and sensor_type.startswith("Unknown"):
                    _LOGGER.info(
                        "Tandem: Unrecognised CGM sensor_type %r from %d daily_status event(s) — update sensor_type_map in tandem_api.py",
                        sensor_type,
                        len(daily_status_events),
                    )
                data[TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE] = sensor_type
            else:
                data[TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE] = UNAVAILABLE
        except (KeyError, TypeError, IndexError) as e:
            _LOGGER.error(
                "Tandem: Error parsing %d daily status event(s): %s",
                len(daily_status_events),
                e,
                exc_info=True,
            )
            data[TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE] = UNAVAILABLE

        # ── Computed summaries ─────────────────────────────────────────
        try:
            self._compute_cgm_summary(cgm_readings, data)
        except Exception as e:
            _LOGGER.warning("Error computing CGM summary: %s", e, exc_info=True)

        try:
            self._compute_insulin_summary(
                bolus_completed,
                bolex_completed,
                basal_delivery,
                basal_rate_changes,
                carbs_entered,
                data,
            )
        except Exception as e:
            _LOGGER.warning("Error computing insulin summary: %s", e, exc_info=True)

    def _parse_alert_alarm_events(
        self,
        alert_events: list[dict],
        alarm_events: list[dict],
        data: dict,
    ) -> None:
        """Parse alert and alarm events into sensor values.

        alert_events contains events 4 (AlertActivated) and 26 (AlertCleared).
        alarm_events contains events 5 (AlarmActivated), 6 (MalfunctionActivated),
        and 28 (AlarmCleared).

        Active count tracks all uncleared activations across both lists.
        """
        tz = ZoneInfo(self.timezone)

        # ── Alert sensors (events 4 / 26) ────────────────────────────
        # Track which alert IDs are currently active (activated but not cleared).
        # Events are pre-sorted by timestamp so we replay in order.
        active_alerts: dict[int, dict] = {}
        for evt in alert_events:
            if evt["event_name"] == "AlertActivated":
                active_alerts[evt["alert_id"]] = evt
            elif evt["event_name"] == "AlertCleared":
                active_alerts.pop(evt["alert_id"], None)

        last_activated_alert = next(
            (e for e in reversed(alert_events) if e["event_name"] == "AlertActivated"),
            None,
        )
        if last_activated_alert:
            aid = last_activated_alert["alert_id"]
            name = TANDEM_ALERT_MAP.get(aid, f"Alert {aid}")
            ts = last_activated_alert["timestamp"].replace(tzinfo=tz)
            # Last 10 activation events in order; the same alert_id may appear
            # multiple times if it fired and cleared repeatedly.
            recent = [
                {
                    "id": e["alert_id"],
                    "name": TANDEM_ALERT_MAP.get(e["alert_id"], f"Alert {e['alert_id']}"),
                    "timestamp": e["timestamp"].replace(tzinfo=tz).isoformat(),
                }
                for e in alert_events
                if e["event_name"] == "AlertActivated"
            ][-10:]
            data[TANDEM_SENSOR_KEY_LAST_ALERT] = name
            data[f"{TANDEM_SENSOR_KEY_LAST_ALERT}_attributes"] = {
                "alert_id": aid,
                "cleared": aid not in active_alerts,
                "timestamp": ts.isoformat(),
                "recent": recent,
            }
        else:
            data[TANDEM_SENSOR_KEY_LAST_ALERT] = UNAVAILABLE

        # ── Alarm sensors (events 5, 6 / 28) ─────────────────────────
        active_alarms: dict[int, dict] = {}
        for evt in alarm_events:
            if evt["event_name"] in ("AlarmActivated", "MalfunctionActivated"):
                active_alarms[evt["alert_id"]] = evt
            elif evt["event_name"] == "AlarmCleared":
                active_alarms.pop(evt["alert_id"], None)

        last_activated_alarm = next(
            (e for e in reversed(alarm_events) if e["event_name"] in ("AlarmActivated", "MalfunctionActivated")),
            None,
        )
        if last_activated_alarm:
            aid = last_activated_alarm["alert_id"]
            name = TANDEM_ALARM_MAP.get(aid, f"Alarm {aid}")
            ts = last_activated_alarm["timestamp"].replace(tzinfo=tz)
            recent = [
                {
                    "id": e["alert_id"],
                    "name": TANDEM_ALARM_MAP.get(e["alert_id"], f"Alarm {e['alert_id']}"),
                    "timestamp": e["timestamp"].replace(tzinfo=tz).isoformat(),
                }
                for e in alarm_events
                if e["event_name"] in ("AlarmActivated", "MalfunctionActivated")
            ][-10:]
            data[TANDEM_SENSOR_KEY_LAST_ALARM] = name
            data[f"{TANDEM_SENSOR_KEY_LAST_ALARM}_attributes"] = {
                "alert_id": aid,
                "cleared": aid not in active_alarms,
                "timestamp": ts.isoformat(),
                "recent": recent,
            }
        else:
            data[TANDEM_SENSOR_KEY_LAST_ALARM] = UNAVAILABLE

        # ── Active count (alerts + alarms combined) ───────────────────
        data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] = len(active_alerts) + len(active_alarms)

    def _parse_dashboard_summary(self, summary: dict | None, data: dict) -> None:
        """Parse dashboard summary into sensor values."""
        if not summary:
            data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] = UNAVAILABLE
            data[TANDEM_TIME_IN_RANGE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CGM_USAGE] = UNAVAILABLE
            return

        try:
            avg_reading = summary.get("averageReading")
            if avg_reading is not None:
                data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] = int(avg_reading)
                data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] = round(float(avg_reading) * 0.0555, 2)
            else:
                data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] = UNAVAILABLE

            # Time in range - calculate from CGM data percentages
            tir = summary.get("timeInRangePercent")
            if tir is not None:
                data[TANDEM_TIME_IN_RANGE] = round(float(tir), 1)
            else:
                data[TANDEM_TIME_IN_RANGE] = UNAVAILABLE

            # CGM usage
            cgm_inactive = summary.get("cgmInactivePercent")
            if cgm_inactive is not None:
                data[TANDEM_SENSOR_KEY_CGM_USAGE] = round(100.0 - float(cgm_inactive), 1)
            else:
                time_in_use = summary.get("timeInUsePercent")
                if time_in_use is not None:
                    data[TANDEM_SENSOR_KEY_CGM_USAGE] = round(float(time_in_use), 1)
                else:
                    data[TANDEM_SENSOR_KEY_CGM_USAGE] = UNAVAILABLE

        except Exception as e:
            _LOGGER.warning("Error parsing dashboard summary: %s", e)
            data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] = UNAVAILABLE
            data[TANDEM_TIME_IN_RANGE] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_CGM_USAGE] = UNAVAILABLE

    def _parse_pump_settings(self, last_upload_obj: dict | None, data: dict) -> None:
        """Extract pump settings from metadata.lastUpload.settings.

        The lastUpload field is a dict: {uploadId, lastUploadedAt, settings}.
        settings contains profiles, controlIQSettings, pumpSettings,
        alertsAndReminders, cgmSettings, etc.
        """
        _set_unavailable = [
            TANDEM_SENSOR_KEY_ACTIVE_PROFILE,
            TANDEM_SENSOR_KEY_CONTROL_IQ_ENABLED,
            TANDEM_SENSOR_KEY_CONTROL_IQ_WEIGHT,
            TANDEM_SENSOR_KEY_CONTROL_IQ_TDI,
            TANDEM_SENSOR_KEY_MAX_BOLUS,
            TANDEM_SENSOR_KEY_BASAL_LIMIT,
            TANDEM_SENSOR_KEY_CGM_HIGH_ALERT,
            TANDEM_SENSOR_KEY_CGM_LOW_ALERT,
            TANDEM_SENSOR_KEY_LOW_BG_THRESHOLD,
            TANDEM_SENSOR_KEY_HIGH_BG_THRESHOLD,
            TANDEM_SENSOR_KEY_LOW_INSULIN_ALERT,
        ]

        if not isinstance(last_upload_obj, dict):
            for key in _set_unavailable:
                data[key] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS] = {}
            return

        settings = last_upload_obj.get("settings")
        if not settings:
            for key in _set_unavailable:
                data[key] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS] = {}
            return

        try:
            # ── Active profile ──────────────────────────────────────────
            profiles = settings.get("profiles") or {}
            active_idp = profiles.get("activeIdp")
            profile_list = profiles.get("profile") or []

            active_profile = None
            for prof in profile_list:
                if prof.get("idp") == active_idp:
                    active_profile = prof
                    break

            if active_profile:
                data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE] = active_profile.get("name", "Unknown")

                # Build profile attributes: schedule segments, insulin duration
                segments = active_profile.get("tDependentSegs") or []
                schedule = []
                for seg in segments:
                    rate = seg.get("basalRate", 0)
                    if rate == 0 and seg.get("startTime", 0) == 0 and not schedule:
                        # Skip empty placeholder segments, but keep the first
                        # one if it has a real rate
                        continue
                    if rate == 0 and seg.get("isf", 0) == 0:
                        # Empty trailing slot
                        continue
                    start_mins = seg.get("startTime", 0)
                    hours, mins = divmod(start_mins, 60)
                    schedule.append(
                        {
                            "time": f"{hours:02d}:{mins:02d}",
                            "basal_rate": round(rate / 1000, 3),
                            "isf_mgdl": seg.get("isf"),
                            "carb_ratio": round(seg.get("carbRatio", 0) / 1000, 1),
                            "target_bg_mgdl": seg.get("targetBg"),
                        }
                    )

                insulin_dur_mins = active_profile.get("insulinDuration", 0)
                attrs = {
                    "profile_name": active_profile.get("name"),
                    "insulin_duration_hours": round(insulin_dur_mins / 60, 1) if insulin_dur_mins else None,
                    "carb_entry_enabled": bool(active_profile.get("carbEntry")),
                    "schedule": schedule,
                }
                data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS] = attrs
            else:
                data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS] = {}

            # ── Control-IQ settings ─────────────────────────────────────
            ciq = settings.get("controlIQSettings") or {}
            closed_loop = ciq.get("ClosedLoop")
            if closed_loop is not None:
                data[TANDEM_SENSOR_KEY_CONTROL_IQ_ENABLED] = "On" if closed_loop else "Off"
            else:
                data[TANDEM_SENSOR_KEY_CONTROL_IQ_ENABLED] = UNAVAILABLE

            weight = ciq.get("Weight")
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_WEIGHT] = weight if weight is not None else UNAVAILABLE

            tdi = ciq.get("TotalDailyInsulin")
            data[TANDEM_SENSOR_KEY_CONTROL_IQ_TDI] = tdi if tdi is not None else UNAVAILABLE

            # ── Pump limits ─────────────────────────────────────────────
            pump_settings = settings.get("pumpSettings") or {}
            max_bolus_raw = pump_settings.get("maxBolus")
            if max_bolus_raw is not None:
                data[TANDEM_SENSOR_KEY_MAX_BOLUS] = round(max_bolus_raw / 1000, 1)
            else:
                data[TANDEM_SENSOR_KEY_MAX_BOLUS] = UNAVAILABLE

            basal_limit_raw = pump_settings.get("basalLimit")
            if basal_limit_raw is not None:
                data[TANDEM_SENSOR_KEY_BASAL_LIMIT] = round(basal_limit_raw / 1000, 1)
            else:
                data[TANDEM_SENSOR_KEY_BASAL_LIMIT] = UNAVAILABLE

            # ── CGM alert thresholds ────────────────────────────────────
            cgm_settings = settings.get("cgmSettings") or {}
            high_alert = cgm_settings.get("highGlucoseAlert") or {}
            low_alert = cgm_settings.get("lowGlucoseAlert") or {}

            high_mgdl = high_alert.get("mgPerDl")
            data[TANDEM_SENSOR_KEY_CGM_HIGH_ALERT] = high_mgdl if high_mgdl is not None else UNAVAILABLE

            low_mgdl = low_alert.get("mgPerDl")
            data[TANDEM_SENSOR_KEY_CGM_LOW_ALERT] = low_mgdl if low_mgdl is not None else UNAVAILABLE

            # ── Alert thresholds ────────────────────────────────────────
            alerts = settings.get("alertsAndReminders") or {}
            low_bg = alerts.get("lowBgThreshold")
            data[TANDEM_SENSOR_KEY_LOW_BG_THRESHOLD] = low_bg if low_bg is not None else UNAVAILABLE

            high_bg = alerts.get("highBgThreshold")
            data[TANDEM_SENSOR_KEY_HIGH_BG_THRESHOLD] = high_bg if high_bg is not None else UNAVAILABLE

            low_insulin = alerts.get("lowInsulinThreshold")
            data[TANDEM_SENSOR_KEY_LOW_INSULIN_ALERT] = low_insulin if low_insulin is not None else UNAVAILABLE

        except Exception as e:
            _LOGGER.warning("Error parsing pump settings: %s", e, exc_info=True)
            for key in _set_unavailable:
                if key not in data:
                    data[key] = UNAVAILABLE
            if TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS not in data:
                data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS] = {}

    def _compute_cgm_summary(self, cgm_readings: list[dict], data: dict) -> None:
        """Compute CGM summary statistics from raw glucose readings.

        Replaces the broken dashboard_summary API by computing locally:
        avg glucose, SD, CV, GMI, time in/below/above range, CGM usage.
        """
        _unavailable_keys = (
            TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL,
            TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL,
            TANDEM_TIME_IN_RANGE,
            TANDEM_SENSOR_KEY_CGM_USAGE,
            TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV,
            TANDEM_SENSOR_KEY_GLUCOSE_CV,
            TANDEM_SENSOR_KEY_GMI,
            TANDEM_SENSOR_KEY_TIME_BELOW_RANGE,
            TANDEM_SENSOR_KEY_TIME_ABOVE_RANGE,
        )

        if not cgm_readings:
            for key in _unavailable_keys:
                data[key] = UNAVAILABLE
            return

        # Extract valid glucose values
        values = [r["glucose_mgdl"] for r in cgm_readings if r.get("glucose_mgdl") and r["glucose_mgdl"] > 0]

        if not values:
            for key in _unavailable_keys:
                data[key] = UNAVAILABLE
            return

        n = len(values)
        mean = sum(values) / n

        # Average glucose
        data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] = round(mean)
        data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] = round(mean * 0.0555, 1)

        # Standard deviation
        if n >= 2:
            variance = sum((v - mean) ** 2 for v in values) / (n - 1)
            sd = math.sqrt(variance)
            data[TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV] = round(sd, 1)
            data[TANDEM_SENSOR_KEY_GLUCOSE_CV] = round((sd / mean) * 100, 1) if mean > 0 else UNAVAILABLE
        else:
            data[TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_GLUCOSE_CV] = UNAVAILABLE

        # GMI (Glucose Management Indicator)
        data[TANDEM_SENSOR_KEY_GMI] = round(3.31 + (0.02392 * mean), 1)

        # Time in range (70-180 mg/dL)
        in_range = sum(1 for v in values if 70 <= v <= 180)
        below = sum(1 for v in values if v < 70)
        above = sum(1 for v in values if v > 180)
        data[TANDEM_TIME_IN_RANGE] = round((in_range / n) * 100, 1)
        data[TANDEM_SENSOR_KEY_TIME_BELOW_RANGE] = round((below / n) * 100, 1)
        data[TANDEM_SENSOR_KEY_TIME_ABOVE_RANGE] = round((above / n) * 100, 1)

        # CGM usage (readings per day: 288 at 5-min intervals)
        # Use reading count vs expected for the fetch window
        data[TANDEM_SENSOR_KEY_CGM_USAGE] = round(min((n / 288) * 100, 100.0), 1)

        _LOGGER.debug(
            "CGM summary: avg=%d mg/dL, SD=%.1f, CV=%.1f%%, GMI=%.1f%%, "
            "TIR=%.1f%%, below=%.1f%%, above=%.1f%%, usage=%.1f%% (%d readings)",
            mean,
            data.get(TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV, 0) or 0,
            data.get(TANDEM_SENSOR_KEY_GLUCOSE_CV, 0) or 0,
            data.get(TANDEM_SENSOR_KEY_GMI, 0) or 0,
            data[TANDEM_TIME_IN_RANGE],
            data[TANDEM_SENSOR_KEY_TIME_BELOW_RANGE],
            data[TANDEM_SENSOR_KEY_TIME_ABOVE_RANGE],
            data[TANDEM_SENSOR_KEY_CGM_USAGE],
            n,
        )

    def _compute_insulin_summary(
        self,
        bolus_completed: list[dict],
        bolex_completed: list[dict],
        basal_delivery: list[dict],
        basal_rate_changes: list[dict],
        carbs_entered: list[dict],
        data: dict,
    ) -> None:
        """Compute daily insulin summary from bolus and basal events.

        Only events from "today" (in pump timezone) are included so that
        the totals reflect a single calendar day, not the full 2-day
        fetch window.
        """
        _unavailable_keys = (
            TANDEM_SENSOR_KEY_TOTAL_DAILY_INSULIN,
            TANDEM_SENSOR_KEY_DAILY_BOLUS_TOTAL,
            TANDEM_SENSOR_KEY_DAILY_BASAL_TOTAL,
            TANDEM_SENSOR_KEY_BASAL_BOLUS_SPLIT,
            TANDEM_SENSOR_KEY_DAILY_CARBS,
            TANDEM_SENSOR_KEY_DAILY_BOLUS_COUNT,
        )

        # Filter events to "today" in pump timezone
        tz = ZoneInfo(self.timezone)
        today = datetime.now(tz).date()

        def _today_only(events: list[dict]) -> list[dict]:
            result = []
            for e in events:
                ts = e.get("timestamp")
                if not ts:
                    continue
                if ts.tzinfo is None:
                    # Naive timestamp — local pump time
                    ts = ts.replace(tzinfo=tz)
                if ts.astimezone(tz).date() == today:
                    result.append(e)
            return result

        bolus_completed = _today_only(bolus_completed)
        bolex_completed = _today_only(bolex_completed)
        basal_delivery = _today_only(basal_delivery)
        basal_rate_changes = _today_only(basal_rate_changes)
        carbs_entered = _today_only(carbs_entered)

        # Daily bolus total: sum insulin_delivered from completed boluses
        all_bolus = bolus_completed + bolex_completed
        bolus_total = sum(b.get("insulin_delivered", 0) for b in all_bolus if b.get("insulin_delivered"))
        data[TANDEM_SENSOR_KEY_DAILY_BOLUS_TOTAL] = round(bolus_total, 2) if all_bolus else UNAVAILABLE
        data[TANDEM_SENSOR_KEY_DAILY_BOLUS_COUNT] = len(all_bolus) if all_bolus else UNAVAILABLE

        # Daily basal total: estimate from basal delivery events
        # Each basal_delivery event gives commanded_rate in U/hr.
        # Approximate: sum (rate * interval) for consecutive events.
        basal_total = 0.0
        if basal_delivery:
            sorted_basal = sorted(basal_delivery, key=lambda e: e["timestamp"])
            for i in range(len(sorted_basal) - 1):
                rate = sorted_basal[i].get("commanded_rate", 0) or 0
                dt_hours = (sorted_basal[i + 1]["timestamp"] - sorted_basal[i]["timestamp"]).total_seconds() / 3600.0
                # Cap interval at 1 hour to avoid gaps inflating the total
                dt_hours = min(dt_hours, 1.0)
                basal_total += rate * dt_hours
            # Add last segment (assume 5 min)
            last_rate = sorted_basal[-1].get("commanded_rate", 0) or 0
            basal_total += last_rate * (5.0 / 60.0)
        elif basal_rate_changes:
            sorted_basal = sorted(basal_rate_changes, key=lambda e: e["timestamp"])
            for i in range(len(sorted_basal) - 1):
                rate = sorted_basal[i].get("commanded_rate", 0) or 0
                dt_hours = (sorted_basal[i + 1]["timestamp"] - sorted_basal[i]["timestamp"]).total_seconds() / 3600.0
                dt_hours = min(dt_hours, 1.0)
                basal_total += rate * dt_hours
            last_rate = sorted_basal[-1].get("commanded_rate", 0) or 0
            basal_total += last_rate * (5.0 / 60.0)

        data[TANDEM_SENSOR_KEY_DAILY_BASAL_TOTAL] = (
            round(basal_total, 2) if (basal_delivery or basal_rate_changes) else UNAVAILABLE
        )

        # TDI and split
        if bolus_total > 0 or basal_total > 0:
            tdi = bolus_total + basal_total
            data[TANDEM_SENSOR_KEY_TOTAL_DAILY_INSULIN] = round(tdi, 2)
            data[TANDEM_SENSOR_KEY_BASAL_BOLUS_SPLIT] = round((basal_total / tdi) * 100, 1) if tdi > 0 else UNAVAILABLE
        else:
            data[TANDEM_SENSOR_KEY_TOTAL_DAILY_INSULIN] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_BASAL_BOLUS_SPLIT] = UNAVAILABLE

        # Daily carbs
        if carbs_entered:
            total_carbs = sum(c.get("carbs", 0) for c in carbs_entered)
            data[TANDEM_SENSOR_KEY_DAILY_CARBS] = total_carbs
        else:
            data[TANDEM_SENSOR_KEY_DAILY_CARBS] = UNAVAILABLE

        _LOGGER.debug(
            "Insulin summary: TDI=%.2f U, bolus=%.2f U (%d), basal=%.2f U, split=%.1f%%, carbs=%s g",
            data.get(TANDEM_SENSOR_KEY_TOTAL_DAILY_INSULIN) or 0,
            bolus_total,
            len(all_bolus),
            basal_total,
            data.get(TANDEM_SENSOR_KEY_BASAL_BOLUS_SPLIT) or 0,
            data.get(TANDEM_SENSOR_KEY_DAILY_CARBS, "N/A"),
        )

    # ── Long-term statistics import ──────────────────────────────────

    async def _import_statistics(self, pump_events: list[dict]) -> None:
        """Import pump events as HA long-term statistics.

        Creates correctly-timestamped 5-minute statistics entries so
        Statistics Graph cards show accurate historical data.
        """
        try:
            from homeassistant.components.recorder.statistics import (
                async_import_statistics,
            )
            from homeassistant.components.recorder.models import (
                StatisticData,
                StatisticMetaData,
            )
        except ImportError:
            _LOGGER.debug("Tandem: Recorder statistics API not available, skipping")
            return

        tz = ZoneInfo(self.timezone)

        # ── CGM statistics ───────────────────────────────────────────
        cgm_stats: list[StatisticData] = []
        iob_stats: list[StatisticData] = []
        basal_stats: list[StatisticData] = []
        carb_stats: list[StatisticData] = []
        bolus_stats: list[StatisticData] = []
        correction_stats: list[StatisticData] = []

        for evt in pump_events:
            eid = evt.get("event_id")
            ts = evt.get("timestamp")
            if not ts:
                continue

            # Pump event timestamps are naive local pump time — label them
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=tz)
            else:
                ts = ts.astimezone(tz)  # already aware (shouldn't happen)

            # Round down to the top of the hour for HA statistics
            # (HA requires timestamps at the top of the hour)
            period_start = ts.replace(minute=0, second=0, microsecond=0)

            if eid in (EVT_CGM_DATA_GXB, EVT_CGM_DATA_G7, EVT_CGM_DATA_FSL2):
                sg = evt.get("glucose_mgdl", 0)
                if sg and sg > 0:
                    mmol = round(sg * 0.0555, 2)
                    cgm_stats.append(
                        StatisticData(
                            start=period_start,
                            mean=mmol,
                            min=mmol,
                            max=mmol,
                            state=mmol,
                        )
                    )

            elif eid in (20, 21):  # BOLUS_COMPLETED / BOLEX_COMPLETED (has IOB + delivered)
                iob = evt.get("iob")
                if iob is not None:
                    iob_val = round(float(iob), 2)
                    iob_stats.append(
                        StatisticData(
                            start=period_start,
                            mean=iob_val,
                            min=iob_val,
                            max=iob_val,
                            state=iob_val,
                        )
                    )
                # Collect completed bolus delivery for bolus statistics
                if evt.get("completion_status") == 3:
                    delivered = evt.get("insulin_delivered")
                    if delivered is not None and delivered > 0:
                        bolus_val = round(float(delivered), 2)
                        bolus_stats.append(
                            StatisticData(
                                start=period_start,
                                mean=bolus_val,
                                state=bolus_val,
                            )
                        )

            elif eid in (3, 279):  # Basal
                rate = evt.get("commanded_rate")
                if rate is not None:
                    rate_val = round(float(rate), 3)
                    basal_stats.append(
                        StatisticData(
                            start=period_start,
                            mean=rate_val,
                            min=rate_val,
                            max=rate_val,
                            state=rate_val,
                        )
                    )

            elif eid == 48:  # CARBS_ENTERED
                carbs = evt.get("carbs")
                if carbs is not None and carbs > 0:
                    carbs_val = round(float(carbs), 1)
                    carb_stats.append(
                        StatisticData(
                            start=period_start,
                            mean=carbs_val,
                            state=carbs_val,
                        )
                    )

            elif eid == 280:  # EVT_BOLUS_DELIVERY — completed correction bolus
                if evt.get("delivery_status") == 0:
                    correction_mu = evt.get("correction_mu", 0)
                    if correction_mu and correction_mu > 0:
                        correction_val = round(correction_mu / 1000, 2)
                        correction_stats.append(
                            StatisticData(
                                start=period_start,
                                mean=correction_val,
                                state=correction_val,
                            )
                        )
                else:
                    _LOGGER.debug(
                        "Tandem: Skipping event 280 — delivery_status=%r (expected 0 for completed)",
                        evt.get("delivery_status"),
                    )

        # Import each statistic type — each in its own try/except so a failure
        # in one type does not prevent the others from being recorded.
        entity_prefix = f"sensor.{DOMAIN}"

        stat_types = [
            ("last_glucose_level_mmol", "Last glucose level mmol", "mmol/L", "CGM", cgm_stats),
            ("active_insulin_iob", "Active insulin (IOB)", "units", "IOB", iob_stats),
            ("basal_rate", "Basal rate", "U/hr", "basal", basal_stats),
            ("meal_carbs", "Meal carbs", "g", "carb", carb_stats),
            ("total_bolus", "Total bolus", "units", "bolus", bolus_stats),
            ("correction_bolus", "Correction bolus", "units", "correction", correction_stats),
        ]

        for stat_id_suffix, name, unit, log_label, stats in stat_types:
            if not stats:
                continue
            try:
                meta = StatisticMetaData(
                    has_mean=True,
                    has_sum=False,
                    name=name,
                    source="recorder",
                    statistic_id=f"{entity_prefix}_{stat_id_suffix}",
                    unit_of_measurement=unit,
                )
                async_import_statistics(self.hass, meta, stats)
                _LOGGER.info("[Tandem] Imported %d %s statistics", len(stats), log_label)
            except Exception as e:
                _LOGGER.warning("Tandem: Failed to import %s statistics: %s", log_label, e)


# ═══════════════════════════════════════════════════════════════════════════
# Helper functions (Carelink)
# ═══════════════════════════════════════════════════════════════════════════


def get_sg(sgs: list, pos: int) -> dict | None:
    """Retrieve sensor glucose reading at position from sorted valid readings."""
    try:
        valid = [sg for sg in sgs if sg.get("sensorState") == "NO_ERROR_MESSAGE"]
        sorted_sgs = sorted(
            valid,
            key=lambda x: convert_date_to_isodate(x["timestamp"]),
            reverse=True,
        )
        if pos < len(sorted_sgs):
            return sorted_sgs[pos]
        return None
    except Exception as error:
        _LOGGER.error("Error retrieving SG data at position %d: %s", pos, error)
        return None


def get_active_notification(last_alarm: dict, notifications: dict) -> dict | None:
    """Retrieve active notification from notifications list."""
    try:
        cleared = notifications.get("clearedNotifications")
        if cleared:
            sorted_cleared = sorted(
                cleared,
                key=lambda x: convert_date_to_isodate(x["dateTime"]),
                reverse=True,
            )
            for entry in sorted_cleared:
                if last_alarm["GUID"] == entry["referenceGUID"]:
                    return None
            return last_alarm
    except Exception as error:
        _LOGGER.error("Error checking active notifications: %s", error)
        return last_alarm


def get_last_marker(marker_type: str, markers: list) -> dict | None:
    """Retrieve the most recent marker of the given type from the 24h marker list."""
    try:
        filtered = [m for m in markers if m["type"] == marker_type]
        sorted_markers = sorted(
            filtered,
            key=lambda x: convert_date_to_isodate(x["timestamp"]),
            reverse=True,
        )

        last_marker = sorted_markers[0]
        for k in ["version", "kind", "index", "views"]:
            last_marker.pop(k, None)
        return {
            "DATETIME": convert_date_to_isodate(last_marker["timestamp"]),
            "ATTRS": last_marker,
        }
    except (IndexError, KeyError) as err:
        _LOGGER.debug("No '%s' marker found: %s", marker_type, err)
        return None
    except Exception as error:
        _LOGGER.error("Error parsing '%s' marker: %s", marker_type, error)
        return None
