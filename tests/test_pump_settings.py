"""Tests for pump settings extraction from metadata.lastUpload.settings."""

from __future__ import annotations

import copy
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.carelink.const import (
    DOMAIN,
    TANDEM_CLIENT,
    PLATFORM_TYPE,
    PLATFORM_TANDEM,
    UNAVAILABLE,
    TANDEM_SENSOR_KEY_LAST_UPLOAD,
    TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP,
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
)


async def _setup_coordinator(hass: HomeAssistant, mock_data: dict[str, Any]):
    """Set up a TandemCoordinator with mocked API calls and return it."""
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

    mock_client = AsyncMock()
    mock_client.login = AsyncMock(return_value=True)
    mock_client.get_recent_data = AsyncMock(return_value=mock_data)
    mock_client.get_pump_event_metadata = AsyncMock(
        return_value=[
            {
                "maxDateWithEvents": "2024-01-15T12:00:00",
            }
        ]
    )
    mock_client.close = AsyncMock()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        TANDEM_CLIENT: mock_client,
        PLATFORM_TYPE: PLATFORM_TANDEM,
    }

    coordinator = TandemCoordinator(hass, entry, update_interval=timedelta(seconds=300))

    await coordinator.async_config_entry_first_refresh()
    return coordinator


# ── Settings keys that should all be present ────────────────────────────

ALL_SETTINGS_KEYS = [
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


class TestLastUploadParsing:
    """Tests for the lastUpload dict parsing fix."""

    async def test_last_upload_dict_parsed(self, hass: HomeAssistant, mock_tandem_recent_data):
        """Test that lastUpload as a dict correctly extracts lastUploadedAt."""
        coordinator = await _setup_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_UPLOAD] is not UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] is not UNAVAILABLE

    async def test_last_upload_bare_string_compat(self, hass: HomeAssistant):
        """Test backwards compat: lastUpload as a bare date string still works."""
        data = {
            "pump_metadata": {
                "serialNumber": "12345678",
                "modelNumber": "t:slim X2",
                "softwareVersion": "7.6.0",
                "lastUpload": "/Date(1705320000000)/",
            },
            "pumper_info": {"firstName": "Test", "lastName": "User"},
            "therapy_timeline": None,
            "dashboard_summary": None,
        }
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_UPLOAD] is not UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP] is not UNAVAILABLE

    async def test_last_upload_missing(self, hass: HomeAssistant):
        """Test that missing lastUpload sets UNAVAILABLE."""
        data = {
            "pump_metadata": {
                "serialNumber": "12345678",
                "modelNumber": "t:slim X2",
                "softwareVersion": "7.6.0",
            },
            "pumper_info": {"firstName": "Test", "lastName": "User"},
            "therapy_timeline": None,
            "dashboard_summary": None,
        }
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_UPLOAD] is UNAVAILABLE


class TestPumpSettingsFullData:
    """Tests for pump settings with complete settings data."""

    async def test_active_profile_name(self, hass: HomeAssistant, mock_tandem_recent_data):
        """Test active profile name is resolved from activeIdp."""
        coordinator = await _setup_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE] == "TestProfile"

    async def test_active_profile_attributes(self, hass: HomeAssistant, mock_tandem_recent_data):
        """Test active profile attributes include schedule and insulin duration."""
        coordinator = await _setup_coordinator(hass, mock_tandem_recent_data)

        attrs = coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS]
        assert attrs["profile_name"] == "TestProfile"
        assert attrs["insulin_duration_hours"] == 5.0
        assert attrs["carb_entry_enabled"] is True
        assert len(attrs["schedule"]) == 2

        # First segment: midnight, 1.2 u/hr, ISF 54, CR 10.0, target 110
        seg0 = attrs["schedule"][0]
        assert seg0["time"] == "00:00"
        assert seg0["basal_rate"] == 1.2
        assert seg0["isf_mgdl"] == 54
        assert seg0["carb_ratio"] == 10.0
        assert seg0["target_bg_mgdl"] == 110

        # Second segment: 08:00, 0.8 u/hr
        seg1 = attrs["schedule"][1]
        assert seg1["time"] == "08:00"
        assert seg1["basal_rate"] == 0.8

    async def test_control_iq_settings(self, hass: HomeAssistant, mock_tandem_recent_data):
        """Test Control-IQ settings extraction."""
        coordinator = await _setup_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_ENABLED] == "On"
        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_WEIGHT] == 74
        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_TDI] == 60

    async def test_pump_limits(self, hass: HomeAssistant, mock_tandem_recent_data):
        """Test pump limit conversions (milliunits to units)."""
        coordinator = await _setup_coordinator(hass, mock_tandem_recent_data)

        # maxBolus 14000 -> 14.0 U
        assert coordinator.data[TANDEM_SENSOR_KEY_MAX_BOLUS] == 14.0
        # basalLimit 2000 -> 2.0 U/hr
        assert coordinator.data[TANDEM_SENSOR_KEY_BASAL_LIMIT] == 2.0

    async def test_cgm_alert_thresholds(self, hass: HomeAssistant, mock_tandem_recent_data):
        """Test CGM alert thresholds from cgmSettings."""
        coordinator = await _setup_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_HIGH_ALERT] == 200
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_LOW_ALERT] == 80

    async def test_alert_thresholds(self, hass: HomeAssistant, mock_tandem_recent_data):
        """Test BG and insulin alert thresholds."""
        coordinator = await _setup_coordinator(hass, mock_tandem_recent_data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LOW_BG_THRESHOLD] == 70
        assert coordinator.data[TANDEM_SENSOR_KEY_HIGH_BG_THRESHOLD] == 214
        assert coordinator.data[TANDEM_SENSOR_KEY_LOW_INSULIN_ALERT] == 20

    async def test_all_settings_keys_present(self, hass: HomeAssistant, mock_tandem_recent_data):
        """Test that all pump settings keys are present in coordinator data."""
        coordinator = await _setup_coordinator(hass, mock_tandem_recent_data)

        for key in ALL_SETTINGS_KEYS:
            assert key in coordinator.data, f"Missing key: {key}"
            assert coordinator.data[key] is not UNAVAILABLE, f"Key {key} is UNAVAILABLE"


