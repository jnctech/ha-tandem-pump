"""Tests for extended statistics: meal carbs and total bolus import."""

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

from custom_components.carelink.const import (
    DOMAIN,
    TANDEM_CLIENT,
    PLATFORM_TYPE,
    PLATFORM_TANDEM,
)


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


# -- Fixtures --------------------------------------------------------------


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


# -- Event factories -------------------------------------------------------

_BASE_TS = datetime(2026, 3, 1, 12, 0, 0)


def _make_carb_event(seq: int, carbs: float, minutes_ago: int = 0) -> dict[str, Any]:
    """Create a mock CARBS_ENTERED event (event_id=48)."""
    return {
        "event_id": 48,
        "event_name": "CarbsEntered",
        "seq": seq,
        "timestamp": _BASE_TS - timedelta(minutes=minutes_ago),
        "carbs": carbs,
    }


def _make_bolus_completed_event(
    seq: int,
    insulin_delivered: float,
    completion_status: int = 3,
    minutes_ago: int = 0,
) -> dict[str, Any]:
    """Create a mock BOLUS_COMPLETED event (event_id=20)."""
    return {
        "event_id": 20,
        "event_name": "BolusCompleted",
        "seq": seq,
        "timestamp": _BASE_TS - timedelta(minutes=minutes_ago),
        "bolus_id": 100 + seq,
        "completion_status": completion_status,
        "iob": 1.5,
        "insulin_delivered": insulin_delivered,
        "insulin_requested": insulin_delivered,
    }


def _make_bolex_completed_event(
    seq: int,
    insulin_delivered: float,
    completion_status: int = 3,
    minutes_ago: int = 0,
) -> dict[str, Any]:
    """Create a mock BOLEX_COMPLETED event (event_id=21, extended bolus)."""
    return {
        "event_id": 21,
        "event_name": "BolexCompleted",
        "seq": seq,
        "timestamp": _BASE_TS - timedelta(minutes=minutes_ago),
        "bolus_id": 200 + seq,
        "completion_status": completion_status,
        "iob": 0.8,
        "insulin_delivered": insulin_delivered,
        "insulin_requested": insulin_delivered,
    }


def _make_cgm_event(seq: int, glucose_mgdl: int, minutes_ago: int = 0) -> dict[str, Any]:
    """Create a mock CGM_DATA_GXB event (event_id=256)."""
    return {
        "event_id": 256,
        "event_name": "CGM_DATA_GXB",
        "seq": seq,
        "timestamp": _BASE_TS - timedelta(minutes=minutes_ago),
        "glucose_mgdl": glucose_mgdl,
    }


# -- Coordinator fixture ---------------------------------------------------


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
    mock_client.get_pump_event_metadata = AsyncMock(
        return_value=[{"maxDateWithEvents": "2026-03-01T12:00:00"}]
    )
    mock_client.close = AsyncMock()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        TANDEM_CLIENT: mock_client,
        PLATFORM_TYPE: PLATFORM_TANDEM,
    }

    coordinator = TandemCoordinator(hass, entry, update_interval=timedelta(seconds=300))
    await coordinator.async_config_entry_first_refresh()
    return coordinator


# -- Helper: extract statistic IDs from mock_import calls ------------------


def _imported_stat_ids(mock_import: MagicMock) -> set[str]:
    """Return the set of statistic_id values from all async_import_statistics calls."""
    return {c[0][1].statistic_id for c in mock_import.call_args_list}


def _find_stat_call(mock_import: MagicMock, stat_id_suffix: str):
    """Find the import call for a given statistic_id suffix and return (meta, stats)."""
    full_id = f"sensor.{DOMAIN}_{stat_id_suffix}"
    call = next(c for c in mock_import.call_args_list if c[0][1].statistic_id == full_id)
    return call[0][1], call[0][2]


# ===========================================================================
# Tests: carb statistics
# ===========================================================================


class TestCarbStatisticsImport:
    """Tests for carb (event 48) statistics import."""

    async def test_carb_statistics_imported(self, hass: HomeAssistant, mock_import):
        """Carb events produce a carb statistics import call."""
        coordinator = await _make_coordinator(hass)
        events = [
            _make_carb_event(seq=1, carbs=25.0),
            _make_carb_event(seq=2, carbs=40.0, minutes_ago=30),
        ]
        await coordinator._import_statistics(events)

        assert mock_import.call_count == 1
        meta, stats = _find_stat_call(mock_import, "meal_carbs")
        assert meta.unit_of_measurement == "g"
        assert meta.has_mean is True
        assert meta.has_sum is False
        assert len(stats) == 2

    async def test_carb_stat_values_correct(self, hass: HomeAssistant, mock_import):
        """Carb event values are correctly stored in StatisticData."""
        coordinator = await _make_coordinator(hass)
        await coordinator._import_statistics([_make_carb_event(seq=1, carbs=30.0)])

        _, stats = _find_stat_call(mock_import, "meal_carbs")
        assert stats[0].mean == 30.0
        assert stats[0].state == 30.0

    async def test_zero_carbs_excluded(self, hass: HomeAssistant, mock_import):
        """Carb events with zero or missing carbs are not imported."""
        coordinator = await _make_coordinator(hass)
        events = [
            {"event_id": 48, "timestamp": datetime(2026, 3, 1, 10, 0, 0), "carbs": 0},
            {"event_id": 48, "timestamp": datetime(2026, 3, 1, 11, 0, 0), "carbs": None},
        ]
        await coordinator._import_statistics(events)
        assert mock_import.call_count == 0

    async def test_empty_events_no_carb_import(self, hass: HomeAssistant, mock_import):
        """Empty pump_events list produces no carb statistics call."""
        coordinator = await _make_coordinator(hass)
        await coordinator._import_statistics([])
        assert mock_import.call_count == 0


