"""Tests for the "cheap-win" sensors (one-line reads of existing event fields).

Covers the coordinator consumer logic for:
- TANDEM_SENSOR_KEY_RSSI                 (event 256/399, rssi field)
- TANDEM_SENSOR_KEY_IOB_HOURS / _MINUTES (event 9, iob_hours/iob_minutes fields)
- TANDEM_SENSOR_KEY_CLOSED_LOOP_PREFERRED (event 230, closed_loop_preferred field)

The event dicts here are already-mapped (map_pump_log_event output), matching what
``get_recent_data`` hands the coordinator.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from conftest import make_tandem_coordinator

from custom_components.tandem.const import (
    UNAVAILABLE,
    TANDEM_SENSOR_KEY_CLOSED_LOOP_PREFERRED,
    TANDEM_SENSOR_KEY_IOB_HOURS,
    TANDEM_SENSOR_KEY_IOB_MINUTES,
    TANDEM_SENSOR_KEY_RSSI,
)
from custom_components.tandem.tandem_api import (
    EVT_AA_PCM_CHANGE,
    EVT_BATTERY_1,
    EVT_CGM_DATA_G7,
    EVT_STATUS,
)

_BASE_TS = datetime(2026, 3, 1, 12, 0, 0)


def _cgm_event(*, glucose_mgdl: int = 120, rssi: Any = -62, minutes_ago: int = 0) -> dict[str, Any]:
    return {
        "event_id": EVT_CGM_DATA_G7,
        "event_name": "CGM",
        "seq": 1,
        "timestamp": _BASE_TS - timedelta(minutes=minutes_ago),
        "glucose_mgdl": glucose_mgdl,
        "rate_of_change": 0.3,
        "status": 0,
        "rssi": rssi,
    }


def _status_event(*, iob_hours: Any, iob_minutes: Any, minutes_ago: int = 0) -> dict[str, Any]:
    return {
        "event_id": EVT_STATUS,
        "event_name": "PumpStatus",
        "seq": 1,
        "timestamp": _BASE_TS - timedelta(minutes=minutes_ago),
        "battery_percent": 96,
        "iob_hours": iob_hours,
        "iob_minutes": iob_minutes,
    }


def _battery_detail_event(*, minutes_ago: int = 0) -> dict[str, Any]:
    # Event 34: shares the bucket but carries no IOB fields.
    return {
        "event_id": EVT_BATTERY_1,
        "event_name": "Battery",
        "seq": 1,
        "timestamp": _BASE_TS - timedelta(minutes=minutes_ago),
        "battery_percent": 95,
        "iob_hours": None,
        "iob_minutes": None,
    }


def _pcm_event(*, closed_loop_preferred: Any) -> dict[str, Any]:
    return {
        "event_id": EVT_AA_PCM_CHANGE,
        "event_name": "PCMChange",
        "seq": 1,
        "timestamp": _BASE_TS,
        "current_pcm": "ClosedLoop",
        "closed_loop_preferred": closed_loop_preferred,
    }


class TestRssi:
    async def test_rssi_from_latest_cgm(self, hass: HomeAssistant):
        coordinator = await make_tandem_coordinator(hass, [_cgm_event(rssi=-58)])
        assert coordinator.data[TANDEM_SENSOR_KEY_RSSI] == -58

    async def test_rssi_surfaced_even_when_glucose_zero(self, hass: HomeAssistant):
        # Signal strength is independent of glucose validity.
        coordinator = await make_tandem_coordinator(hass, [_cgm_event(glucose_mgdl=0, rssi=-77)])
        assert coordinator.data[TANDEM_SENSOR_KEY_RSSI] == -77

    async def test_rssi_unavailable_when_absent(self, hass: HomeAssistant):
        coordinator = await make_tandem_coordinator(hass, [_cgm_event(rssi=None)])
        assert coordinator.data[TANDEM_SENSOR_KEY_RSSI] is UNAVAILABLE

    async def test_rssi_unavailable_when_no_cgm(self, hass: HomeAssistant):
        coordinator = await make_tandem_coordinator(hass, [])
        assert coordinator.data[TANDEM_SENSOR_KEY_RSSI] is UNAVAILABLE


class TestIobDuration:
    async def test_iob_from_status_event(self, hass: HomeAssistant):
        coordinator = await make_tandem_coordinator(hass, [_status_event(iob_hours=2, iob_minutes=45)])
        assert coordinator.data[TANDEM_SENSOR_KEY_IOB_HOURS] == 2
        assert coordinator.data[TANDEM_SENSOR_KEY_IOB_MINUTES] == 45

    async def test_iob_takes_latest_status_event(self, hass: HomeAssistant):
        coordinator = await make_tandem_coordinator(
            hass,
            [
                _status_event(iob_hours=5, iob_minutes=0, minutes_ago=60),
                _status_event(iob_hours=1, iob_minutes=30, minutes_ago=5),
            ],
        )
        assert coordinator.data[TANDEM_SENSOR_KEY_IOB_HOURS] == 1
        assert coordinator.data[TANDEM_SENSOR_KEY_IOB_MINUTES] == 30

    async def test_iob_not_clobbered_by_newer_battery_detail(self, hass: HomeAssistant):
        # A newer battery-detail event (34, no IOB) must not null the IOB from event 9.
        coordinator = await make_tandem_coordinator(
            hass,
            [
                _status_event(iob_hours=3, iob_minutes=15, minutes_ago=30),
                _battery_detail_event(minutes_ago=1),
            ],
        )
        assert coordinator.data[TANDEM_SENSOR_KEY_IOB_HOURS] == 3
        assert coordinator.data[TANDEM_SENSOR_KEY_IOB_MINUTES] == 15

    async def test_iob_unavailable_when_no_status(self, hass: HomeAssistant):
        coordinator = await make_tandem_coordinator(hass, [_battery_detail_event()])
        assert coordinator.data[TANDEM_SENSOR_KEY_IOB_HOURS] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_IOB_MINUTES] is UNAVAILABLE


class TestClosedLoopPreferred:
    async def test_true(self, hass: HomeAssistant):
        coordinator = await make_tandem_coordinator(hass, [_pcm_event(closed_loop_preferred=True)])
        assert coordinator.data[TANDEM_SENSOR_KEY_CLOSED_LOOP_PREFERRED] is True

    async def test_false(self, hass: HomeAssistant):
        coordinator = await make_tandem_coordinator(hass, [_pcm_event(closed_loop_preferred=False)])
        assert coordinator.data[TANDEM_SENSOR_KEY_CLOSED_LOOP_PREFERRED] is False

    async def test_unavailable_when_absent(self, hass: HomeAssistant):
        coordinator = await make_tandem_coordinator(hass, [_pcm_event(closed_loop_preferred=None)])
        assert coordinator.data[TANDEM_SENSOR_KEY_CLOSED_LOOP_PREFERRED] is UNAVAILABLE

    async def test_unavailable_when_no_pcm(self, hass: HomeAssistant):
        coordinator = await make_tandem_coordinator(hass, [])
        assert coordinator.data[TANDEM_SENSOR_KEY_CLOSED_LOOP_PREFERRED] is UNAVAILABLE
