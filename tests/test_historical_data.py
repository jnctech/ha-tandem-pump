"""Tests for historical data import: _parse_pump_events, replay, and statistics."""
from __future__ import annotations

import sys
import types
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

import pytest

from homeassistant.core import HomeAssistant

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.carelink.const import (
    DOMAIN,
    TANDEM_CLIENT,
    PLATFORM_TYPE,
    PLATFORM_TANDEM,
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
    TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS,
    TANDEM_SENSOR_KEY_BASAL_RATE,
    TANDEM_SENSOR_KEY_ACTIVE_INSULIN,
    TANDEM_SENSOR_KEY_LAST_UPLOAD,
    TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS,
    TANDEM_SENSOR_KEY_UPDATE_TIMESTAMP,
    TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS,
    TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS_ATTRS,
)


def _make_cgm_event(
    seq: int, glucose_mgdl: int, minutes_ago: int = 0
) -> dict[str, Any]:
    """Create a mock CGM_DATA_GXB event (event_id=256)."""
    ts = datetime(2026, 2, 14, 12, 0, 0) - timedelta(minutes=minutes_ago)
    return {
        "event_id": 256,
        "event_name": "CGM_DATA_GXB",
        "seq": seq,
        "timestamp": ts,
        "glucose_mgdl": glucose_mgdl,
        "rate_of_change": 0.5,
        "status": 0,
    }


def _make_bolus_completed_event(
    seq: int,
    insulin_delivered: float,
    iob: float,
    minutes_ago: int = 0,
) -> dict[str, Any]:
    """Create a mock BOLUS_COMPLETED event (event_id=20)."""
    ts = datetime(2026, 2, 14, 12, 0, 0) - timedelta(minutes=minutes_ago)
    return {
        "event_id": 20,
        "event_name": "BOLUS_COMPLETED",
        "seq": seq,
        "timestamp": ts,
        "bolus_id": 100 + seq,
        "completion_status": 3,
        "iob": iob,
        "insulin_delivered": insulin_delivered,
        "insulin_requested": insulin_delivered,
    }


def _make_bolus_delivery_event(
    seq: int,
    insulin_delivered: float,
    bolus_type: int = 0,
    minutes_ago: int = 0,
) -> dict[str, Any]:
    """Create a mock BOLUS_DELIVERY event (event_id=280)."""
    ts = datetime(2026, 2, 14, 12, 0, 0) - timedelta(minutes=minutes_ago)
    return {
        "event_id": 280,
        "event_name": "BOLUS_DELIVERY",
        "seq": seq,
        "timestamp": ts,
        "bolus_id": 200 + seq,
        "bolus_type": bolus_type,
        "delivery_status": 0,
        "insulin_delivered": insulin_delivered,
        "requested_now_mu": int(insulin_delivered * 1000),
        "correction_mu": 0,
    }


def _make_basal_rate_change_event(
    seq: int,
    commanded_rate: float,
    change_type: int = 0,
    minutes_ago: int = 0,
) -> dict[str, Any]:
    """Create a mock BASAL_RATE_CHANGE event (event_id=3)."""
    ts = datetime(2026, 2, 14, 12, 0, 0) - timedelta(minutes=minutes_ago)
    return {
        "event_id": 3,
        "event_name": "BASAL_RATE_CHANGE",
        "seq": seq,
        "timestamp": ts,
        "commanded_rate": commanded_rate,
        "base_rate": 0.8,
        "max_rate": 3.0,
        "change_type": change_type,
    }


def _make_basal_delivery_event(
    seq: int,
    commanded_rate: float,
    commanded_source: int = 1,
    minutes_ago: int = 0,
) -> dict[str, Any]:
    """Create a mock BASAL_DELIVERY event (event_id=279)."""
    ts = datetime(2026, 2, 14, 12, 0, 0) - timedelta(minutes=minutes_ago)
    return {
        "event_id": 279,
        "event_name": "BASAL_DELIVERY",
        "seq": seq,
        "timestamp": ts,
        "commanded_source": commanded_source,
        "commanded_rate": commanded_rate,
        "profile_rate_mu": int(0.8 * 1000),
    }


