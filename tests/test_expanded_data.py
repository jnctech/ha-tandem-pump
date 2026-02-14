"""Tests for expanded data sources: new event decoders, computed summaries, new sensors."""
from __future__ import annotations

import struct
import base64
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.carelink.const import (
    DOMAIN,
    TANDEM_CLIENT,
    PLATFORM_TYPE,
    PLATFORM_TANDEM,
    UNAVAILABLE,
    # CGM summary
    TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL,
    TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL,
    TANDEM_SENSOR_KEY_TIME_IN_RANGE,
    TANDEM_SENSOR_KEY_CGM_USAGE,
    TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV,
    TANDEM_SENSOR_KEY_GLUCOSE_CV,
    TANDEM_SENSOR_KEY_GMI,
    TANDEM_SENSOR_KEY_TIME_BELOW_RANGE,
    TANDEM_SENSOR_KEY_TIME_ABOVE_RANGE,
    # New event sensors
    TANDEM_SENSOR_KEY_ACTIVITY_MODE,
    TANDEM_SENSOR_KEY_CONTROL_IQ_MODE,
    TANDEM_SENSOR_KEY_PUMP_SUSPENDED,
    TANDEM_SENSOR_KEY_LAST_CARBS,
    TANDEM_SENSOR_KEY_LAST_CARBS_TIMESTAMP,
    TANDEM_SENSOR_KEY_LAST_CARTRIDGE_CHANGE,
    TANDEM_SENSOR_KEY_LAST_SITE_CHANGE,
    TANDEM_SENSOR_KEY_LAST_TUBING_CHANGE,
    TANDEM_SENSOR_KEY_CARTRIDGE_INSULIN,
    TANDEM_SENSOR_KEY_LAST_BG_READING,
    # Insulin summary
    TANDEM_SENSOR_KEY_TOTAL_DAILY_INSULIN,
    TANDEM_SENSOR_KEY_DAILY_BOLUS_TOTAL,
    TANDEM_SENSOR_KEY_DAILY_BASAL_TOTAL,
    TANDEM_SENSOR_KEY_BASAL_BOLUS_SPLIT,
    TANDEM_SENSOR_KEY_DAILY_CARBS,
    TANDEM_SENSOR_KEY_DAILY_BOLUS_COUNT,
)

from custom_components.carelink.tandem_api import (
    decode_pump_events,
    TANDEM_EPOCH,
    EVENT_LEN,
)


# ── Helpers ──────────────────────────────────────────────────────────

# Use midday UTC today so events remain "today" even in far-west timezones
# (e.g. US/Pacific = UTC-8).  Using plain datetime.now(utc) would fail if
# the Docker host clock is near midnight UTC.
_now = datetime.now(timezone.utc)
BASE_TS = _now.replace(hour=12, minute=0, second=0, microsecond=0)


def _make_cgm_event(seq: int, glucose_mgdl: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 256, "event_name": "CGM", "seq": seq,
        "timestamp": ts, "glucose_mgdl": glucose_mgdl,
        "rate_of_change": 0.5, "status": 0,
    }


def _make_bolus_completed(seq: int, delivered: float, iob: float, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 20, "event_name": "BolusCompleted", "seq": seq,
        "timestamp": ts, "bolus_id": 100 + seq, "completion_status": 3,
        "iob": iob, "insulin_delivered": delivered, "insulin_requested": delivered,
    }


def _make_basal_delivery(seq: int, rate: float, source: int = 1, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 279, "event_name": "BasalDelivery", "seq": seq,
        "timestamp": ts, "commanded_source": source,
        "commanded_rate": rate, "profile_rate_mu": int(0.8 * 1000),
    }


def _make_carbs_event(seq: int, carbs: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 48, "event_name": "CarbsEntered", "seq": seq,
        "timestamp": ts, "carbs": carbs,
    }


def _make_user_mode_event(seq: int, current_mode: str, mode_id: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 229, "event_name": "UserModeChange", "seq": seq,
        "timestamp": ts, "current_mode": current_mode, "previous_mode": "Normal",
        "current_mode_id": mode_id, "previous_mode_id": 0,
    }


def _make_pcm_event(seq: int, current_pcm: str, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 230, "event_name": "PCMChange", "seq": seq,
        "timestamp": ts, "current_pcm": current_pcm, "previous_pcm": "No Control",
    }


def _make_suspend_event(seq: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 11, "event_name": "PumpingSuspended", "seq": seq,
        "timestamp": ts, "suspend_reason": "User", "suspend_reason_id": 0,
        "insulin_amount": 0.5,
    }


