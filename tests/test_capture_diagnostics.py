"""Tests for the capture_diagnostics service handler."""

from __future__ import annotations

import json
import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant, ServiceCall

from custom_components.carelink import _handle_capture_diagnostics
from custom_components.carelink.const import COORDINATOR, DOMAIN


def _make_coordinator_mock(
    *,
    timezone="UTC",
    data=None,
    metadata_list=None,
    pumper_info=None,
    pump_events=None,
    login_error=None,
    metadata_error=None,
    pumper_error=None,
    events_error=None,
):
    """Build a mock coordinator with configurable API responses."""
    coordinator = MagicMock()
    coordinator.timezone = timezone
    coordinator.data = data

    client = AsyncMock()
    if login_error:
        client.login.side_effect = login_error
    else:
        client.login.return_value = True

    if metadata_error:
        client.get_pump_event_metadata.side_effect = metadata_error
    else:
        client.get_pump_event_metadata.return_value = metadata_list or []

    if pumper_error:
        client.get_pumper_info.side_effect = pumper_error
    else:
        client.get_pumper_info.return_value = pumper_info or {}

    if events_error:
        client.get_pump_events.side_effect = events_error
    else:
        client.get_pump_events.return_value = pump_events or []

    coordinator.client = client
    return coordinator


async def _run_diagnostics(hass, entry_id, mock_call, coordinator, tmp_path):
    """Run _handle_capture_diagnostics with file output to tmp_path."""
    hass.data.setdefault(DOMAIN, {})[entry_id] = {COORDINATOR: coordinator}
    out_file = str(tmp_path / "carelink_diagnostics_test.json")

    with (
        patch.object(hass.config, "path", return_value=out_file),
        patch.dict("sys.modules", {"aiofiles": None}),
    ):
        await _handle_capture_diagnostics(hass, entry_id, mock_call)

    if os.path.exists(out_file):
        return json.loads(open(out_file).read())
    return None


@pytest.fixture
def mock_call():
    """Return a mock ServiceCall."""
    return MagicMock(spec=ServiceCall)


@pytest.fixture
def entry_id():
    return "test_entry_123"


class TestCaptureDiagnosticsLoginFailure:
    """Test early return when login fails."""

    async def test_login_failure_returns_early(self, hass: HomeAssistant, mock_call, entry_id, tmp_path):
        coordinator = _make_coordinator_mock(login_error=Exception("auth failed"))
        result = await _run_diagnostics(hass, entry_id, mock_call, coordinator, tmp_path)

        assert result is None
        coordinator.client.get_pump_event_metadata.assert_not_called()


class TestCaptureDiagnosticsHappyPath:
    """Test successful diagnostics capture with full data."""

    async def test_writes_snapshot_with_metadata_and_events(self, hass: HomeAssistant, mock_call, entry_id, tmp_path):
        metadata = [{"tconnectDeviceId": 12345, "serialNumber": "SN123"}]
        pumper = {"pumperId": "abc-123", "firstName": "Test"}
        events = [
            {"event_name": "CGM", "event_id": 7, "timestamp": datetime(2026, 3, 13, 12, 0)},
            {"event_name": "CGM", "event_id": 7, "timestamp": datetime(2026, 3, 13, 12, 5)},
            {"event_name": "Bolus", "event_id": 11, "value": 3.5},
        ]
        sensor_data = {
            "glucose": 120,
            "iob": 2.5,
            "last_upload": datetime(2026, 3, 13, 10, 0),
            "missing_field": None,
        }

        coordinator = _make_coordinator_mock(
            metadata_list=metadata,
            pumper_info=pumper,
            pump_events=events,
            data=sensor_data,
        )
        snapshot = await _run_diagnostics(hass, entry_id, mock_call, coordinator, tmp_path)

        assert snapshot is not None
        assert "captured_at" in snapshot

        # Metadata captured and sanitised
        assert "pump_event_metadata" in snapshot
        assert snapshot["pump_event_metadata"][0]["tconnectDeviceId"] == 12345

        # Pumper info captured
        assert "pumper_info" in snapshot

        # Event summary
        assert snapshot["pump_events_summary"]["total_events"] == 3
        assert snapshot["pump_events_summary"]["event_counts"]["CGM"] == 2
        assert snapshot["pump_events_summary"]["event_counts"]["Bolus"] == 1

        # Event samples — one per type
        assert len(snapshot["pump_events_samples"]) == 2
        sample_names = [s["event_name"] for s in snapshot["pump_events_samples"]]
        assert "CGM" in sample_names
        assert "Bolus" in sample_names

        # Sensor state captured
        assert snapshot["current_sensor_state"]["glucose"] == 120
        assert snapshot["current_sensor_state"]["missing_field"] == "UNAVAILABLE"
        assert "2026-03-13" in snapshot["current_sensor_state"]["last_upload"]