def _make_pump_events_data(
    pump_events: list[dict],
) -> dict[str, Any]:
    """Wrap pump_events in the format get_recent_data returns."""
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
        "pump_events": pump_events,
        "therapy_timeline": None,
        "dashboard_summary": None,
    }


async def _setup_coordinator(
    hass: HomeAssistant,
    mock_data: dict[str, Any],
):
    """Set up a TandemCoordinator with mocked data and return it."""
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
    # Metadata check returns a new maxDateWithEvents each time (forces full fetch)
    mock_client.get_pump_event_metadata = AsyncMock(return_value=[{
        "maxDateWithEvents": "2024-01-15T12:00:00",
    }])
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


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _parse_pump_events - CGM
# ═══════════════════════════════════════════════════════════════════════════


class TestParsePumpEventsCGM:
    """Tests for CGM event parsing from binary pump events."""

    async def test_single_cgm_event(self, hass: HomeAssistant):
        """Test a single CGM event populates glucose sensors."""
        events = [_make_cgm_event(seq=1, glucose_mgdl=150)]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == 150
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MMOL] == round(
            150 * 0.0555, 2
        )

    async def test_latest_cgm_used(self, hass: HomeAssistant):
        """Test that the most recent CGM event is used for sensor state."""
        events = [
            _make_cgm_event(seq=1, glucose_mgdl=100, minutes_ago=10),
            _make_cgm_event(seq=2, glucose_mgdl=120, minutes_ago=5),
            _make_cgm_event(seq=3, glucose_mgdl=140, minutes_ago=0),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == 140

    async def test_cgm_zero_glucose_unavailable(self, hass: HomeAssistant):
        """Test that a zero glucose reading results in UNAVAILABLE."""
        events = [_make_cgm_event(seq=1, glucose_mgdl=0)]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] is UNAVAILABLE

    async def test_no_cgm_events_unavailable(self, hass: HomeAssistant):
        """Test that no CGM events results in UNAVAILABLE glucose."""
        events = [_make_basal_rate_change_event(seq=1, commanded_rate=0.8)]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MMOL] is UNAVAILABLE

    async def test_cgm_history_attributes(self, hass: HomeAssistant):
        """Test that CGM readings are stored in entity attributes."""
        events = [
            _make_cgm_event(seq=i, glucose_mgdl=100 + i * 5, minutes_ago=30 - i * 5)
            for i in range(1, 7)
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        attrs = coordinator.data.get(f"{TANDEM_SENSOR_KEY_LASTSG_MGDL}_attributes", {})
        readings = attrs.get("readings", [])
        assert len(readings) == 6
        # Verify compact keys and values
        assert "t" in readings[0]
        assert "v" in readings[0]
        assert readings[-1]["v"] == 130  # Last reading = 100 + 6*5

    async def test_cgm_history_max_limit(self, hass: HomeAssistant):
        """Test that CGM history is limited to 24 entries."""
        events = [
            _make_cgm_event(seq=i, glucose_mgdl=100 + i, minutes_ago=150 - i * 5)
            for i in range(1, 31)  # 30 events
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        attrs = coordinator.data.get(f"{TANDEM_SENSOR_KEY_LASTSG_MGDL}_attributes", {})
        readings = attrs.get("readings", [])
        assert len(readings) == 24  # Capped at _MAX_CGM_HISTORY


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _parse_pump_events - Bolus
# ═══════════════════════════════════════════════════════════════════════════


class TestParsePumpEventsBolus:
    """Tests for bolus event parsing."""

    async def test_bolus_completed_values(self, hass: HomeAssistant):
        """Test BOLUS_COMPLETED populates sensor values."""
        events = [
            _make_bolus_completed_event(
                seq=1, insulin_delivered=3.5, iob=2.1, minutes_ago=5
            ),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] == 3.5
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] == 2.1
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP] is not UNAVAILABLE

    async def test_iob_from_bolus_completed(self, hass: HomeAssistant):
        """Test IOB is extracted from BOLUS_COMPLETED events."""
        events = [
            _make_bolus_completed_event(seq=1, insulin_delivered=2.0, iob=5.3),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] == 5.3

    async def test_meal_bolus_detection(self, hass: HomeAssistant):
        """Test meal bolus is detected from bolus_type bit 4."""
        events = [
            _make_bolus_delivery_event(
                seq=1, insulin_delivered=4.0, bolus_type=0x10, minutes_ago=10
            ),
            _make_bolus_delivery_event(
                seq=2, insulin_delivered=1.0, bolus_type=0x00, minutes_ago=5
            ),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] == 4.0

    async def test_no_meal_bolus_when_no_carb_flag(self, hass: HomeAssistant):
        """Test meal bolus is UNAVAILABLE when no carb flag present."""
        events = [
            _make_bolus_delivery_event(
                seq=1, insulin_delivered=2.0, bolus_type=0x00
            ),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] is UNAVAILABLE

    async def test_bolus_attrs_populated(self, hass: HomeAssistant):
        """Test bolus attributes are populated correctly."""
        events = [
            _make_bolus_completed_event(
                seq=1, insulin_delivered=3.5, iob=2.1
            ),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        attrs = coordinator.data.get(TANDEM_SENSOR_KEY_LAST_BOLUS_ATTRS, {})
        assert attrs["event_type"] == "BOLUS_COMPLETED"
        assert attrs["bolus_id"] == 101
        assert attrs["completion_status"] == 3

    async def test_no_bolus_events_unavailable(self, hass: HomeAssistant):
        """Test that no bolus events results in UNAVAILABLE."""
        events = [_make_cgm_event(seq=1, glucose_mgdl=120)]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] is UNAVAILABLE


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _parse_pump_events - Basal
# ═══════════════════════════════════════════════════════════════════════════