# ===========================================================================
# Tests: bolus statistics
# ===========================================================================


class TestBolusStatisticsImport:
    """Tests for bolus (event 20/21) statistics import."""

    async def test_bolus_statistics_imported(self, hass: HomeAssistant, mock_import):
        """Completed bolus events produce a bolus statistics import call."""
        coordinator = await _make_coordinator(hass)
        events = [
            _make_bolus_completed_event(seq=1, insulin_delivered=3.5),
            _make_bolus_completed_event(seq=2, insulin_delivered=2.0, minutes_ago=60),
        ]
        await coordinator._import_statistics(events)

        assert f"sensor.{DOMAIN}_total_bolus" in _imported_stat_ids(mock_import)
        meta, stats = _find_stat_call(mock_import, "total_bolus")
        assert meta.unit_of_measurement == "units"
        assert meta.has_mean is True
        assert meta.has_sum is False
        assert len(stats) == 2

    async def test_bolus_stat_values_correct(self, hass: HomeAssistant, mock_import):
        """Bolus delivered value is correctly stored in StatisticData."""
        coordinator = await _make_coordinator(hass)
        await coordinator._import_statistics(
            [_make_bolus_completed_event(seq=1, insulin_delivered=4.75)]
        )

        _, stats = _find_stat_call(mock_import, "total_bolus")
        assert stats[0].mean == 4.75
        assert stats[0].state == 4.75

    async def test_incomplete_bolus_excluded(self, hass: HomeAssistant, mock_import):
        """Bolus events with completion_status != 3 are NOT imported as bolus stats."""
        coordinator = await _make_coordinator(hass)
        events = [
            _make_bolus_completed_event(seq=1, insulin_delivered=3.0, completion_status=1),
            _make_bolus_completed_event(seq=2, insulin_delivered=2.5, completion_status=2),
        ]
        await coordinator._import_statistics(events)

        ids = _imported_stat_ids(mock_import)
        # IOB should still be collected (not filtered by completion_status)
        assert f"sensor.{DOMAIN}_active_insulin_iob" in ids
        # But bolus stats should NOT be present
        assert f"sensor.{DOMAIN}_total_bolus" not in ids

    async def test_extended_bolus_event_21_included(self, hass: HomeAssistant, mock_import):
        """BOLEX_COMPLETED (event_id=21) is also included in bolus statistics."""
        coordinator = await _make_coordinator(hass)
        await coordinator._import_statistics(
            [_make_bolex_completed_event(seq=1, insulin_delivered=6.0)]
        )
        assert f"sensor.{DOMAIN}_total_bolus" in _imported_stat_ids(mock_import)

    async def test_zero_insulin_excluded(self, hass: HomeAssistant, mock_import):
        """Bolus events with zero insulin_delivered are not imported."""
        coordinator = await _make_coordinator(hass)
        await coordinator._import_statistics(
            [_make_bolus_completed_event(seq=1, insulin_delivered=0.0)]
        )
        assert f"sensor.{DOMAIN}_total_bolus" not in _imported_stat_ids(mock_import)


# ===========================================================================
# Tests: all 5 statistic types together
# ===========================================================================


class TestAllFiveStatisticsTypes:
    """Verify all 5 statistic types are imported in a single _import_statistics call."""

    async def test_all_five_stats_imported_together(self, hass: HomeAssistant, mock_import):
        """A mixed event list produces imports for CGM, IOB, basal, carbs, and bolus."""
        coordinator = await _make_coordinator(hass)
        events = [
            _make_cgm_event(seq=1, glucose_mgdl=120),
            _make_bolus_completed_event(seq=2, insulin_delivered=3.5),  # IOB + bolus
            {"event_id": 3, "timestamp": datetime(2026, 3, 1, 10, 0, 0), "commanded_rate": 0.85},
            _make_carb_event(seq=4, carbs=30.0),
        ]
        await coordinator._import_statistics(events)

        ids = _imported_stat_ids(mock_import)
        assert ids == {
            f"sensor.{DOMAIN}_last_glucose_level_mmol",
            f"sensor.{DOMAIN}_active_insulin_iob",
            f"sensor.{DOMAIN}_basal_rate",
            f"sensor.{DOMAIN}_meal_carbs",
            f"sensor.{DOMAIN}_total_bolus",
        }

    async def test_iob_and_bolus_from_same_event_20(self, hass: HomeAssistant, mock_import):
        """A single BOLUS_COMPLETED event produces both an IOB stat and a bolus stat."""
        coordinator = await _make_coordinator(hass)
        await coordinator._import_statistics(
            [_make_bolus_completed_event(seq=1, insulin_delivered=2.5)]
        )

        ids = _imported_stat_ids(mock_import)
        assert f"sensor.{DOMAIN}_active_insulin_iob" in ids
        assert f"sensor.{DOMAIN}_total_bolus" in ids