def _make_resume_event(seq: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 12, "event_name": "PumpingResumed", "seq": seq,
        "timestamp": ts, "pre_resume_state": 0, "insulin_amount": 0.0,
    }


def _make_cartridge_event(seq: int, volume: float, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 33, "event_name": "CartridgeFilled", "seq": seq,
        "timestamp": ts, "insulin_volume": volume,
    }


def _make_cannula_event(seq: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 61, "event_name": "CannulaFilled", "seq": seq,
        "timestamp": ts, "prime_size": 0.3, "completion_status": 0,
    }


def _make_tubing_event(seq: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 63, "event_name": "TubingFilled", "seq": seq,
        "timestamp": ts, "prime_size": 10.0, "completion_status": 0,
    }


def _make_bg_event(seq: int, bg_mgdl: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 16, "event_name": "BGReading", "seq": seq,
        "timestamp": ts, "bg_mgdl": bg_mgdl, "iob": 2.5,
        "entry_type": "Manual",
    }


def _make_pump_events_data(pump_events: list[dict]) -> dict:
    return {
        "pump_metadata": {
            "serialNumber": "12345678",
            "modelNumber": "t:slim X2",
            "softwareVersion": "7.6.0",
            "lastUpload": "/Date(1705320000000)/",
        },
        "pumper_info": {"firstName": "Test", "lastName": "User"},
        "pump_events": pump_events,
        "therapy_timeline": None,
        "dashboard_summary": None,
    }