class TestParsePumpEventsBasal:
    """Tests for basal event parsing."""

    async def test_basal_rate_change(self, hass: HomeAssistant):
        """Test BASAL_RATE_CHANGE populates basal rate sensor."""
        events = [
            _make_basal_rate_change_event(seq=1, commanded_rate=0.85),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_BASAL_RATE] == 0.85

    async def test_basal_delivery_with_source(self, hass: HomeAssistant):
        """Test BASAL_DELIVERY sets Control-IQ status from commanded_source."""
        events = [
            _make_basal_delivery_event(
                seq=1, commanded_rate=1.2, commanded_source=3
            ),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_BASAL_RATE] == 1.2
        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] == "Algorithm"

    async def test_basal_suspended_status(self, hass: HomeAssistant):
        """Test suspended basal maps to 'Suspended' status."""
        events = [
            _make_basal_delivery_event(
                seq=1, commanded_rate=0.0, commanded_source=0
            ),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] == "Suspended"

    async def test_no_basal_events_unavailable(self, hass: HomeAssistant):
        """Test that no basal events results in UNAVAILABLE."""
        events = [_make_cgm_event(seq=1, glucose_mgdl=120)]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_BASAL_RATE] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_STATUS] is UNAVAILABLE


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Sequence number deduplication
# ═══════════════════════════════════════════════════════════════════════════