class TestCaptureDiagnosticsEmptyEvents:
    """Test diagnostics when pump events are empty."""

    async def test_empty_events_recorded(self, hass: HomeAssistant, mock_call, entry_id, tmp_path):
        metadata = [{"tconnectDeviceId": 99}]
        coordinator = _make_coordinator_mock(metadata_list=metadata, pump_events=[])
        snapshot = await _run_diagnostics(hass, entry_id, mock_call, coordinator, tmp_path)

        assert snapshot is not None
        assert snapshot["pump_events_summary"]["total_events"] == 0


class TestCaptureDiagnosticsApiErrors:
    """Test graceful handling of API errors during capture."""

    async def test_metadata_error_recorded(self, hass: HomeAssistant, mock_call, entry_id, tmp_path):
        coordinator = _make_coordinator_mock(metadata_error=Exception("metadata timeout"))
        snapshot = await _run_diagnostics(hass, entry_id, mock_call, coordinator, tmp_path)

        assert snapshot is not None
        assert "metadata timeout" in snapshot["pump_event_metadata_error"]

    async def test_pumper_info_error_recorded(self, hass: HomeAssistant, mock_call, entry_id, tmp_path):
        coordinator = _make_coordinator_mock(pumper_error=Exception("pumper not found"))
        snapshot = await _run_diagnostics(hass, entry_id, mock_call, coordinator, tmp_path)

        assert snapshot is not None
        assert "pumper not found" in snapshot["pumper_info_error"]

    async def test_events_error_recorded(self, hass: HomeAssistant, mock_call, entry_id, tmp_path):
        metadata = [{"tconnectDeviceId": 42}]
        coordinator = _make_coordinator_mock(metadata_list=metadata, events_error=Exception("event decode failed"))
        snapshot = await _run_diagnostics(hass, entry_id, mock_call, coordinator, tmp_path)

        assert snapshot is not None
        assert "event decode failed" in snapshot["pump_events_error"]


class TestCaptureDiagnosticsMetadataFormats:
    """Test device_id extraction from different metadata formats."""

    async def test_metadata_as_dict(self, hass: HomeAssistant, mock_call, entry_id, tmp_path):
        """When metadata is sanitised as a dict instead of list."""
        metadata_dict = {"tconnectDeviceId": 77, "serialNumber": "SN-DICT"}
        coordinator = _make_coordinator_mock(
            metadata_list=metadata_dict,
            pump_events=[{"event_name": "CGM", "event_id": 7}],
        )
        snapshot = await _run_diagnostics(hass, entry_id, mock_call, coordinator, tmp_path)

        assert snapshot is not None
        assert "pump_events_summary" in snapshot

    async def test_no_device_id_skips_events(self, hass: HomeAssistant, mock_call, entry_id, tmp_path):
        """When metadata has no tconnectDeviceId, events are skipped."""
        coordinator = _make_coordinator_mock(metadata_list=[{"serialNumber": "SN-NO-ID"}])
        snapshot = await _run_diagnostics(hass, entry_id, mock_call, coordinator, tmp_path)

        assert snapshot is not None
        assert "pump_events_summary" not in snapshot
        coordinator.client.get_pump_events.assert_not_called()