async def _setup_coordinator(hass: HomeAssistant, mock_data: dict):
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
    mock_client.get_pump_event_metadata = AsyncMock(return_value=[{
        "maxDateWithEvents": "2026-02-14T12:00:00",
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


def _build_binary_event(event_id: int, seq: int, ts_offset: int, payload: bytes) -> bytes:
    """Build a 26-byte binary event record for the decoder."""
    source_and_id = event_id & 0x0FFF
    header = struct.pack(">H", source_and_id)
    header += struct.pack(">I", ts_offset)
    header += struct.pack(">I", seq)
    # Pad payload to 16 bytes
    payload = payload.ljust(16, b'\x00')[:16]
    return header + payload


# ═══════════════════════════════════════════════════════════════════════
# Tests: Binary decoder for new event types
# ═══════════════════════════════════════════════════════════════════════


class TestNewEventDecoders:
    """Test binary decoding of the 10 new event types."""

    def _decode_single(self, event_id: int, payload: bytes, seq: int = 1) -> dict:
        raw = _build_binary_event(event_id, seq, 500000000, payload)
        b64 = base64.b64encode(raw).decode()
        events = decode_pump_events(b64)
        assert len(events) == 1
        return events[0]

    def test_decode_pumping_suspended(self):
        payload = struct.pack(">B", 0) + b'\x00\x00\x00' + struct.pack(">f", 1.5)
        evt = self._decode_single(11, payload)
        assert evt["event_name"] == "PumpingSuspended"
        assert evt["suspend_reason"] == "User"
        assert evt["insulin_amount"] == 1.5

    def test_decode_pumping_resumed(self):
        payload = struct.pack(">B", 2) + b'\x00\x00\x00' + struct.pack(">f", 0.0)
        evt = self._decode_single(12, payload)
        assert evt["event_name"] == "PumpingResumed"
        assert evt["pre_resume_state"] == 2

    def test_decode_bg_reading(self):
        payload = struct.pack(">H", 145) + b'\x00\x00' + struct.pack(">f", 3.2) + struct.pack(">B", 0)
        evt = self._decode_single(16, payload)
        assert evt["event_name"] == "BGReading"
        assert evt["bg_mgdl"] == 145
        assert evt["iob"] == 3.2
        assert evt["entry_type"] == "Manual"

    def test_decode_bolex_completed(self):
        payload = struct.pack(">HH", 500, 3) + struct.pack(">fff", 2.5, 1.0, 1.0)
        evt = self._decode_single(21, payload)
        assert evt["event_name"] == "BolexCompleted"
        assert evt["bolus_id"] == 500
        assert evt["insulin_delivered"] == 1.0
        assert evt["iob"] == 2.5

    def test_decode_cartridge_filled(self):
        payload = struct.pack(">f", 200.5)
        evt = self._decode_single(33, payload)
        assert evt["event_name"] == "CartridgeFilled"
        assert evt["insulin_volume"] == 200.5

    def test_decode_carbs_entered(self):
        payload = struct.pack(">f", 45.0)
        evt = self._decode_single(48, payload)
        assert evt["event_name"] == "CarbsEntered"
        assert evt["carbs"] == 45

    def test_decode_cannula_filled(self):
        payload = struct.pack(">f", 0.3) + struct.pack(">H", 0)
        evt = self._decode_single(61, payload)
        assert evt["event_name"] == "CannulaFilled"
        assert evt["prime_size"] == 0.3
        assert evt["completion_status"] == 0

    def test_decode_tubing_filled(self):
        payload = struct.pack(">f", 10.0) + struct.pack(">H", 0)
        evt = self._decode_single(63, payload)
        assert evt["event_name"] == "TubingFilled"
        assert evt["prime_size"] == 10.0

    def test_decode_user_mode_change(self):
        payload = struct.pack(">BB", 2, 0)  # Exercise, from Normal
        evt = self._decode_single(229, payload)
        assert evt["event_name"] == "UserModeChange"
        assert evt["current_mode"] == "Exercise"
        assert evt["previous_mode"] == "Normal"

    def test_decode_pcm_change(self):
        payload = struct.pack(">BB", 3, 1)  # Closed Loop, from Open Loop
        evt = self._decode_single(230, payload)
        assert evt["event_name"] == "PCMChange"
        assert evt["current_pcm"] == "Closed Loop"
        assert evt["previous_pcm"] == "Open Loop"

    def test_unknown_event_skipped(self):
        """Events we don't handle are skipped."""
        payload = b'\x00' * 16
        raw = _build_binary_event(999, 1, 500000000, payload)
        b64 = base64.b64encode(raw).decode()
        events = decode_pump_events(b64)
        assert len(events) == 0


# ═══════════════════════════════════════════════════════════════════════
# Tests: Computed CGM summary
# ═══════════════════════════════════════════════════════════════════════


class TestComputedCGMSummary:
    """Test _compute_cgm_summary populates avg glucose, TIR, SD, CV, GMI."""

    async def test_cgm_summary_basic(self, hass: HomeAssistant):
        """Test CGM summary with readings across range thresholds."""
        events = [
            # 3 in range, 1 below, 1 above = 60% TIR, 20% below, 20% above
            _make_cgm_event(1, 60, minutes_ago=20),   # below
            _make_cgm_event(2, 100, minutes_ago=15),   # in range
            _make_cgm_event(3, 130, minutes_ago=10),   # in range
            _make_cgm_event(4, 170, minutes_ago=5),    # in range
            _make_cgm_event(5, 200, minutes_ago=0),    # above
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        # Average: (60+100+130+170+200)/5 = 132
        assert coordinator.data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] == 132
        assert coordinator.data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] == round(132 * 0.0555, 1)
        assert coordinator.data[TANDEM_SENSOR_KEY_TIME_IN_RANGE] == 60.0
        assert coordinator.data[TANDEM_SENSOR_KEY_TIME_BELOW_RANGE] == 20.0
        assert coordinator.data[TANDEM_SENSOR_KEY_TIME_ABOVE_RANGE] == 20.0
        assert coordinator.data[TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV] is not UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_GLUCOSE_CV] is not UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_GMI] == round(3.31 + 0.02392 * 132, 1)

    async def test_cgm_summary_all_in_range(self, hass: HomeAssistant):
        """100% TIR when all readings are 70-180."""
        events = [
            _make_cgm_event(1, 100, minutes_ago=10),
            _make_cgm_event(2, 120, minutes_ago=5),
            _make_cgm_event(3, 140, minutes_ago=0),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_TIME_IN_RANGE] == 100.0
        assert coordinator.data[TANDEM_SENSOR_KEY_TIME_BELOW_RANGE] == 0.0
        assert coordinator.data[TANDEM_SENSOR_KEY_TIME_ABOVE_RANGE] == 0.0

    async def test_cgm_summary_no_events(self, hass: HomeAssistant):
        """CGM summary is UNAVAILABLE when no CGM events exist."""
        events = [_make_basal_delivery(1, 0.8)]  # No CGM events
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_TIME_IN_RANGE] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV] is UNAVAILABLE

    async def test_cgm_summary_single_reading(self, hass: HomeAssistant):
        """SD/CV unavailable with single reading, but avg/TIR still computed."""
        events = [_make_cgm_event(1, 150)]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] == 150
        assert coordinator.data[TANDEM_SENSOR_KEY_TIME_IN_RANGE] == 100.0
        assert coordinator.data[TANDEM_SENSOR_KEY_GLUCOSE_STD_DEV] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_GLUCOSE_CV] is UNAVAILABLE

    async def test_cgm_usage_calculated(self, hass: HomeAssistant):
        """CGM usage = readings / 288 * 100."""
        # 10 readings out of 288 expected per day
        events = [_make_cgm_event(i, 120, minutes_ago=i * 5) for i in range(10)]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        expected = round((10 / 288) * 100, 1)
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_USAGE] == expected