class TestSequenceDeduplication:
    """Tests for event sequence number tracking."""

    async def test_last_event_seq_updated(self, hass: HomeAssistant):
        """Test that _last_event_seq is updated after processing."""
        events = [
            _make_cgm_event(seq=10, glucose_mgdl=100, minutes_ago=10),
            _make_cgm_event(seq=20, glucose_mgdl=120, minutes_ago=5),
            _make_cgm_event(seq=30, glucose_mgdl=140, minutes_ago=0),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator._last_event_seq == 30

    async def test_stale_events_filtered_on_second_poll(
        self, hass: HomeAssistant
    ):
        """Test that previously-seen events are filtered on the next poll."""
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

        first_events = [
            _make_cgm_event(seq=10, glucose_mgdl=100, minutes_ago=10),
            _make_cgm_event(seq=20, glucose_mgdl=120, minutes_ago=5),
        ]
        second_events = [
            # seq 10, 20 are duplicates; seq 30 is new
            _make_cgm_event(seq=10, glucose_mgdl=100, minutes_ago=10),
            _make_cgm_event(seq=20, glucose_mgdl=120, minutes_ago=5),
            _make_cgm_event(seq=30, glucose_mgdl=140, minutes_ago=0),
        ]

        mock_client = AsyncMock()
        mock_client.login = AsyncMock(return_value=True)
        mock_client.get_recent_data = AsyncMock(
            side_effect=[
                _make_pump_events_data(first_events),
                _make_pump_events_data(second_events),
            ]
        )
        # Return different maxDateWithEvents each poll to force full fetch
        mock_client.get_pump_event_metadata = AsyncMock(
            side_effect=[
                [{"maxDateWithEvents": "2024-01-15T12:00:00"}],
                [{"maxDateWithEvents": "2024-01-15T12:05:00"}],
            ]
        )
        mock_client.close = AsyncMock()

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: mock_client,
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }

        coordinator = TandemCoordinator(
            hass, entry, update_interval=timedelta(seconds=300)
        )

        # First poll
        await coordinator.async_config_entry_first_refresh()
        assert coordinator._last_event_seq == 20

        # Second poll
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert coordinator._last_event_seq == 30
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == 140


# ═══════════════════════════════════════════════════════════════════════════
# Tests: _import_statistics
# ═══════════════════════════════════════════════════════════════════════════


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
    has_mean: bool = False
    has_sum: bool = False
    name: str = ""
    source: str = ""
    statistic_id: str = ""
    unit_of_measurement: str = ""


def _install_mock_recorder_modules(mock_import_fn):
    """Install fake recorder modules so the lazy import inside _import_statistics works.

    Returns a cleanup function that removes the modules.
    """
    recorder_mod = types.ModuleType("homeassistant.components.recorder")
    stats_mod = types.ModuleType("homeassistant.components.recorder.statistics")
    models_mod = types.ModuleType("homeassistant.components.recorder.models")

    stats_mod.async_import_statistics = mock_import_fn
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

    def cleanup():
        for k in keys:
            if saved[k] is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = saved[k]

    return cleanup


