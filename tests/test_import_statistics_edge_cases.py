"""Tests for _import_statistics edge cases: null timestamps, zero values, exceptions."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.carelink.const import DOMAIN, PLATFORM_TANDEM, PLATFORM_TYPE, TANDEM_CLIENT


# -- Mock stat data classes ------------------------------------------------


@dataclass
class _MockStatisticData:
    """Lightweight stand-in for homeassistant.components.recorder.models.StatisticData."""

    start: Any = None
    mean: Any = None
    min: Any = None
    max: Any = None
    state: Any = None
    sum: Any = None


@dataclass
class _MockStatisticMetaData:
    """Lightweight stand-in for homeassistant.components.recorder.models.StatisticMetaData."""

    has_mean: bool = True
    has_sum: bool = False
    name: str = ""
    source: str = ""
    statistic_id: str = ""
    unit_of_measurement: str = ""


# -- Fixture ---------------------------------------------------------------


@pytest.fixture
def mock_import():
    """Install fake recorder modules and yield the mock async_import_statistics.

    Automatically restores original sys.modules on teardown.
    """
    mock_fn = MagicMock()

    recorder_mod = types.ModuleType("homeassistant.components.recorder")
    stats_mod = types.ModuleType("homeassistant.components.recorder.statistics")
    models_mod = types.ModuleType("homeassistant.components.recorder.models")

    stats_mod.async_import_statistics = mock_fn
    models_mod.StatisticData = _MockStatisticData
    models_mod.StatisticMetaData = _MockStatisticMetaData

    keys = [
        "homeassistant.components.recorder",
        "homeassistant.components.recorder.statistics",
        "homeassistant.components.recorder.models",
    ]
    saved = {k: sys.modules.get(k) for k in keys}
    sys.modules["homeassistant.components.recorder"] = recorder_mod
    sys.modules["homeassistant.components.recorder.statistics"] = stats_mod
    sys.modules["homeassistant.components.recorder.models"] = models_mod

    yield mock_fn

    for k in keys:
        if saved[k] is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = saved[k]


# -- Helpers ---------------------------------------------------------------

_BASE_TS = datetime(2026, 3, 1, 12, 0, 0)


async def _make_coordinator(hass: HomeAssistant):
    """Create a minimal TandemCoordinator wired to hass (no network calls)."""
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
            "pump_events": [],
            "therapy_timeline": None,
            "dashboard_summary": None,
        }
    )
    mock_client.get_pump_event_metadata = AsyncMock(return_value=[{"maxDateWithEvents": "2026-03-01T12:00:00"}])
    mock_client.close = AsyncMock()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        TANDEM_CLIENT: mock_client,
        PLATFORM_TYPE: PLATFORM_TANDEM,
    }

    coordinator = TandemCoordinator(hass, entry, update_interval=timedelta(seconds=300))
    await coordinator.async_config_entry_first_refresh()
    return coordinator


# ===========================================================================
# Tests: null / missing timestamps
# ===========================================================================


class TestNullTimestampHandling:
    """Events with null or missing timestamps must be silently skipped."""

    async def test_null_timestamp_skipped(self, hass: HomeAssistant, mock_import):
        """Event with timestamp=None produces no statistics."""
        coordinator = await _make_coordinator(hass)
        events = [{"event_id": 256, "timestamp": None, "glucose_mgdl": 120}]
        await coordinator._import_statistics(events)
        assert mock_import.call_count == 0

    async def test_missing_timestamp_key_skipped(self, hass: HomeAssistant, mock_import):
        """Event with no timestamp key at all produces no statistics."""
        coordinator = await _make_coordinator(hass)
        events = [{"event_id": 256, "glucose_mgdl": 120}]
        await coordinator._import_statistics(events)
        assert mock_import.call_count == 0


# ===========================================================================
# Tests: zero / None value guards
# ===========================================================================


class TestZeroAndNoneValueGuards:
    """Zero-glucose, None-IOB and similar guard branches are skipped correctly."""

    async def test_cgm_zero_glucose_excluded(self, hass: HomeAssistant, mock_import):
        """CGM event with glucose_mgdl=0 is not imported."""
        coordinator = await _make_coordinator(hass)
        events = [{"event_id": 256, "timestamp": _BASE_TS, "glucose_mgdl": 0}]
        await coordinator._import_statistics(events)
        assert mock_import.call_count == 0

    async def test_iob_none_skips_iob_stat(self, hass: HomeAssistant, mock_import):
        """IOB=None skips the IOB stat; completed bolus is still imported."""
        coordinator = await _make_coordinator(hass)
        events = [
            {
                "event_id": 20,
                "timestamp": _BASE_TS,
                "iob": None,
                "completion_status": 3,
                "insulin_delivered": 2.5,
            }
        ]
        await coordinator._import_statistics(events)

        stat_ids = {c[0][1].statistic_id for c in mock_import.call_args_list}
        assert f"sensor.{DOMAIN}_active_insulin_iob" not in stat_ids
        assert f"sensor.{DOMAIN}_total_bolus" in stat_ids


# ===========================================================================
# Tests: exception resilience
# ===========================================================================


class TestImportExceptionResilience:
    """A failure in one stat-type import must not prevent the others."""

    async def test_exception_in_first_import_does_not_stop_others(self, hass: HomeAssistant, mock_import):
        """Exception raised by async_import_statistics is caught; remaining stats proceed."""
        coordinator = await _make_coordinator(hass)
        # First call (CGM) raises; second call (carbs) should still run.
        mock_import.side_effect = [Exception("recorder unavailable"), None]
        events = [
            {"event_id": 256, "timestamp": _BASE_TS, "glucose_mgdl": 120},
            {
                "event_id": 48,
                "timestamp": _BASE_TS - timedelta(minutes=10),
                "carbs": 30.0,
            },
        ]
        await coordinator._import_statistics(events)
        assert mock_import.call_count == 2


# ===========================================================================
# Tests: correction bolus (event 280)
# ===========================================================================


class TestCorrectionBolusStatistic:
    """Event 280 (BolusDelivery) correction bolus branches in _import_statistics."""

    async def test_correction_bolus_delivery_status_0_creates_stat(self, hass: HomeAssistant, mock_import):
        """Event 280 with delivery_status=0 and correction_mu>0 generates a correction stat."""
        coordinator = await _make_coordinator(hass)
        events = [
            {
                "event_id": 280,
                "timestamp": _BASE_TS,
                "delivery_status": 0,
                "correction_mu": 1500,
            }
        ]
        await coordinator._import_statistics(events)
        stat_ids = {c[0][1].statistic_id for c in mock_import.call_args_list}
        assert "sensor.carelink_correction_bolus" in stat_ids

    async def test_correction_bolus_nonzero_delivery_status_skipped(self, hass: HomeAssistant, mock_import):
        """Event 280 with delivery_status != 0 (not completed) does not generate a stat."""
        coordinator = await _make_coordinator(hass)
        events = [
            {
                "event_id": 280,
                "timestamp": _BASE_TS,
                "delivery_status": 1,
                "correction_mu": 1500,
            }
        ]
        await coordinator._import_statistics(events)
        assert mock_import.call_count == 0

    async def test_correction_bolus_zero_correction_mu_skipped(self, hass: HomeAssistant, mock_import):
        """Event 280 with correction_mu=0 does not generate a stat."""
        coordinator = await _make_coordinator(hass)
        events = [
            {
                "event_id": 280,
                "timestamp": _BASE_TS,
                "delivery_status": 0,
                "correction_mu": 0,
            }
        ]
        await coordinator._import_statistics(events)
        assert mock_import.call_count == 0