# ═══════════════════════════════════════════════════════════════════════
# Tests: New event-derived sensors
# ═══════════════════════════════════════════════════════════════════════


class TestNewEventSensors:
    """Test sensor population from new event types."""

    async def test_activity_mode_exercise(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 120),
            _make_user_mode_event(2, "Exercise", 2),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVITY_MODE] == "Exercise"

    async def test_activity_mode_sleep(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 120),
            _make_user_mode_event(2, "Sleep", 1),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVITY_MODE] == "Sleep"

    async def test_activity_mode_unavailable_when_no_events(self, hass: HomeAssistant):
        events = [_make_cgm_event(1, 120)]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVITY_MODE] is UNAVAILABLE

    async def test_control_iq_mode(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 120),
            _make_pcm_event(2, "Closed Loop"),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)
        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_MODE] == "Closed Loop"

    async def test_pump_suspended(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 120),
            _make_suspend_event(2, minutes_ago=5),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)
        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_SUSPENDED] == "Suspended"

    async def test_pump_resumed(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 120),
            _make_suspend_event(2, minutes_ago=10),
            _make_resume_event(3, minutes_ago=5),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)
        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_SUSPENDED] == "Active"

    async def test_last_carbs(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 120),
            _make_carbs_event(2, 30, minutes_ago=10),
            _make_carbs_event(3, 45, minutes_ago=0),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARBS] == 45

    async def test_last_cartridge_change(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 120),
            _make_cartridge_event(2, 200.0),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_CHANGE] is not UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_CARTRIDGE_INSULIN] == 200.0

    async def test_last_site_change(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 120),
            _make_cannula_event(2),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_SITE_CHANGE] is not UNAVAILABLE

    async def test_last_tubing_change(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 120),
            _make_tubing_event(2),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_TUBING_CHANGE] is not UNAVAILABLE

    async def test_last_bg_reading(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 120),
            _make_bg_event(2, 145),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BG_READING] == 145


# ═══════════════════════════════════════════════════════════════════════
# Tests: Computed insulin summary
# ═══════════════════════════════════════════════════════════════════════


class TestComputedInsulinSummary:
    """Test _compute_insulin_summary for TDI, bolus/basal totals, carbs."""

    async def test_basic_insulin_summary(self, hass: HomeAssistant):
        """Test TDI with bolus + basal events."""
        events = [
            _make_cgm_event(1, 120),
            _make_bolus_completed(2, delivered=3.0, iob=5.0, minutes_ago=60),
            _make_bolus_completed(3, delivered=2.0, iob=4.5, minutes_ago=30),
            _make_basal_delivery(4, rate=0.8, minutes_ago=60),
            _make_basal_delivery(5, rate=1.0, minutes_ago=30),
            _make_basal_delivery(6, rate=0.8, minutes_ago=0),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        # Bolus total: 3.0 + 2.0 = 5.0
        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_BOLUS_TOTAL] == 5.0
        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_BOLUS_COUNT] == 2
        # Basal total: 0.8 * 0.5h + 1.0 * 0.5h + 0.8 * (5/60)h
        # = 0.4 + 0.5 + 0.067 ≈ 0.97
        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_BASAL_TOTAL] is not UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_TOTAL_DAILY_INSULIN] is not UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_BASAL_BOLUS_SPLIT] is not UNAVAILABLE

    async def test_daily_carbs_summed(self, hass: HomeAssistant):
        """Test daily carbs from CARBS_ENTERED events."""
        events = [
            _make_cgm_event(1, 120),
            _make_carbs_event(2, 30, minutes_ago=60),
            _make_carbs_event(3, 45, minutes_ago=30),
            _make_carbs_event(4, 20, minutes_ago=0),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_CARBS] == 95  # 30+45+20

    async def test_no_bolus_events_unavailable(self, hass: HomeAssistant):
        """Bolus sensors unavailable when no bolus events."""
        events = [
            _make_cgm_event(1, 120),
            _make_basal_delivery(2, rate=0.8),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_BOLUS_TOTAL] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_BOLUS_COUNT] is UNAVAILABLE

    async def test_no_carbs_unavailable(self, hass: HomeAssistant):
        events = [_make_cgm_event(1, 120)]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_CARBS] is UNAVAILABLE