class TestPumpSettingsMissing:
    """Tests for graceful handling of missing settings data."""

    async def test_no_settings_in_last_upload(self, hass: HomeAssistant):
        """Test that missing settings dict sets all to UNAVAILABLE."""
        data = {
            "pump_metadata": {
                "serialNumber": "12345678",
                "modelNumber": "t:slim X2",
                "softwareVersion": "7.6.0",
                "lastUpload": {
                    "uploadId": 999,
                    "lastUploadedAt": "/Date(1705320000000)/",
                    "settings": None,
                },
            },
            "pumper_info": {"firstName": "Test", "lastName": "User"},
            "therapy_timeline": None,
            "dashboard_summary": None,
        }
        coordinator = await _setup_coordinator(hass, data)

        for key in ALL_SETTINGS_KEYS:
            assert coordinator.data[key] is UNAVAILABLE, f"Key {key} should be UNAVAILABLE"
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS] == {}

    async def test_no_metadata(self, hass: HomeAssistant):
        """Test that missing metadata sets all settings to UNAVAILABLE."""
        data = {
            "pump_metadata": None,
            "pumper_info": None,
            "therapy_timeline": None,
            "dashboard_summary": None,
        }
        coordinator = await _setup_coordinator(hass, data)

        for key in ALL_SETTINGS_KEYS:
            assert coordinator.data[key] is UNAVAILABLE, f"Key {key} should be UNAVAILABLE"

    async def test_missing_control_iq(self, hass: HomeAssistant, mock_tandem_recent_data):
        """Test missing controlIQSettings is handled gracefully."""
        data = copy.deepcopy(mock_tandem_recent_data)
        data["pump_metadata"]["lastUpload"]["settings"]["controlIQSettings"] = None
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_ENABLED] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_WEIGHT] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_TDI] is UNAVAILABLE
        # Other settings should still work
        assert coordinator.data[TANDEM_SENSOR_KEY_MAX_BOLUS] == 14.0

    async def test_missing_profiles(self, hass: HomeAssistant, mock_tandem_recent_data):
        """Test missing profiles section is handled gracefully."""
        data = copy.deepcopy(mock_tandem_recent_data)
        data["pump_metadata"]["lastUpload"]["settings"]["profiles"] = None
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS] == {}
        # Other settings should still work
        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_ENABLED] == "On"

    async def test_control_iq_off(self, hass: HomeAssistant, mock_tandem_recent_data):
        """Test Control-IQ ClosedLoop=0 reports 'Off'."""
        data = copy.deepcopy(mock_tandem_recent_data)
        data["pump_metadata"]["lastUpload"]["settings"]["controlIQSettings"]["ClosedLoop"] = 0
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_ENABLED] == "Off"

    async def test_active_idp_no_match(self, hass: HomeAssistant, mock_tandem_recent_data):
        """Test that an activeIdp with no matching profile returns UNAVAILABLE."""
        data = copy.deepcopy(mock_tandem_recent_data)
        data["pump_metadata"]["lastUpload"]["settings"]["profiles"]["activeIdp"] = 99
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE] is UNAVAILABLE

    async def test_empty_segments_filtered(self, hass: HomeAssistant):
        """Test that empty (zeroed) tDependentSegs slots are filtered out."""
        data = {
            "pump_metadata": {
                "serialNumber": "12345678",
                "modelNumber": "t:slim X2",
                "softwareVersion": "7.6.0",
                "lastUpload": {
                    "uploadId": 999,
                    "lastUploadedAt": "/Date(1705320000000)/",
                    "settings": {
                        "profiles": {
                            "activeIdp": 0,
                            "profile": [
                                {
                                    "name": "Test",
                                    "idp": 0,
                                    "insulinDuration": 300,
                                    "carbEntry": 1,
                                    "tDependentSegs": [
                                        {
                                            "startTime": 0,
                                            "basalRate": 1000,
                                            "isf": 50,
                                            "carbRatio": 10000,
                                            "targetBg": 110,
                                        },
                                        # Empty trailing slot
                                        {
                                            "startTime": 0,
                                            "basalRate": 0,
                                            "isf": 0,
                                            "carbRatio": 0,
                                            "targetBg": 0,
                                        },
                                    ],
                                },
                            ],
                        },
                        "controlIQSettings": {"ClosedLoop": 1, "Weight": 70, "TotalDailyInsulin": 50},
                        "pumpSettings": {"basalLimit": 2000, "maxBolus": 10000},
                        "alertsAndReminders": {"lowInsulinThreshold": 15, "lowBgThreshold": 65, "highBgThreshold": 200},
                        "cgmSettings": {
                            "highGlucoseAlert": {"mgPerDl": 180, "enabled": 1},
                            "lowGlucoseAlert": {"mgPerDl": 70, "enabled": 1},
                        },
                    },
                },
            },
            "pumper_info": {"firstName": "Test", "lastName": "User"},
            "therapy_timeline": None,
            "dashboard_summary": None,
        }
        coordinator = await _setup_coordinator(hass, data)

        attrs = coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_PROFILE_ATTRS]
        # Only the real segment should be present (not the zeroed one)
        assert len(attrs["schedule"]) == 1
        assert attrs["schedule"][0]["basal_rate"] == 1.0
