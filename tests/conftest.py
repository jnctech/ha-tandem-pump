"""Fixtures for Carelink / Tandem integration tests."""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.carelink.api import CarelinkClient
from custom_components.carelink.nightscout_uploader import NightscoutUploader
from custom_components.carelink.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in all tests."""
    yield


# ── Carelink (Medtronic) fixtures ──────────────────────────────────────────


@pytest.fixture
def mock_token_data() -> dict[str, str]:
    """Return mock token data.

    Note: The JWT token contains a hardcoded expiration (exp: 9999999999 = Nov 2286)
    to ensure tests don't fail due to token expiration. The payload contains:
    - exp: 9999999999
    - token_details: {"country": "NL", "preferred_username": "testuser"}
    """
    return {
        "access_token": (
            "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJleHAiOjk5OTk5OTk5OTksInRva2VuX2RldGFpbHMiOnsiY291bnRyeSI6Ik5MIiwicH"
            "JlZmVycmVkX3VzZXJuYW1lIjoidGVzdHVzZXIifX0.fake"
        ),
        "refresh_token": "mock_refresh_token",
        "client_id": "mock_client_id",
        "client_secret": "mock_client_secret",
        "mag-identifier": "mock_mag_identifier",
    }


@pytest.fixture
def mock_recent_data() -> dict[str, Any]:
    """Return mock recent data from Carelink API."""
    return {
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


@pytest.fixture
def mock_carelink_client(mock_token_data: dict[str, str], tmp_path) -> CarelinkClient:
    """Return a CarelinkClient instance for testing."""
    return CarelinkClient(
        carelink_refresh_token=mock_token_data["refresh_token"],
        carelink_token=mock_token_data["access_token"],
        client_id=mock_token_data["client_id"],
        client_secret=mock_token_data["client_secret"],
        mag_identifier=mock_token_data["mag-identifier"],
        carelink_patient_id="mock_patient_id",
        config_path=str(tmp_path),
    )


@pytest.fixture
def mock_nightscout_uploader() -> NightscoutUploader:
    """Return a NightscoutUploader instance for testing."""
    return NightscoutUploader(
        nightscout_url="https://nightscout.example.com",
        nightscout_secret="mock_api_secret",
    )


# ── Config entry fixtures ─────────────────────────────────────────────────


@pytest.fixture
def mock_carelink_config_entry() -> MockConfigEntry:
    """Return a MockConfigEntry for Carelink (Medtronic)."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Carelink",
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


@pytest.fixture
def mock_tandem_config_entry() -> MockConfigEntry:
    """Return a MockConfigEntry for Tandem t:slim."""
    return MockConfigEntry(
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


# ── Tandem mock data fixtures ─────────────────────────────────────────────


@pytest.fixture
def mock_tandem_recent_data() -> dict[str, Any]:
    """Return mock data from the Tandem Source API."""
    return {
        "pump_metadata": {
            "serialNumber": "12345678",
            "modelNumber": "t:slim X2",
            "softwareVersion": "7.6.0",
            "lastUpload": "/Date(1705320000000)/",
        },
        "pumper_info": {
            "firstName": "Test",
            "lastName": "User",
            "pumperId": "abc-123",
        },
        "therapy_timeline": {
            "cgm": [
                {
                    "EventDateTime": "/Date(1705320000000)/",
                    "Readings": [
                        {"Value": 120, "Type": "EGV"},
                    ],
                },
            ],
            "bolus": [
                {
                    "CompletionDateTime": "/Date(1705318000000)/",
                    "RequestDateTime": "/Date(1705317800000)/",
                    "InsulinDelivered": 3.5,
                    "RequestedInsulin": 3.5,
                    "Description": "Standard",
                    "CarbSize": 45,
                    "BG": 120,
                    "IOB": 2.1,
                    "CompletionStatusID": "Completed",
                },
            ],
            "basal": [
                {
                    "EventDateTime": "/Date(1705320000000)/",
                    "BasalRate": 0.85,
                    "Type": "Control-IQ",
                },
            ],
        },
        "dashboard_summary": {
            "averageReading": 135,
            "timeInRangePercent": 72.5,
            "cgmInactivePercent": 5.0,
        },
    }


@pytest.fixture
def mock_tandem_recent_data_minimal() -> dict[str, Any]:
    """Return mock Tandem data with only metadata (no ControlIQ)."""
    return {
        "pump_metadata": {
            "serialNumber": "12345678",
            "modelNumber": "t:slim X2",
            "softwareVersion": "7.6.0",
            "lastUpload": "/Date(1705320000000)/",
        },
        "pumper_info": {
            "firstName": "Test",
            "lastName": "User",
        },
        "therapy_timeline": None,
        "dashboard_summary": None,
    }
