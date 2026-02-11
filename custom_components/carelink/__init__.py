"""Medtronic Carelink / Tandem t:slim integration."""
from __future__ import annotations

import logging
import os
import re
import shutil

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.util.dt import DEFAULT_TIME_ZONE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from .api import CarelinkClient, LEGACY_AUTH_FILE, AUTH_FILE_PREFIX, SHARED_AUTH_FILE
from .tandem_api import TandemSourceClient, parse_dotnet_date
from .nightscout_uploader import NightscoutUploader

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
)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

_LOGGER = logging.getLogger(__name__)


# Fields containing personally identifiable information that should be redacted from logs
PII_FIELDS = {
    "firstName", "lastName", "username", "patientId", "conduitSerialNumber",
    "medicalDeviceSerialNumber", "systemId", "email", "phone", "emailAddress",
    "phoneNumber", "address", "dateOfBirth", "dob", "deviceSerialNumber",
    "patientName", "patientDateOfBirth", "patientCareGiver",
}


def sanitize_for_logging(data, depth=0):
    """Recursively sanitize data by redacting PII fields for safe logging."""
    if depth > 10:  # Prevent infinite recursion
        return "[MAX_DEPTH]"
    if isinstance(data, dict):
        return {
            k: "[REDACTED]" if k in PII_FIELDS else sanitize_for_logging(v, depth + 1)
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [sanitize_for_logging(item, depth + 1) for item in data]
    return data


def convert_date_to_isodate(date):
    date_iso = re.sub(r"\.\d{3}Z$", "+00:00", date)

    return datetime.fromisoformat(date_iso).replace(tzinfo=None)


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
            _LOGGER.info(
                "Copied logindata from shared location %s to %s",
                shared_path,
                new_path
            )
            return
        except OSError as error:
            _LOGGER.warning(
                "Failed to copy logindata from %s to %s: %s. "
                "Will use fallback location at runtime.",
                shared_path,
                new_path,
                error
            )

    # Try legacy location (old installations)
    if os.path.exists(legacy_path):
        try:
            shutil.copy(legacy_path, new_path)
            _LOGGER.info(
                "Migrated logindata from legacy location %s to %s",
                legacy_path,
                new_path
            )
            return
        except OSError as error:
            _LOGGER.warning(
                "Failed to migrate logindata from %s to %s: %s. "
                "Will use fallback location at runtime.",
                legacy_path,
                new_path,
                error
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up carelink from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    config = entry.data
    platform_type = config.get(PLATFORM_TYPE, PLATFORM_CARELINK)

    if platform_type == PLATFORM_TANDEM:
        return await _async_setup_tandem_entry(hass, entry, config)
    else:
        return await _async_setup_carelink_entry(hass, entry, config)


async def _async_setup_carelink_entry(
    hass: HomeAssistant, entry: ConfigEntry, config: dict
) -> bool:
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
        entry_id=entry.entry_id
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        CLIENT: carelink_client,
        PLATFORM_TYPE: PLATFORM_CARELINK,
    }

    if config.get("nightscout_url") and config.get("nightscout_api"):
        nightscout_uploader = NightscoutUploader(
            config["nightscout_url"],
            config["nightscout_api"]
        )
        hass.data[DOMAIN][entry.entry_id][UPLOADER] = nightscout_uploader

    coordinator = CarelinkCoordinator(
        hass, entry, update_interval=timedelta(seconds=config[SCAN_INTERVAL])
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id][COORDINATOR] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_setup_tandem_entry(
    hass: HomeAssistant, entry: ConfigEntry, config: dict
) -> bool:
    """Set up a Tandem t:slim Source config entry."""
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
        nightscout_uploader = NightscoutUploader(
            config["nightscout_url"],
            config["nightscout_api"]
        )
        hass.data[DOMAIN][entry.entry_id][UPLOADER] = nightscout_uploader

    coordinator = TandemCoordinator(
        hass, entry, update_interval=timedelta(seconds=config[SCAN_INTERVAL])
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id][COORDINATOR] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
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

        self.uploader = None
        self.client = hass.data[DOMAIN][entry.entry_id][CLIENT]
        self.timezone = hass.config.time_zone

        if UPLOADER in hass.data[DOMAIN][entry.entry_id]:
            self.uploader = hass.data[DOMAIN][entry.entry_id][UPLOADER]

    async def _async_update_data(self):

        data = {}
        client_timezone = DEFAULT_TIME_ZONE

        await self.client.login()
        recent_data = await self.client.get_recent_data()

        if recent_data is None:
            recent_data = dict()
        if recent_data and 'patientData' in recent_data:
            recent_data=recent_data['patientData']

        _LOGGER.debug("Before Data parsing %s", sanitize_for_logging(recent_data))
        try:
            if recent_data is not None and "clientTimeZoneName" in recent_data:
                client_timezone = recent_data["clientTimeZoneName"]

            data[SENSOR_KEY_CLIENT_TIMEZONE] = client_timezone

            timezone_map = MS_TIMEZONE_TO_IANA_MAP.setdefault(
                client_timezone, DEFAULT_TIME_ZONE
            )

            timezone = ZoneInfo(str(timezone_map))

            _LOGGER.debug("Using timezone %s", DEFAULT_TIME_ZONE)

        except Exception as error:
            _LOGGER.error(
                "Can not set timezone to %s. The error was: %s", timezone_map, error
            )
            timezone = ZoneInfo("Europe/London")

        _LOGGER.debug("Using timezone %s", DEFAULT_TIME_ZONE)

        # nightscout uploader
        if self.uploader:
            await self.uploader.send_recent_data(recent_data, timezone)

        recent_data["lastConduitDateTime"] = recent_data.setdefault("lastConduitDateTime", "")
        recent_data["activeInsulin"] = recent_data.setdefault("activeInsulin", {})
        recent_data["therapyAlgorithmState"] = recent_data.setdefault("therapyAlgorithmState", {})
        recent_data["lastAlarm"] = recent_data.setdefault("lastAlarm", {})
        recent_data["markers"] = recent_data.setdefault("markers", [])
        recent_data["sgs"] = recent_data.setdefault("sgs", [])

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
                data[SENSOR_KEY_SG_DELTA] = (float(current_sg["sg"]) - float(prev_sg["sg"]))

        # Sensors

        data[SENSOR_KEY_PUMP_BATTERY_LEVEL] = recent_data.setdefault(
            "pumpBatteryLevelPercent", UNAVAILABLE
        )
        data[SENSOR_KEY_CONDUIT_BATTERY_LEVEL] = recent_data.setdefault(
            "conduitBatteryLevel", UNAVAILABLE
        )
        data[SENSOR_KEY_SENSOR_BATTERY_LEVEL] = recent_data.setdefault(
            "gstBatteryLevel", UNAVAILABLE
        )
        data[SENSOR_KEY_SENSOR_DURATION_HOURS] = recent_data.setdefault(
            "sensorDurationHours", UNAVAILABLE
        )
        data[SENSOR_KEY_SENSOR_DURATION_MINUTES] = recent_data.setdefault(
            "sensorDurationMinutes", UNAVAILABLE
        )
        data[SENSOR_KEY_RESERVOIR_LEVEL] = recent_data.setdefault(
            "reservoirLevelPercent", UNAVAILABLE
        )
        data[SENSOR_KEY_RESERVOIR_AMOUNT] = recent_data.setdefault(
            "reservoirAmount", UNAVAILABLE
        )
        data[SENSOR_KEY_RESERVOIR_REMAINING_UNITS] = recent_data.setdefault(
            "reservoirRemainingUnits", UNAVAILABLE
        )
        data[SENSOR_KEY_LASTSG_TREND] = recent_data.setdefault(
            "lastSGTrend", UNAVAILABLE
        )

        data[SENSOR_KEY_TIME_TO_NEXT_CALIB_HOURS] = recent_data.setdefault(
            "timeToNextCalibHours", UNAVAILABLE
        )

        if recent_data["activeInsulin"]:
            if "amount" in recent_data["activeInsulin"]:
                # Active insulin sensor
                active_insulin = recent_data["activeInsulin"]

                amount = recent_data["activeInsulin"].setdefault(
                    "amount", UNAVAILABLE
                )
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

            last_alarm["dateTime"]=date_time_local
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
            data[SENSOR_KEY_ACTIVE_BASAL_PATTERN] = recent_data["therapyAlgorithmState"].setdefault(
                "autoModeShieldState", UNAVAILABLE
            )
        else:
            data[SENSOR_KEY_ACTIVE_BASAL_PATTERN] = UNAVAILABLE

        average_sg_raw = recent_data.setdefault("averageSG", UNAVAILABLE)
        if average_sg_raw is not None:
            data[SENSOR_KEY_AVG_GLUCOSE_MMOL] = float(
                round(average_sg_raw * 0.0555, 2)
            )
            data[SENSOR_KEY_AVG_GLUCOSE_MGDL] = average_sg_raw
        else:
            data[SENSOR_KEY_AVG_GLUCOSE_MMOL] = UNAVAILABLE
            data[SENSOR_KEY_AVG_GLUCOSE_MGDL] = UNAVAILABLE

        data[SENSOR_KEY_BELOW_HYPO_LIMIT] = recent_data.setdefault(
            "belowHypoLimit", UNAVAILABLE
        )
        data[SENSOR_KEY_ABOVE_HYPER_LIMIT] = recent_data.setdefault(
            "aboveHyperLimit", UNAVAILABLE
        )
        data[SENSOR_KEY_TIME_IN_RANGE] = recent_data.setdefault(
            "timeInRange", UNAVAILABLE
        )
        data[SENSOR_KEY_MAX_AUTO_BASAL_RATE] = recent_data.setdefault(
            "maxAutoBasalRate", UNAVAILABLE
        )
        data[SENSOR_KEY_SG_BELOW_LIMIT] = recent_data.setdefault(
            "sgBelowLimit", UNAVAILABLE
        )

        last_meal_marker = get_last_marker("MEAL", recent_data["markers"])

        if last_meal_marker is not None:
            data[SENSOR_KEY_LAST_MEAL_MARKER] = last_meal_marker["DATETIME"].replace(
                tzinfo=timezone
            )
            data[SENSOR_KEY_LAST_MEAL_MARKER_ATTRS] = last_meal_marker["ATTRS"]
        else:
            data[SENSOR_KEY_LAST_MEAL_MARKER] = UNAVAILABLE

        last_insuline_marker = get_last_marker("INSULIN", recent_data["markers"])

        if last_insuline_marker is not None:
            data[SENSOR_KEY_LAST_INSULIN_MARKER] = last_insuline_marker[
                "DATETIME"
            ].replace(tzinfo=timezone)
            data[SENSOR_KEY_LAST_INSULIN_MARKER_ATTRS] = last_insuline_marker["ATTRS"]
        else:
            data[SENSOR_KEY_LAST_INSULIN_MARKER] = UNAVAILABLE

        last_autobasal_marker = get_last_marker(
            "AUTO_BASAL_DELIVERY", recent_data["markers"]
        )

        if last_autobasal_marker is not None:
            data[SENSOR_KEY_LAST_AUTO_BASAL_DELIVERY_MARKER] = last_autobasal_marker[
                "DATETIME"
            ].replace(tzinfo=timezone)
            data[
                SENSOR_KEY_LAST_AUTO_BASAL_DELIVERY_MARKER_ATTRS
            ] = last_autobasal_marker["ATTRS"]
        else:
            data[SENSOR_KEY_LAST_AUTO_BASAL_DELIVERY_MARKER] = UNAVAILABLE

        last_auto_mode_status_marker = get_last_marker(
            "AUTO_MODE_STATUS", recent_data["markers"]
        )

        if last_auto_mode_status_marker is not None:
            data[
                SENSOR_KEY_LAST_AUTO_MODE_STATUS_MARKER
            ] = last_auto_mode_status_marker["DATETIME"].replace(tzinfo=timezone)
            data[
                SENSOR_KEY_LAST_AUTO_MODE_STATUS_MARKER_ATTRS
            ] = last_auto_mode_status_marker["ATTRS"]
        else:
            data[SENSOR_KEY_LAST_AUTO_MODE_STATUS_MARKER] = UNAVAILABLE

        last_low_glucose_marker = get_last_marker(
            "LOW_GLUCOSE_SUSPENDED", recent_data["markers"]
        )

        if last_low_glucose_marker is not None:
            data[
                SENSOR_KEY_LAST_LOW_GLUCOSE_SUSPENDED_MARKER
            ] = last_low_glucose_marker["DATETIME"].replace(tzinfo=timezone)
            data[
                SENSOR_KEY_LAST_LOW_GLUCOSE_SUSPENDED_MARKER_ATTRS
            ] = last_low_glucose_marker["ATTRS"]
        else:
            data[SENSOR_KEY_LAST_LOW_GLUCOSE_SUSPENDED_MARKER] = UNAVAILABLE

        # Binary Sensors

        data[BINARY_SENSOR_KEY_PUMP_COMM_STATE] = recent_data.setdefault(
            "pumpCommunicationState", UNAVAILABLE
        )
        data[BINARY_SENSOR_KEY_SENSOR_COMM_STATE] = recent_data.setdefault(
            "gstCommunicationState", UNAVAILABLE
        )
        data[BINARY_SENSOR_KEY_CONDUIT_IN_RANGE] = recent_data.setdefault(
            "conduitInRange", UNAVAILABLE
        )
        data[BINARY_SENSOR_KEY_CONDUIT_PUMP_IN_RANGE] = recent_data.setdefault(
            "conduitMedicalDeviceInRange", UNAVAILABLE
        )
        data[BINARY_SENSOR_KEY_CONDUIT_SENSOR_IN_RANGE] = recent_data.setdefault(
            "conduitSensorInRange", UNAVAILABLE
        )

        # Device info

        data[DEVICE_PUMP_SERIAL] = recent_data.setdefault(
            "conduitSerialNumber", UNAVAILABLE
        )
        data[DEVICE_PUMP_NAME] = (
            recent_data.setdefault("firstName", "Name")
            + " "
            + recent_data.setdefault("lastName", "Unvailable")
        )
        data[DEVICE_PUMP_MODEL] = recent_data.setdefault("pumpModelNumber", UNAVAILABLE)
        data[DEVICE_PUMP_MANUFACTURER] = "Medtronic"

        data[SENSOR_KEY_APP_MODEL_TYPE] = recent_data.setdefault(
            "appModelType", UNAVAILABLE
        )

        # Add device info when available

        if "medicalDeviceInformation" in recent_data:

            data[SENSOR_KEY_MEDICAL_DEVICE_MANUFACTURER] = recent_data[
                "medicalDeviceInformation"
            ].setdefault("manufacturer", UNAVAILABLE)

            data[SENSOR_KEY_MEDICAL_DEVICE_MODEL_NUMBER] = recent_data[
                "medicalDeviceInformation"
            ].setdefault("modelNumber", UNAVAILABLE)

            data[SENSOR_KEY_MEDICAL_DEVICE_HARDWARE_REVISION] = recent_data[
                "medicalDeviceInformation"
            ].setdefault("hardwareRevision", UNAVAILABLE)

            data[SENSOR_KEY_MEDICAL_DEVICE_FIRMWARE_REVISION] = recent_data[
                "medicalDeviceInformation"
            ].setdefault("firmwareRevision", UNAVAILABLE)
            data[SENSOR_KEY_MEDICAL_DEVICE_SYSTEM_ID] = recent_data[
                "medicalDeviceInformation"
            ].setdefault("systemId", UNAVAILABLE)

        _LOGGER.debug("_async_update_data: %s", sanitize_for_logging(data))

        return data


# ═══════════════════════════════════════════════════════════════════════════
# Tandem t:slim Coordinator
# ═══════════════════════════════════════════════════════════════════════════

class TandemCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the Tandem Source API."""

    def __init__(self, hass: HomeAssistant, entry, update_interval: timedelta):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

        self.uploader = None
        self.client = hass.data[DOMAIN][entry.entry_id][TANDEM_CLIENT]
        self.timezone = hass.config.time_zone
        self._prev_sg_mgdl: float | None = None

        if UPLOADER in hass.data[DOMAIN][entry.entry_id]:
            self.uploader = hass.data[DOMAIN][entry.entry_id][UPLOADER]

    async def _async_update_data(self):
        data = {}

        await self.client.login()
        recent_data = await self.client.get_recent_data()

        _LOGGER.debug(
            "Tandem before data parsing: %s", sanitize_for_logging(recent_data)
        )

        # Log what data sources are available
        _LOGGER.info(
            "Tandem data sources: pump_metadata=%s, pumper_info=%s, "
            "therapy_timeline=%s, dashboard_summary=%s",
            "present" if recent_data.get("pump_metadata") else "MISSING",
            "present" if recent_data.get("pumper_info") else "MISSING",
            "present" if recent_data.get("therapy_timeline") else "MISSING",
            "present" if recent_data.get("dashboard_summary") else "MISSING",
        )

        # ── Device info from pump metadata ───────────────────────────────
        metadata = recent_data.get("pump_metadata")
        pumper_info = recent_data.get("pumper_info")

        if metadata:
            _LOGGER.debug(
                "Tandem metadata keys: %s", list(metadata.keys())
            )
            data[DEVICE_PUMP_SERIAL] = metadata.get("serialNumber", "unknown")
            data[DEVICE_PUMP_MODEL] = metadata.get("modelNumber", "t:slim X2")
            data[DEVICE_PUMP_NAME] = metadata.get("patientName", "Tandem Pump")
            data[TANDEM_SENSOR_KEY_PUMP_SERIAL_INFO] = metadata.get("serialNumber")
            data[TANDEM_SENSOR_KEY_PUMP_MODEL_INFO] = metadata.get("modelNumber")
            data[TANDEM_SENSOR_KEY_SOFTWARE_VERSION] = metadata.get("softwareVersion")

            # Parse last upload timestamp
            last_upload = metadata.get("lastUpload")
            if last_upload:
                upload_dt = parse_dotnet_date(last_upload)
                if upload_dt:
                    data[TANDEM_SENSOR_KEY_LAST_UPLOAD] = upload_dt.replace(
                        tzinfo=ZoneInfo(self.timezone)
                    )
                    data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] = upload_dt.replace(
                        tzinfo=ZoneInfo(self.timezone)
                    )
                else:
                    data[TANDEM_SENSOR_KEY_LAST_UPLOAD] = UNAVAILABLE
                    data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] = UNAVAILABLE
            else:
                data[TANDEM_SENSOR_KEY_LAST_UPLOAD] = UNAVAILABLE
                data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] = UNAVAILABLE
        else:
            data[DEVICE_PUMP_SERIAL] = "unknown"
            data[DEVICE_PUMP_MODEL] = "t:slim X2"
            data[DEVICE_PUMP_NAME] = "Tandem Pump"
            data[TANDEM_SENSOR_KEY_PUMP_SERIAL_INFO] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_PUMP_MODEL_INFO] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_SOFTWARE_VERSION] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_LAST_UPLOAD] = UNAVAILABLE
            data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] = UNAVAILABLE

        data[DEVICE_PUMP_MANUFACTURER] = "Tandem Diabetes Care"

        # Override name from pumper info if available
        if pumper_info:
            first = pumper_info.get("firstName", "")
            last = pumper_info.get("lastName", "")
            name = f"{first} {last}".strip()
            if name:
                data[DEVICE_PUMP_NAME] = name

        # ── Therapy timeline (CGM, bolus, basal) ────────────────────────
        timeline = recent_data.get("therapy_timeline")
        self._parse_therapy_timeline(timeline, data)

        # ── Dashboard summary (statistics) ───────────────────────────────
        summary = recent_data.get("dashboard_summary")
        self._parse_dashboard_summary(summary, data)

        _LOGGER.debug(
            "Tandem _async_update_data: %s", sanitize_for_logging(data)
        )

        return data

    def _parse_therapy_timeline(self, timeline: dict | None, data: dict) -> None:
        """Parse therapy timeline data into sensor values."""
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
                        data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] = latest_dt.replace(
                            tzinfo=ZoneInfo(self.timezone)
                        )

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
                    key=lambda b: parse_dotnet_date(
                        b.get("CompletionDateTime") or b.get("RequestDateTime", 0)
                    ) or datetime.min,
                    reverse=True,
                )

                last_bolus = sorted_boluses[0]
                insulin = last_bolus.get("InsulinDelivered", 0)
                data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] = round(float(insulin), 2) if insulin else UNAVAILABLE

                bolus_dt = parse_dotnet_date(
                    last_bolus.get("CompletionDateTime")
                    or last_bolus.get("RequestDateTime")
                )
                if bolus_dt:
                    data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] = bolus_dt.replace(
                        tzinfo=ZoneInfo(self.timezone)
                    )
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
                    data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] = round(float(meal_insulin), 2) if meal_insulin else UNAVAILABLE
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
                data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] = round(
                    float(avg_reading) * 0.0555, 2
                )
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


# ═══════════════════════════════════════════════════════════════════════════
# Helper functions (Carelink)
# ═══════════════════════════════════════════════════════════════════════════

def get_sg(sgs: list, pos: int) -> dict:
    """Retrieve previous sg from list"""

    try:
        array = [sg for sg in sgs if "sensorState" in sg.keys() and sg["sensorState"] == "NO_ERROR_MESSAGE"]
        sorted_array = sorted(
            array,
            key=lambda x: convert_date_to_isodate(x["timestamp"]),
            reverse=True,
        )

        if len(sorted_array) > pos:
            return sorted_array[pos]
        else:
            return None
    except Exception as error:
        _LOGGER.error(
            "the sg data could not be tracked correctly. A unknown error happened while parsing the data.",
            error,
        )
        return None

def get_active_notification(last_alarm: list, notifications: list) -> dict:
    """Retrieve active notification from notifications list"""
    try:
        filtered_array = notifications["clearedNotifications"]
        if filtered_array:
            sorted_array = sorted(
                filtered_array,
                key=lambda x: convert_date_to_isodate(x["dateTime"]),
                reverse=True,
            )
            for entry in sorted_array:
                if last_alarm["GUID"] == entry["referenceGUID"]:
                    return None
            return last_alarm
    except Exception as error:
        _LOGGER.error(
            "Check if your Carelink data contains an active notification, it seems to be missing.", error
        )
        return last_alarm

def get_last_marker(marker_type: str, markers: list) -> dict:
    """Retrieve last marker from type in 24h marker list"""

    try:
        filtered_array = [marker for marker in markers if marker["type"] == marker_type]
        sorted_array = sorted(
            filtered_array,
            key=lambda x: convert_date_to_isodate(x["timestamp"]),
            reverse=True,
        )

        last_marker = sorted_array[0]
        for k in ["version", "kind", "index", "views"]:
            last_marker.pop(k, None)
        return {
            "DATETIME": convert_date_to_isodate(last_marker["timestamp"]),
            "ATTRS": last_marker,
        }
    except (IndexError, KeyError) as index_error:
        _LOGGER.debug(
            "the marker with type '%s' could not be tracked correctly. Check if your Carelink data contains a key with the name %s, it seems to be missing.",
            marker_type,
            index_error,
        )
        return None
    except Exception as error:
        _LOGGER.error(
            "the marker with type '%s' could not be tracked correctly. A unknown error happened while parsing the data.",
            error,
        )
        return None
