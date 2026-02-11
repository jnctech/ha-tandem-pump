"""Tests for the TandemCoordinator data parsing."""
from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.carelink.const import (
    DOMAIN,
    TANDEM_CLIENT,
    PLATFORM_TYPE,
    PLATFORM_TANDEM,
    COORDINATOR,
    UNAVAILABLE,
    DEVICE_PUMP_SERIAL,
    DEVICE_PUMP_MODEL,
    DEVICE_PUMP_NAME,
    DEVICE_PUMP_MANUFACTURER,
    TANDEM_SENSOR_KEY_LASTSG_MMOL,
    TANDEM_SENSOR_KEY_LASTSG_MGDL,
    TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP,
    TANDEM_SENSOR_KEY_SG_DELTA,
    TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS,
    TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP,
    TANDEM_SENSOR_KEY_BASAL_RATE,
    TANDEM_SENSOR_KEY_ACTIVE_INSULIN,
    TANDEM_SENSOR_KEY_LAST_UPLOAD,
    TANDEM_SENSOR_KEY_SOFTWARE_VERSION,
    TANDEM_SENSOR_KEY_PUMP_SERIAL_INFO,
    TANDEM_SENSOR_KEY_PUMP_MODEL_INFO,
    TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL,
    TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL,
    TANDEM_SENSOR_KEY_TIME_IN_RANGE,
    TANDEM_SENSOR_KEY_CGM_USAGE,
    TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS,
    TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP,
    TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS,
)


async def _setup_tandem_coordinator(
    hass: HomeAssistant,
    mock_recent_data: dict[str, Any],
):
    """Set up a TandemCoordinator with mocked API calls and return the coordinator."""
    from custom_components.carelink import TandemCoordinator

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Tandem t:slim",
        data={
            "platform_type": "tandem",
            "tandem_email": "test@example.com",
            "tandem_password": "testpassword",
            "tandem_region": "EU",
            "scan_interval": 300,
        },
    )
    entry.add_to_hass(hass)

    # Set up the mock client in hass.data
    mock_client = AsyncMock()
    mock_client.login = AsyncMock(return_value=True)
    mock_client.get_recent_data = AsyncMock(return_value=mock_recent_data)
    mock_client.close = AsyncMock()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        TANDEM_CLIENT: mock_client,
        PLATFORM_TYPE: PLATFORM_TANDEM,
    }

    coordinator = TandemCoordinator(
        hass, entry, update_interval=timedelta(seconds=300)
    )

    await coordinator.async_config_entry_first_refresh()
    return coordinator


class TestTandemCoordinatorFullData:
    """Tests for TandemCoordinator with full data (metadata + ControlIQ)."""

    async def test_device_info_from_metadata(
        self, hass: HomeAssistant, mock_tandem_recent_data
    ):
        """Test device info is populated from pump metadata."""
        coordinator = await _setup_tandem_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[DEVICE_PUMP_SERIAL] == "12345678"
        assert coordinator.data[DEVICE_PUMP_MODEL] == "t:slim X2"
        assert coordinator.data[DEVICE_PUMP_MANUFACTURER] == "Tandem Diabetes Care"

    async def test_pump_name_from_pumper_info(
        self, hass: HomeAssistant, mock_tandem_recent_data
    ):
        """Test pump name is populated from pumper info."""
        coordinator = await _setup_tandem_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[DEVICE_PUMP_NAME] == "Test User"

    async def test_sensor_keys_from_metadata(
        self, hass: HomeAssistant, mock_tandem_recent_data
    ):
        """Test sensor-level metadata values."""
        coordinator = await _setup_tandem_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_SERIAL_INFO] == "12345678"
        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_MODEL_INFO] == "t:slim X2"
        assert coordinator.data[TANDEM_SENSOR_KEY_SOFTWARE_VERSION] == "7.6.0"

    async def test_last_upload_parsed(
        self, hass: HomeAssistant, mock_tandem_recent_data
    ):
        """Test that /Date()/ format last upload is parsed correctly."""
        coordinator = await _setup_tandem_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_UPLOAD] is not UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] is not UNAVAILABLE

    async def test_cgm_reading_parsed(
        self, hass: HomeAssistant, mock_tandem_recent_data
    ):
        """Test CGM reading from therapy timeline."""
        coordinator = await _setup_tandem_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == 120
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MMOL] == round(120 * 0.0555, 2)

    async def test_bolus_data_parsed(
        self, hass: HomeAssistant, mock_tandem_recent_data
    ):
        """Test bolus data from therapy timeline."""
        coordinator = await _setup_tandem_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] == 3.5
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] is not UNAVAILABLE

    async def test_iob_from_bolus(
        self, hass: HomeAssistant, mock_tandem_recent_data
    ):
        """Test IOB is extracted from last bolus entry."""
        coordinator = await _setup_tandem_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] == 2.1

    async def test_meal_bolus_detected(
        self, hass: HomeAssistant, mock_tandem_recent_data
    ):
        """Test meal bolus is identified by CarbSize > 0."""
        coordinator = await _setup_tandem_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] == 3.5

    async def test_basal_rate_parsed(
        self, hass: HomeAssistant, mock_tandem_recent_data
    ):
        """Test basal rate from therapy timeline."""
        coordinator = await _setup_tandem_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_BASAL_RATE] == 0.85

    async def test_control_iq_status(
        self, hass: HomeAssistant, mock_tandem_recent_data
    ):
        """Test Control-IQ status from basal type."""
        coordinator = await _setup_tandem_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] == "Control-IQ"

    async def test_dashboard_summary_parsed(
        self, hass: HomeAssistant, mock_tandem_recent_data
    ):
        """Test dashboard summary statistics."""
        coordinator = await _setup_tandem_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] == 135
        assert coordinator.data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] == round(135 * 0.0555, 2)
        assert coordinator.data[TANDEM_SENSOR_KEY_TIME_IN_RANGE] == 72.5
        # CGM usage = 100 - cgmInactivePercent = 100 - 5.0 = 95.0
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_USAGE] == 95.0