class TestImportStatistics:
    """Tests for the _import_statistics method."""

    async def test_statistics_imported_for_cgm(self, hass: HomeAssistant):
        """Test that CGM events generate statistics import calls."""
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
        mock_client.close = AsyncMock()

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: mock_client,
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }

        coordinator = TandemCoordinator(
            hass, entry, update_interval=timedelta(seconds=300)
        )

        events = [
            _make_cgm_event(seq=1, glucose_mgdl=100, minutes_ago=10),
            _make_cgm_event(seq=2, glucose_mgdl=120, minutes_ago=5),
            _make_cgm_event(seq=3, glucose_mgdl=140, minutes_ago=0),
        ]

        mock_import = MagicMock()
        cleanup = _install_mock_recorder_modules(mock_import)
        try:
            await coordinator._import_statistics(events)

            # Should be called once for CGM stats (no IOB or basal in events)
            assert mock_import.call_count == 1
            call_args = mock_import.call_args
            meta = call_args[0][1]
            stats = call_args[0][2]
            assert meta.unit_of_measurement == "mmol/L"
            assert len(stats) == 3
        finally:
            cleanup()

    async def test_statistics_period_rounded_to_hour(
        self, hass: HomeAssistant
    ):
        """Test that statistics timestamps are rounded to the top of the hour."""
        from custom_components.carelink import TandemCoordinator
        from datetime import timezone as dt_tz

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
        mock_client.close = AsyncMock()

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: mock_client,
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }

        coordinator = TandemCoordinator(
            hass, entry, update_interval=timedelta(seconds=300)
        )

        # Create a CGM event at 12:07:30 UTC - should round to 12:00:00
        events = [{
            "event_id": 256,
            "event_name": "CGM_DATA_GXB",
            "seq": 1,
            "timestamp": datetime(2026, 2, 14, 12, 7, 30, tzinfo=dt_tz.utc),
            "glucose_mgdl": 120,
        }]

        mock_import = MagicMock()
        cleanup = _install_mock_recorder_modules(mock_import)
        try:
            await coordinator._import_statistics(events)

            stats = mock_import.call_args[0][2]
            assert stats[0].start.minute == 0
            assert stats[0].start.second == 0
        finally:
            cleanup()

    async def test_statistics_handles_import_error(self, hass: HomeAssistant):
        """Test that import errors are handled gracefully."""
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
        mock_client.close = AsyncMock()

        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: mock_client,
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }

        coordinator = TandemCoordinator(
            hass, entry, update_interval=timedelta(seconds=300)
        )

        events = [_make_cgm_event(seq=1, glucose_mgdl=120)]

        mock_import = MagicMock(side_effect=Exception("DB error"))
        cleanup = _install_mock_recorder_modules(mock_import)
        try:
            # Should not raise
            await coordinator._import_statistics(events)
        finally:
            cleanup()


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Empty pump_events list
# ═══════════════════════════════════════════════════════════════════════════


class TestEmptyPumpEvents:
    """Tests for when pump_events is an empty list."""

    async def test_empty_pump_events_all_unavailable(self, hass: HomeAssistant):
        """Test that empty pump_events falls through to UNAVAILABLE."""
        data = _make_pump_events_data([])
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_BASAL_RATE] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] is UNAVAILABLE


# ═══════════════════════════════════════════════════════════════════════════
# Tests: Mixed event types in single poll
# ═══════════════════════════════════════════════════════════════════════════


class TestMixedEvents:
    """Tests for realistic scenarios with multiple event types."""

    async def test_full_event_mix(self, hass: HomeAssistant):
        """Test a realistic mix of CGM, bolus, and basal events."""
        events = [
            _make_cgm_event(seq=1, glucose_mgdl=110, minutes_ago=20),
            _make_basal_delivery_event(
                seq=2, commanded_rate=0.8, commanded_source=1, minutes_ago=18
            ),
            _make_cgm_event(seq=3, glucose_mgdl=115, minutes_ago=15),
            _make_bolus_completed_event(
                seq=4, insulin_delivered=2.5, iob=3.0, minutes_ago=12
            ),
            _make_bolus_delivery_event(
                seq=5, insulin_delivered=2.5, bolus_type=0x10, minutes_ago=12
            ),
            _make_cgm_event(seq=6, glucose_mgdl=125, minutes_ago=10),
            _make_basal_rate_change_event(
                seq=7, commanded_rate=1.2, minutes_ago=8
            ),
            _make_cgm_event(seq=8, glucose_mgdl=130, minutes_ago=5),
            _make_cgm_event(seq=9, glucose_mgdl=135, minutes_ago=0),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        # Latest CGM: 135
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == 135
        # Latest bolus: 2.5 units
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_UNITS] == 2.5
        # IOB from bolus_completed: 3.0
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_INSULIN] == 3.0
        # Meal bolus detected (bolus_type has bit 4)
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_MEAL_BOLUS] == 2.5
        # Latest basal rate: 1.2 (from basal_rate_change)
        assert coordinator.data[TANDEM_SENSOR_KEY_BASAL_RATE] == 1.2
