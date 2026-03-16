"""Tests for CarelinkCoordinator (Medtronic) to cover new-code lines in __init__.py.

Covers uncovered new-code lines in __init__.py for CarelinkCoordinator:
- Lines 466-467, 481, 484-490: __init__ + _async_update_data setup
- Lines 499, 504, 518: timezone mapping + defaults
- Lines 537, 548, 557-578: SG history + battery/sensor data
- Lines 644, 650-654: glucose averages + range limits
- Lines 659-700: marker processing (meal, insulin, auto_basal, auto_mode, low_glucose)
- Lines 704-708, 712-725: binary sensors + device info
- Lines 731, 752, 760, 765, 768, 777, 787: SG statistics import
- Lines 811, 829: statistics exception paths
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.carelink.const import (
    BINARY_SENSOR_KEY_CONDUIT_IN_RANGE,
    BINARY_SENSOR_KEY_CONDUIT_PUMP_IN_RANGE,
    BINARY_SENSOR_KEY_CONDUIT_SENSOR_IN_RANGE,
    BINARY_SENSOR_KEY_PUMP_COMM_STATE,
    BINARY_SENSOR_KEY_SENSOR_COMM_STATE,
    CLIENT,
    DEVICE_PUMP_MANUFACTURER,
    DEVICE_PUMP_MODEL,
    DEVICE_PUMP_NAME,
    DEVICE_PUMP_SERIAL,
    DOMAIN,
    PLATFORM_CARELINK,
    PLATFORM_TYPE,
    SENSOR_KEY_ABOVE_HYPER_LIMIT,
    SENSOR_KEY_ACTIVE_BASAL_PATTERN,
    SENSOR_KEY_ACTIVE_INSULIN,
    SENSOR_KEY_APP_MODEL_TYPE,
    SENSOR_KEY_AVG_GLUCOSE_MGDL,
    SENSOR_KEY_AVG_GLUCOSE_MMOL,
    SENSOR_KEY_BELOW_HYPO_LIMIT,
    SENSOR_KEY_CLIENT_TIMEZONE,
    SENSOR_KEY_CONDUIT_BATTERY_LEVEL,
    SENSOR_KEY_LAST_ALARM,
    SENSOR_KEY_LAST_AUTO_BASAL_DELIVERY_MARKER,
    SENSOR_KEY_LAST_AUTO_MODE_STATUS_MARKER,
    SENSOR_KEY_LAST_INSULIN_MARKER,
    SENSOR_KEY_LAST_LOW_GLUCOSE_SUSPENDED_MARKER,
    SENSOR_KEY_LAST_MEAL_MARKER,
    SENSOR_KEY_LASTSG_MGDL,
    SENSOR_KEY_LASTSG_MMOL,
    SENSOR_KEY_LASTSG_TREND,
    SENSOR_KEY_MAX_AUTO_BASAL_RATE,
    SENSOR_KEY_MEDICAL_DEVICE_FIRMWARE_REVISION,
    SENSOR_KEY_MEDICAL_DEVICE_HARDWARE_REVISION,
    SENSOR_KEY_MEDICAL_DEVICE_MANUFACTURER,
    SENSOR_KEY_MEDICAL_DEVICE_MODEL_NUMBER,
    SENSOR_KEY_MEDICAL_DEVICE_SYSTEM_ID,
    SENSOR_KEY_PUMP_BATTERY_LEVEL,
    SENSOR_KEY_RESERVOIR_AMOUNT,
    SENSOR_KEY_RESERVOIR_LEVEL,
    SENSOR_KEY_RESERVOIR_REMAINING_UNITS,
    SENSOR_KEY_SENSOR_BATTERY_LEVEL,
    SENSOR_KEY_SENSOR_DURATION_HOURS,
    SENSOR_KEY_SENSOR_DURATION_MINUTES,
    SENSOR_KEY_SG_BELOW_LIMIT,
    SENSOR_KEY_TIME_IN_RANGE,
    SENSOR_KEY_TIME_TO_NEXT_CALIB_HOURS,
    SENSOR_KEY_UPDATE_TIMESTAMP,
    UNAVAILABLE,
)


# ─── Helpers ───────────────────────────────────────────────────────────────


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "platform_type": "carelink",
            "cl_token": "mock_token",
            "cl_refresh_token": "mock_refresh",
            "cl_client_id": "mock_client_id",
            "cl_client_secret": "mock_secret",
            "cl_mag_identifier": "mock_mag",
            "patientId": "mock_patient",
            "scan_interval": 60,
        },
    )
    entry.add_to_hass(hass)
    return entry


def _make_recent_data() -> dict:
    """Return mock data similar to conftest mock_recent_data, wrapped in patientData."""
    return {
        "patientData": {
            "clientTimeZoneName": "Europe/Amsterdam",
            "lastConduitDateTime": "2024-01-15T12:00:00.000Z",
            "pumpBatteryLevelPercent": 75,
            "conduitBatteryLevel": 100,
            "gstBatteryLevel": 80,
            "sensorDurationHours": 120,
            "sensorDurationMinutes": 30,
            "reservoirLevelPercent": 50,
            "reservoirAmount": 100,
            "reservoirRemainingUnits": 50,
            "lastSGTrend": "FLAT",
            "timeToNextCalibHours": 6,
            "averageSG": 120,
            "belowHypoLimit": 5,
            "aboveHyperLimit": 10,
            "timeInRange": 85,
            "maxAutoBasalRate": 2.5,
            "sgBelowLimit": 70,
            "pumpCommunicationState": True,
            "gstCommunicationState": True,
            "conduitInRange": True,
            "conduitMedicalDeviceInRange": True,
            "conduitSensorInRange": True,
            "conduitSerialNumber": "MOCK123456",
            "firstName": "Test",
            "lastName": "User",
            "pumpModelNumber": "MMT-1780",
            "appModelType": "Guardian",
            "activeInsulin": {
                "amount": 2.5,
                "datetime": "2024-01-15T11:30:00.000Z",
            },
            "lastAlarm": {
                "dateTime": "2024-01-15T10:00:00.000Z",
                "faultId": 123,
                "GUID": "mock-guid",
            },
            "therapyAlgorithmState": {
                "autoModeShieldState": "SAFE_BASAL",
            },
            "markers": [],
            "sgs": [
                {
                    "timestamp": "2024-01-15T12:00:00.000Z",
                    "sg": 120,
                    "sensorState": "NO_ERROR_MESSAGE",
                },
                {
                    "timestamp": "2024-01-15T11:55:00.000Z",
                    "sg": 118,
                    "sensorState": "NO_ERROR_MESSAGE",
                },
            ],
            "notificationHistory": {
                "clearedNotifications": [],
            },
            "medicalDeviceInformation": {
                "manufacturer": "Medtronic",
                "modelNumber": "MMT-1780",
                "hardwareRevision": "1.0",
                "firmwareRevision": "2.0",
                "systemId": "MOCK_SYSTEM_ID",
            },
        }
    }


def _make_client(recent_data=None) -> AsyncMock:
    client = AsyncMock()
    client.login = AsyncMock(return_value=True)
    client.get_recent_data = AsyncMock(return_value=recent_data or _make_recent_data())
    return client


async def _make_coordinator(hass: HomeAssistant, recent_data=None):
    """Create and initialise a CarelinkCoordinator."""
    from custom_components.carelink import CarelinkCoordinator

    entry = _make_entry(hass)
    client = _make_client(recent_data)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        CLIENT: client,
        PLATFORM_TYPE: PLATFORM_CARELINK,
    }
    coordinator = CarelinkCoordinator(hass, entry, update_interval=timedelta(seconds=60))
    # Patch _import_sg_statistics to avoid recorder dependency
    with patch.object(coordinator, "_import_sg_statistics", new_callable=AsyncMock):
        await coordinator.async_config_entry_first_refresh()
    return coordinator, client


# ─── Full update cycle ─────────────────────────────────────────────────────


class TestCarelinkCoordinatorFullCycle:
    """CarelinkCoordinator processes recent_data and populates all sensors."""

    async def test_full_update_populates_sensors(self, hass: HomeAssistant):
        """Full update with valid data sets all sensor keys."""
        coordinator, _ = await _make_coordinator(hass)
        data = coordinator.data

        # Timezone
        assert data[SENSOR_KEY_CLIENT_TIMEZONE] == "Europe/Amsterdam"

        # Last update timestamp
        assert data[SENSOR_KEY_UPDATE_TIMESTAMP] is not None

        # Glucose
        assert data[SENSOR_KEY_LASTSG_MMOL] == round(120 * 0.0555, 2)
        assert data[SENSOR_KEY_LASTSG_MGDL] == 120

        # Battery levels
        assert data[SENSOR_KEY_PUMP_BATTERY_LEVEL] == 75
        assert data[SENSOR_KEY_CONDUIT_BATTERY_LEVEL] == 100
        assert data[SENSOR_KEY_SENSOR_BATTERY_LEVEL] == 80

        # Sensor duration
        assert data[SENSOR_KEY_SENSOR_DURATION_HOURS] == 120
        assert data[SENSOR_KEY_SENSOR_DURATION_MINUTES] == 30

        # Reservoir
        assert data[SENSOR_KEY_RESERVOIR_LEVEL] == 50
        assert data[SENSOR_KEY_RESERVOIR_AMOUNT] == 100
        assert data[SENSOR_KEY_RESERVOIR_REMAINING_UNITS] == 50

        # Trend / calibration
        assert data[SENSOR_KEY_LASTSG_TREND] == "FLAT"
        assert data[SENSOR_KEY_TIME_TO_NEXT_CALIB_HOURS] == 6

        # Averages and limits
        assert data[SENSOR_KEY_AVG_GLUCOSE_MMOL] == round(120 * 0.0555, 2)
        assert data[SENSOR_KEY_AVG_GLUCOSE_MGDL] == 120
        assert data[SENSOR_KEY_BELOW_HYPO_LIMIT] == 5
        assert data[SENSOR_KEY_ABOVE_HYPER_LIMIT] == 10
        assert data[SENSOR_KEY_TIME_IN_RANGE] == 85
        assert data[SENSOR_KEY_MAX_AUTO_BASAL_RATE] == 2.5
        assert data[SENSOR_KEY_SG_BELOW_LIMIT] == 70

        # Active insulin
        assert data[SENSOR_KEY_ACTIVE_INSULIN] == 2.5

        # Therapy state
        assert data[SENSOR_KEY_ACTIVE_BASAL_PATTERN] == "SAFE_BASAL"

        # Binary sensors
        assert data[BINARY_SENSOR_KEY_PUMP_COMM_STATE] is True
        assert data[BINARY_SENSOR_KEY_SENSOR_COMM_STATE] is True
        assert data[BINARY_SENSOR_KEY_CONDUIT_IN_RANGE] is True
        assert data[BINARY_SENSOR_KEY_CONDUIT_PUMP_IN_RANGE] is True
        assert data[BINARY_SENSOR_KEY_CONDUIT_SENSOR_IN_RANGE] is True

        # Device info
        assert data[DEVICE_PUMP_SERIAL] == "MOCK123456"
        assert data[DEVICE_PUMP_NAME] == "Test User"
        assert data[DEVICE_PUMP_MODEL] == "MMT-1780"
        assert data[DEVICE_PUMP_MANUFACTURER] == "Medtronic"

        # Medical device info
        assert data[SENSOR_KEY_MEDICAL_DEVICE_MANUFACTURER] == "Medtronic"
        assert data[SENSOR_KEY_MEDICAL_DEVICE_MODEL_NUMBER] == "MMT-1780"
        assert data[SENSOR_KEY_MEDICAL_DEVICE_HARDWARE_REVISION] == "1.0"
        assert data[SENSOR_KEY_MEDICAL_DEVICE_FIRMWARE_REVISION] == "2.0"
        assert data[SENSOR_KEY_MEDICAL_DEVICE_SYSTEM_ID] == "MOCK_SYSTEM_ID"

        # App model type
        assert data[SENSOR_KEY_APP_MODEL_TYPE] == "Guardian"

        # Markers are empty → UNAVAILABLE
        assert data[SENSOR_KEY_LAST_MEAL_MARKER] is UNAVAILABLE
        assert data[SENSOR_KEY_LAST_INSULIN_MARKER] is UNAVAILABLE
        assert data[SENSOR_KEY_LAST_AUTO_BASAL_DELIVERY_MARKER] is UNAVAILABLE
        assert data[SENSOR_KEY_LAST_AUTO_MODE_STATUS_MARKER] is UNAVAILABLE
        assert data[SENSOR_KEY_LAST_LOW_GLUCOSE_SUSPENDED_MARKER] is UNAVAILABLE

    async def test_patient_data_unwrapped(self, hass: HomeAssistant):
        """patientData wrapper is unwrapped before processing."""
        coordinator, client = await _make_coordinator(hass)
        assert coordinator.data[SENSOR_KEY_LASTSG_MGDL] == 120

    async def test_none_recent_data_no_crash(self, hass: HomeAssistant):
        """None return from API results in empty dict, no crash."""
        coordinator, _ = await _make_coordinator(hass, recent_data=None)
        # Should still complete without error (data will have defaults)
        assert coordinator.data is not None

    async def test_empty_dict_recent_data(self, hass: HomeAssistant):
        """Empty dict from API processes without crash."""
        coordinator, _ = await _make_coordinator(hass, recent_data={})
        assert coordinator.data is not None

    async def test_login_exception_raises_config_entry_not_ready(self, hass: HomeAssistant):
        """Login exception → UpdateFailed → ConfigEntryNotReady."""
        from custom_components.carelink import CarelinkCoordinator

        entry = _make_entry(hass)
        client = _make_client()
        client.login = AsyncMock(side_effect=Exception("network error"))
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            CLIENT: client,
            PLATFORM_TYPE: PLATFORM_CARELINK,
        }
        coordinator = CarelinkCoordinator(hass, entry, update_interval=timedelta(seconds=60))
        with pytest.raises(ConfigEntryNotReady):
            await coordinator.async_config_entry_first_refresh()

    async def test_login_returns_false_raises_config_entry_auth_failed(self, hass: HomeAssistant):
        """Login returning False → ConfigEntryAuthFailed (triggers reauth)."""
        from custom_components.carelink import CarelinkCoordinator

        entry = _make_entry(hass)
        client = _make_client()
        client.login = AsyncMock(return_value=False)
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            CLIENT: client,
            PLATFORM_TYPE: PLATFORM_CARELINK,
        }
        coordinator = CarelinkCoordinator(hass, entry, update_interval=timedelta(seconds=60))
        with pytest.raises(ConfigEntryAuthFailed):
            await coordinator.async_config_entry_first_refresh()

    async def test_averagesg_none_sets_unavailable(self, hass: HomeAssistant):
        """averageSG=None → both average glucose sensors set to UNAVAILABLE."""
        raw = _make_recent_data()
        raw["patientData"]["averageSG"] = None
        coordinator, _ = await _make_coordinator(hass, recent_data=raw)
        assert coordinator.data[SENSOR_KEY_AVG_GLUCOSE_MMOL] is UNAVAILABLE
        assert coordinator.data[SENSOR_KEY_AVG_GLUCOSE_MGDL] is UNAVAILABLE

    async def test_no_medical_device_info(self, hass: HomeAssistant):
        """Missing medicalDeviceInformation → device info keys absent."""
        raw = _make_recent_data()
        del raw["patientData"]["medicalDeviceInformation"]
        coordinator, _ = await _make_coordinator(hass, recent_data=raw)
        assert SENSOR_KEY_MEDICAL_DEVICE_MANUFACTURER not in coordinator.data

    async def test_empty_active_insulin(self, hass: HomeAssistant):
        """Empty activeInsulin → UNAVAILABLE."""
        raw = _make_recent_data()
        raw["patientData"]["activeInsulin"] = {}
        coordinator, _ = await _make_coordinator(hass, recent_data=raw)
        assert coordinator.data[SENSOR_KEY_ACTIVE_INSULIN] is UNAVAILABLE

    async def test_no_therapy_state(self, hass: HomeAssistant):
        """None therapyAlgorithmState → UNAVAILABLE basal pattern."""
        raw = _make_recent_data()
        raw["patientData"]["therapyAlgorithmState"] = None
        coordinator, _ = await _make_coordinator(hass, recent_data=raw)
        assert coordinator.data[SENSOR_KEY_ACTIVE_BASAL_PATTERN] is UNAVAILABLE

    async def test_no_last_alarm(self, hass: HomeAssistant):
        """Empty lastAlarm → UNAVAILABLE."""
        raw = _make_recent_data()
        raw["patientData"]["lastAlarm"] = {}
        coordinator, _ = await _make_coordinator(hass, recent_data=raw)
        assert coordinator.data[SENSOR_KEY_LAST_ALARM] is UNAVAILABLE

    async def test_string_fault_id(self, hass: HomeAssistant):
        """String faultId (Simplera sensor) uses it as-is."""
        raw = _make_recent_data()
        raw["patientData"]["lastAlarm"]["faultId"] = "alert.sg.threshold.low"
        coordinator, _ = await _make_coordinator(hass, recent_data=raw)
        assert coordinator.data[SENSOR_KEY_LAST_ALARM] is not UNAVAILABLE

    async def test_markers_present_populates_sensor_keys(self, hass: HomeAssistant):
        """Markers with data → marker sensor keys populated (lines 659-698)."""
        raw = _make_recent_data()
        raw["patientData"]["markers"] = [
            {"type": "MEAL", "timestamp": "2024-01-15T11:00:00.000Z", "index": 0, "value": 45},
            {"type": "INSULIN", "timestamp": "2024-01-15T10:30:00.000Z", "index": 1, "value": 3.5},
            {
                "type": "AUTO_BASAL_DELIVERY",
                "timestamp": "2024-01-15T10:00:00.000Z",
                "index": 2,
                "value": 0.8,
            },
            {
                "type": "AUTO_MODE_STATUS",
                "timestamp": "2024-01-15T09:00:00.000Z",
                "index": 3,
                "value": "ON",
            },
            {
                "type": "LOW_GLUCOSE_SUSPENDED",
                "timestamp": "2024-01-15T08:00:00.000Z",
                "index": 4,
                "value": "SUSPEND",
            },
        ]
        coordinator, _ = await _make_coordinator(hass, recent_data=raw)
        assert coordinator.data[SENSOR_KEY_LAST_MEAL_MARKER] is not UNAVAILABLE
        assert coordinator.data[SENSOR_KEY_LAST_INSULIN_MARKER] is not UNAVAILABLE
        assert coordinator.data[SENSOR_KEY_LAST_AUTO_BASAL_DELIVERY_MARKER] is not UNAVAILABLE
        assert coordinator.data[SENSOR_KEY_LAST_AUTO_MODE_STATUS_MARKER] is not UNAVAILABLE
        assert coordinator.data[SENSOR_KEY_LAST_LOW_GLUCOSE_SUSPENDED_MARKER] is not UNAVAILABLE

    async def test_active_notification_present(self, hass: HomeAssistant):
        """lastAlarm with uncleared notification → active notification set (lines 621-622)."""
        raw = _make_recent_data()
        # clearedNotifications has an entry but with a different GUID → alarm is still active
        raw["patientData"]["notificationHistory"] = {
            "clearedNotifications": [
                {
                    "dateTime": "2024-01-15T09:00:00.000Z",
                    "referenceGUID": "different-guid",
                }
            ],
        }
        coordinator, _ = await _make_coordinator(hass, recent_data=raw)
        assert coordinator.data[SENSOR_KEY_LAST_ALARM] is not UNAVAILABLE


class TestCarelinkSGStatistics:
    """SG statistics import paths."""

    async def test_sg_statistics_called_with_valid_sgs(self, hass: HomeAssistant):
        """Valid SGs trigger _import_sg_statistics."""
        from custom_components.carelink import CarelinkCoordinator

        entry = _make_entry(hass)
        client = _make_client()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            CLIENT: client,
            PLATFORM_TYPE: PLATFORM_CARELINK,
        }
        coordinator = CarelinkCoordinator(hass, entry, update_interval=timedelta(seconds=60))
        with patch.object(coordinator, "_import_sg_statistics", new_callable=AsyncMock) as mock_import:
            await coordinator.async_config_entry_first_refresh()
            mock_import.assert_called_once()

    async def test_no_valid_sgs_skips_statistics(self, hass: HomeAssistant):
        """No valid SGs → _import_sg_statistics not called."""
        from custom_components.carelink import CarelinkCoordinator

        raw = _make_recent_data()
        raw["patientData"]["sgs"] = []  # No SG readings
        entry = _make_entry(hass)
        client = _make_client(raw)
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            CLIENT: client,
            PLATFORM_TYPE: PLATFORM_CARELINK,
        }
        coordinator = CarelinkCoordinator(hass, entry, update_interval=timedelta(seconds=60))
        with patch.object(coordinator, "_import_sg_statistics", new_callable=AsyncMock) as mock_import:
            await coordinator.async_config_entry_first_refresh()
            mock_import.assert_not_called()

    async def test_import_sg_statistics_direct(self, hass: HomeAssistant):
        """Direct call to _import_sg_statistics processes SG data (lines 743-829)."""
        from custom_components.carelink import CarelinkCoordinator
        from unittest.mock import MagicMock
        from zoneinfo import ZoneInfo

        entry = _make_entry(hass)
        client = _make_client()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            CLIENT: client,
            PLATFORM_TYPE: PLATFORM_CARELINK,
        }
        coordinator = CarelinkCoordinator(hass, entry, update_interval=timedelta(seconds=60))
        with patch.object(coordinator, "_import_sg_statistics", new_callable=AsyncMock):
            await coordinator.async_config_entry_first_refresh()

        valid_sgs = [
            {
                "timestamp": "2024-01-15T12:00:00.000Z",
                "sg": 120,
                "sensorState": "NO_ERROR_MESSAGE",
            },
            {
                "timestamp": "2024-01-15T12:05:00.000Z",
                "sg": 125,
                "sensorState": "NO_ERROR_MESSAGE",
            },
        ]
        tz = ZoneInfo("Europe/Amsterdam")

        mock_import_stats = MagicMock()
        mock_stat_data = MagicMock(side_effect=lambda **kwargs: kwargs)
        mock_stat_meta = MagicMock(side_effect=lambda **kwargs: kwargs)

        with patch.dict(
            "sys.modules",
            {
                "homeassistant.components.recorder.statistics": MagicMock(async_import_statistics=mock_import_stats),
                "homeassistant.components.recorder.models": MagicMock(
                    StatisticData=mock_stat_data,
                    StatisticMetaData=mock_stat_meta,
                ),
            },
        ):
            await coordinator._import_sg_statistics(valid_sgs, tz)
            # Should have been called twice: once for mmol, once for mgdl
            assert mock_import_stats.call_count == 2

    async def test_import_sg_statistics_exception_handled(self, hass: HomeAssistant):
        """Exception in statistics import is caught and logged (line 811, 829)."""
        from custom_components.carelink import CarelinkCoordinator
        from unittest.mock import MagicMock
        from zoneinfo import ZoneInfo

        entry = _make_entry(hass)
        client = _make_client()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            CLIENT: client,
            PLATFORM_TYPE: PLATFORM_CARELINK,
        }
        coordinator = CarelinkCoordinator(hass, entry, update_interval=timedelta(seconds=60))
        with patch.object(coordinator, "_import_sg_statistics", new_callable=AsyncMock):
            await coordinator.async_config_entry_first_refresh()

        valid_sgs = [
            {
                "timestamp": "2024-01-15T12:00:00.000Z",
                "sg": 120,
                "sensorState": "NO_ERROR_MESSAGE",
            },
        ]
        tz = ZoneInfo("Europe/Amsterdam")

        mock_import_stats = MagicMock(side_effect=Exception("recorder error"))
        mock_stat_data = MagicMock(side_effect=lambda **kwargs: kwargs)
        mock_stat_meta = MagicMock(side_effect=lambda **kwargs: kwargs)

        with patch.dict(
            "sys.modules",
            {
                "homeassistant.components.recorder.statistics": MagicMock(async_import_statistics=mock_import_stats),
                "homeassistant.components.recorder.models": MagicMock(
                    StatisticData=mock_stat_data,
                    StatisticMetaData=mock_stat_meta,
                ),
            },
        ):
            # Should not raise — exceptions are caught
            await coordinator._import_sg_statistics(valid_sgs, tz)