class TestTandemCoordinatorMinimalData:
    """Tests for TandemCoordinator when ControlIQ data is not available."""

    async def test_metadata_sensors_populated(
        self, hass: HomeAssistant, mock_tandem_recent_data_minimal
    ):
        """Test that metadata sensors still work without ControlIQ data."""
        coordinator = await _setup_tandem_coordinator(
            hass, mock_tandem_recent_data_minimal
        )

        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_SERIAL_INFO] == "12345678"
        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_MODEL_INFO] == "t:slim X2"
        assert coordinator.data[TANDEM_SENSOR_KEY_SOFTWARE_VERSION] == "7.6.0"

    async def test_cgm_sensors_unavailable(
        self, hass: HomeAssistant, mock_tandem_recent_data_minimal
    ):
        """Test CGM sensors show UNAVAILABLE when timeline is None."""
        coordinator = await _setup_tandem_coordinator(
            hass, mock_tandem_recent_data_minimal
        )

        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MMOL] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_SG_DELTA] is UNAVAILABLE

    async def test_bolus_sensors_unavailable(
        self, hass: HomeAssistant, mock_tandem_recent_data_minimal
    ):
        """Test bolus sensors show UNAVAILABLE when timeline is None."""
        coordinator = await _setup_tandem_coordinator(
            hass, mock_tandem_recent_data_minimal
        )

        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] is UNAVAILABLE

    async def test_basal_sensors_unavailable(
        self, hass: HomeAssistant, mock_tandem_recent_data_minimal
    ):
        """Test basal sensors show UNAVAILABLE when timeline is None."""
        coordinator = await _setup_tandem_coordinator(
            hass, mock_tandem_recent_data_minimal
        )

        assert coordinator.data[TANDEM_SENSOR_KEY_BASAL_RATE] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] is UNAVAILABLE

    async def test_summary_sensors_unavailable(
        self, hass: HomeAssistant, mock_tandem_recent_data_minimal
    ):
        """Test summary sensors show UNAVAILABLE when dashboard is None."""
        coordinator = await _setup_tandem_coordinator(
            hass, mock_tandem_recent_data_minimal
        )

        assert coordinator.data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_TIME_IN_RANGE] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_USAGE] is UNAVAILABLE


class TestTandemCoordinatorNoMetadata:
    """Tests for TandemCoordinator when even metadata is missing."""

    async def test_defaults_when_no_metadata(self, hass: HomeAssistant):
        """Test that sensible defaults are used when metadata is missing."""
        empty_data = {
            "therapy_timeline": None,
            "dashboard_summary": None,
        }
        coordinator = await _setup_tandem_coordinator(hass, empty_data)

        assert coordinator.data[DEVICE_PUMP_SERIAL] == "unknown"
        assert coordinator.data[DEVICE_PUMP_MODEL] == "t:slim X2"
        assert coordinator.data[DEVICE_PUMP_NAME] == "Tandem Pump"
        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_SERIAL_INFO] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_MODEL_INFO] is UNAVAILABLE


class TestTandemCoordinatorSgDelta:
    """Tests for glucose delta calculation across updates."""

    async def test_delta_unavailable_on_first_update(
        self, hass: HomeAssistant, mock_tandem_recent_data
    ):
        """Test delta is UNAVAILABLE on first coordinator update."""
        coordinator = await _setup_tandem_coordinator(hass, mock_tandem_recent_data)

        # First update: no previous reading, so delta is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_SG_DELTA] is UNAVAILABLE

    async def test_delta_calculated_on_second_update(
        self, hass: HomeAssistant
    ):
        """Test delta is calculated between consecutive updates."""
        from custom_components.carelink import TandemCoordinator

        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                "platform_type": "tandem",
                "tandem_email": "test@example.com",
                "tandem_password": "testpassword",
                "tandem_region": "EU",
                "scan_interval": 300,
            },
        )
        entry.add_to_hass(hass)

        # First response: SG = 120
        first_data = {
            "pump_metadata": {"serialNumber": "SN1", "modelNumber": "M1"},
            "therapy_timeline": {
                "cgm": [{
                    "EventDateTime": "/Date(1705320000000)/",
                    "Readings": [{"Value": 120, "Type": "EGV"}],
                }],
                "bolus": [],
                "basal": [],
            },
            "dashboard_summary": None,
        }
        # Second response: SG = 135
        second_data = {
            "pump_metadata": {"serialNumber": "SN1", "modelNumber": "M1"},
            "therapy_timeline": {
                "cgm": [{
                    "EventDateTime": "/Date(1705320300000)/",
                    "Readings": [{"Value": 135, "Type": "EGV"}],
                }],
                "bolus": [],
                "basal": [],
            },
            "dashboard_summary": None,
        }

        mock_client = AsyncMock()
        mock_client.login = AsyncMock(return_value=True)
        mock_client.get_recent_data = AsyncMock(side_effect=[first_data, second_data])
        mock_client.close = AsyncMock()

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: mock_client,
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }

        coordinator = TandemCoordinator(
            hass, entry, update_interval=timedelta(seconds=300)
        )

        # First refresh
        await coordinator.async_config_entry_first_refresh()
        assert coordinator.data[TANDEM_SENSOR_KEY_SG_DELTA] is UNAVAILABLE

        # Second refresh
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        # Delta should be 135 - 120 = 15
        assert coordinator.data[TANDEM_SENSOR_KEY_SG_DELTA] == 15.0
