"""Fixtures for Tandem integration tests."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.syrupy import HomeAssistantSnapshotExtension
from syrupy.assertion import SnapshotAssertion

from custom_components.tandem.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading custom integrations in all tests."""
    yield


@pytest.fixture
def snapshot(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    """Return a syrupy snapshot assertion using the HA extension (.ambr files)."""
    return snapshot.use_extension(HomeAssistantSnapshotExtension)


# ── Recorder statistics capture ───────────────────────────────────────────


@pytest.fixture
def mock_import():
    """Patch the real recorder ``async_import_statistics`` and yield the mock.

    Deliberately keeps Home Assistant's real ``StatisticMetaData`` /
    ``StatisticData`` / ``StatisticMeanType`` in play — only the side-effectful
    import boundary is intercepted. Substituting fake recorder modules (the old
    approach) hid the real TypedDict contract, so when the recorder API added the
    required ``mean_type`` / ``unit_class`` keys the tests kept passing against a
    stale stand-in. Patching the real symbol means such a drift fails loudly.

    Captured calls carry the real ``StatisticMetaData``/``StatisticData`` dicts,
    so assert with subscript access (``meta["statistic_id"]``, ``stats[0]["mean"]``).
    """
    mock = MagicMock()
    with patch(
        "homeassistant.components.recorder.statistics.async_import_statistics",
        mock,
    ):
        yield mock


# ── Config entry fixtures ─────────────────────────────────────────────────


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
            "lastUpload": {
                "uploadId": 999,
                "lastUploadedAt": "/Date(1705320000000)/",
                "settings": {
                    "profiles": {
                        "activeIdp": 0,
                        "profile": [
                            {
                                "name": "TestProfile",
                                "idp": 0,
                                "insulinDuration": 300,
                                "carbEntry": 1,
                                "tDependentSegs": [
                                    {
                                        "startTime": 0,
                                        "basalRate": 1200,
                                        "isf": 54,
                                        "carbRatio": 10000,
                                        "targetBg": 110,
                                    },
                                    {
                                        "startTime": 480,
                                        "basalRate": 800,
                                        "isf": 72,
                                        "carbRatio": 12000,
                                        "targetBg": 110,
                                    },
                                ],
                            },
                            {
                                "name": "Sick",
                                "idp": 1,
                                "insulinDuration": 300,
                                "carbEntry": 1,
                                "tDependentSegs": [
                                    {
                                        "startTime": 0,
                                        "basalRate": 600,
                                        "isf": 72,
                                        "carbRatio": 15000,
                                        "targetBg": 120,
                                    },
                                ],
                            },
                        ],
                    },
                    "controlIqSettings": {
                        "closedLoop": 1,
                        "weight": 74,
                        "weightUnit": 2,
                        "totalDailyInsulin": 60,
                        "sleepSchedule0": {
                            "activeDays": 127,
                            "startTime": 1439,
                            "endTime": 360,
                            "enabled": 1,
                        },
                    },
                    "pumpSettings": {
                        "lowInsulinThreshold": 20,
                        "cannulaPrimeSize": 0,
                        "autoShutdownEnabled": 0,
                        "status": 0,
                    },
                    "globalMaxBolusSettings": {
                        "maxBolus": 14000,
                        "maxBolusDefault": 25000,
                    },
                    "basalLimitSettings": {
                        "basalLimit": 2000,
                        "basalLimitDefault": 15000,
                    },
                    "reminders": {
                        "lowBgThreshold": 70,
                        "highBgThreshold": 214,
                        "siteChangeDays": 3,
                        "status": 0,
                    },
                    "cgmSettings": {
                        "highGlucoseAlertMgPerDl": 200,
                        "highGlucoseAlertEnabled": 1,
                        "lowGlucoseAlertMgPerDl": 80,
                        "lowGlucoseAlertEnabled": 1,
                        "cgmSensorType": 1,
                    },
                },
            },
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
            "lastUpload": {
                "uploadId": 999,
                "lastUploadedAt": "/Date(1705320000000)/",
                "settings": None,
            },
        },
        "pumper_info": {
            "firstName": "Test",
            "lastName": "User",
        },
        "therapy_timeline": None,
        "dashboard_summary": None,
    }


# ── Shared Tandem coordinator factory ─────────────────────────────────────


async def make_tandem_coordinator(
    hass: HomeAssistant,
    pump_events: list[dict] | None = None,
):
    """Create a minimal TandemCoordinator with specific pump_events.

    Shared factory used by test_additional_sensors and test_extended_statistics
    to avoid duplicating the coordinator setup boilerplate.
    """
    from custom_components.tandem import TandemCoordinator

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
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)

    mock_client = AsyncMock()
    mock_client.login = AsyncMock(return_value=True)
    mock_client.get_recent_data = AsyncMock(
        return_value={
            "pump_metadata": {
                "serialNumber": "12345678",
                "modelNumber": "t:slim X2",
                "softwareVersion": "7.6.0",
                "lastUpload": "/Date(1705320000000)/",
            },
            "pumper_info": {"firstName": "Test", "lastName": "User"},
            "pump_events": pump_events if pump_events is not None else [],
            "therapy_timeline": None,
            "dashboard_summary": None,
        }
    )
    mock_client.get_pump_event_metadata = AsyncMock(return_value=[{"maxDateWithEvents": "2026-03-01T12:00:00"}])
    mock_client.close = AsyncMock()

    coordinator = TandemCoordinator(hass, entry, mock_client, update_interval=timedelta(seconds=300))
    # As async_setup_entry: the short-window first refresh, then the full-window
    # backfill (the 7-day CGM summary is only computed on the full window).
    await coordinator.async_config_entry_first_refresh()
    await coordinator.async_backfill_full_history()
    # The backfill swallows its own errors; a successful one caches maxDate.
    assert coordinator._last_max_date is not None, "full-window backfill failed"
    return coordinator
