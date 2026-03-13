"""Tests for expanded data sources: new event decoders, computed summaries, new sensors."""

from __future__ import annotations

import struct
import base64
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

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
    # Battery sensors
    TANDEM_SENSOR_KEY_BATTERY_PERCENT,
    TANDEM_SENSOR_KEY_BATTERY_VOLTAGE,
    TANDEM_SENSOR_KEY_BATTERY_REMAINING_MAH,
    TANDEM_SENSOR_KEY_CHARGING_STATUS,
)

from custom_components.carelink.tandem_api import decode_pump_events


# ── Helpers ──────────────────────────────────────────────────────────

# Use midday UTC today so events remain "today" even in far-west timezones
# (e.g. US/Pacific = UTC-8).  Using plain datetime.now(utc) would fail if
# the Docker host clock is near midnight UTC.
_now = datetime.now(timezone.utc)
BASE_TS = _now.replace(hour=12, minute=0, second=0, microsecond=0)


def _make_cgm_event(seq: int, glucose_mgdl: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 256,
        "event_name": "CGM",
        "seq": seq,
        "timestamp": ts,
        "glucose_mgdl": glucose_mgdl,
        "rate_of_change": 0.5,
        "status": 0,
    }


def _make_bolus_completed(seq: int, delivered: float, iob: float, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 20,
        "event_name": "BolusCompleted",
        "seq": seq,
        "timestamp": ts,
        "bolus_id": 100 + seq,
        "completion_status": 3,
        "iob": iob,
        "insulin_delivered": delivered,
        "insulin_requested": delivered,
    }


def _make_basal_delivery(seq: int, rate: float, source: int = 1, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 279,
        "event_name": "BasalDelivery",
        "seq": seq,
        "timestamp": ts,
        "commanded_source": source,
        "commanded_rate": rate,
        "profile_rate_mu": int(0.8 * 1000),
    }


def _make_carbs_event(seq: int, carbs: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 48,
        "event_name": "CarbsEntered",
        "seq": seq,
        "timestamp": ts,
        "carbs": carbs,
    }


def _make_user_mode_event(seq: int, current_mode: str, mode_id: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 229,
        "event_name": "UserModeChange",
        "seq": seq,
        "timestamp": ts,
        "current_mode": current_mode,
        "previous_mode": "Normal",
        "current_mode_id": mode_id,
        "previous_mode_id": 0,
    }


def _make_pcm_event(seq: int, current_pcm: str, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 230,
        "event_name": "PCMChange",
        "seq": seq,
        "timestamp": ts,
        "current_pcm": current_pcm,
        "previous_pcm": "No Control",
    }


def _make_suspend_event(seq: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 11,
        "event_name": "PumpingSuspended",
        "seq": seq,
        "timestamp": ts,
        "suspend_reason": "User",
        "suspend_reason_id": 0,
        "insulin_amount": 0.5,
    }


def _make_resume_event(seq: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 12,
        "event_name": "PumpingResumed",
        "seq": seq,
        "timestamp": ts,
        "pre_resume_state": 0,
        "insulin_amount": 0.0,
    }


def _make_cartridge_event(seq: int, volume: float, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 33,
        "event_name": "CartridgeFilled",
        "seq": seq,
        "timestamp": ts,
        "insulin_volume": volume,
    }


def _make_cannula_event(seq: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 61,
        "event_name": "CannulaFilled",
        "seq": seq,
        "timestamp": ts,
        "prime_size": 0.3,
        "completion_status": 0,
    }


def _make_tubing_event(seq: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 63,
        "event_name": "TubingFilled",
        "seq": seq,
        "timestamp": ts,
        "prime_size": 10.0,
        "completion_status": 0,
    }


def _make_bg_event(seq: int, bg_mgdl: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 16,
        "event_name": "BGReading",
        "seq": seq,
        "timestamp": ts,
        "bg_mgdl": bg_mgdl,
        "iob": 2.5,
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
    mock_client.get_pump_event_metadata = AsyncMock(
        return_value=[
            {
                "maxDateWithEvents": "2026-02-14T12:00:00",
            }
        ]
    )
    mock_client.close = AsyncMock()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        TANDEM_CLIENT: mock_client,
        PLATFORM_TYPE: PLATFORM_TANDEM,
    }

    # Pin to UTC so date comparisons in _compute_insulin_summary are
    # consistent regardless of the CI runner's local timezone.
    hass.config.time_zone = "UTC"

    coordinator = TandemCoordinator(hass, entry, update_interval=timedelta(seconds=300))
    await coordinator.async_config_entry_first_refresh()
    return coordinator


def _build_binary_event(event_id: int, seq: int, ts_offset: int, payload: bytes) -> bytes:
    """Build a 26-byte binary event record for the decoder."""
    source_and_id = event_id & 0x0FFF
    header = struct.pack(">H", source_and_id)
    header += struct.pack(">I", ts_offset)
    header += struct.pack(">I", seq)
    # Pad payload to 16 bytes
    payload = payload.ljust(16, b"\x00")[:16]
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
        payload = struct.pack(">B", 0) + b"\x00\x00\x00" + struct.pack(">f", 1.5)
        evt = self._decode_single(11, payload)
        assert evt["event_name"] == "PumpingSuspended"
        assert evt["suspend_reason"] == "User"
        assert evt["insulin_amount"] == 1.5

    def test_decode_pumping_resumed(self):
        payload = struct.pack(">B", 2) + b"\x00\x00\x00" + struct.pack(">f", 0.0)
        evt = self._decode_single(12, payload)
        assert evt["event_name"] == "PumpingResumed"
        assert evt["pre_resume_state"] == 2

    def test_decode_bg_reading(self):
        payload = struct.pack(">H", 145) + b"\x00\x00" + struct.pack(">f", 3.2) + struct.pack(">B", 0)
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

    def test_decode_cgm_data_event(self):
        """Event 256 (CGM_DATA_GXB) decodes glucose, rate of change and status."""
        # int8 @ offset 0 (rate_raw), uint16 @ offset 2 (status), uint16 @ offset 4 (glucose)
        payload = struct.pack(">b", 5) + b"\x00" + struct.pack(">H", 0) + struct.pack(">H", 120)
        evt = self._decode_single(256, payload)
        assert evt["event_name"] == "CGM"
        assert evt["glucose_mgdl"] == 120
        assert evt["rate_of_change"] == 0.5  # 5 * 0.1
        assert evt["status"] == 0

    def test_decode_cgm_data_event_rate_zero(self):
        """Event 256 with rate_raw=0 and non-zero status decodes correctly."""
        payload = struct.pack(">b", 0) + b"\x00" + struct.pack(">H", 1) + struct.pack(">H", 85)
        evt = self._decode_single(256, payload)
        assert evt["rate_of_change"] == 0.0
        assert evt["glucose_mgdl"] == 85
        assert evt["status"] == 1

    def test_decode_bolus_delivery_event(self):
        """Event 280 (BolusDelivery) decodes type, status, correction and delivered."""
        payload = (
            struct.pack(">B", 1)  # bolus_type
            + struct.pack(">B", 0)  # delivery_status = 0 (completed)
            + struct.pack(">H", 42)  # bolus_id
            + struct.pack(">H", 2000)  # requested_now_mu
            + b"\x00\x00"  # unknown
            + struct.pack(">H", 500)  # correction_mu
            + b"\x00\x00"  # unknown
            + struct.pack(">H", 2000)  # delivered_total_mu
        )
        evt = self._decode_single(280, payload)
        assert evt["event_name"] == "BolusDelivery"
        assert evt["delivery_status"] == 0
        assert evt["correction_mu"] == 500
        assert evt["insulin_delivered"] == 2.0  # 2000 / 1000

    def test_decode_bolus_delivery_no_correction(self):
        """Event 280 with correction_mu=0 and delivery_status=1 (started)."""
        payload = (
            struct.pack(">B", 0)  # bolus_type
            + struct.pack(">B", 1)  # delivery_status = 1
            + struct.pack(">H", 1)  # bolus_id
            + struct.pack(">H", 1000)  # requested_now_mu
            + b"\x00\x00"  # unknown
            + struct.pack(">H", 0)  # correction_mu = 0
            + b"\x00\x00"  # unknown
            + struct.pack(">H", 1000)  # delivered_total_mu
        )
        evt = self._decode_single(280, payload)
        assert evt["correction_mu"] == 0
        assert evt["delivery_status"] == 1

    def test_decode_unknown_suspend_reason(self):
        """Event 11 with an unrecognised reason code falls back to 'Unknown (N)'."""
        payload = struct.pack(">B", 99) + b"\x00\x00\x00" + struct.pack(">f", 0.0)
        evt = self._decode_single(11, payload)
        assert evt["suspend_reason"] == "Unknown (99)"

    def test_unknown_event_skipped(self):
        """Events we don't handle are skipped."""
        payload = b"\x00" * 16
        raw = _build_binary_event(999, 1, 500000000, payload)
        b64 = base64.b64encode(raw).decode()
        events = decode_pump_events(b64)
        assert len(events) == 0

    def test_decode_bolus_completed(self):
        """Event 20 (EVT_BOLUS_COMPLETED) is decoded correctly."""
        payload = (
            struct.pack(">H", 7)  # bolus_id
            + struct.pack(">H", 3)  # completion (3=completed)
            + struct.pack(">f", 1.5)  # iob
            + struct.pack(">f", 2.0)  # delivered
            + struct.pack(">f", 2.0)  # requested
        )
        evt = self._decode_single(20, payload)
        assert evt["event_name"] == "BolusCompleted"
        assert evt["bolus_id"] == 7
        assert evt["completion_status"] == 3
        assert evt["iob"] == 1.5
        assert evt["insulin_delivered"] == 2.0
        assert evt["insulin_requested"] == 2.0

    def test_decode_basal_rate_change(self):
        """Event 3 (EVT_BASAL_RATE_CHANGE) is decoded correctly."""
        payload = (
            struct.pack(">f", 0.85)  # commanded_rate
            + struct.pack(">f", 0.80)  # base_rate
            + struct.pack(">f", 2.0)  # max_rate
            + b"\x00\x00\x00\x00\x00"  # padding to byte 13
        )
        # Insert change_type at byte 13
        payload = payload[:12] + b"\x00" + struct.pack(">B", 2)
        evt = self._decode_single(3, payload)
        assert evt["event_name"] == "BasalRateChange"
        assert evt["commanded_rate"] == 0.85
        assert evt["base_rate"] == 0.8
        assert evt["change_type"] == 2

    def test_decode_basal_delivery(self):
        """Event 279 (EVT_BASAL_DELIVERY) is decoded correctly."""
        payload = (
            b"\x00\x00"  # bytes 0-1 (unused)
            + struct.pack(">H", 1)  # commanded_source at offset 2
            + struct.pack(">H", 850)  # profile_rate at offset 4 (milliunits/hr)
            + struct.pack(">H", 800)  # commanded_rate at offset 6 (milliunits/hr)
        )
        evt = self._decode_single(279, payload)
        assert evt["event_name"] == "BasalDelivery"
        assert evt["commanded_source"] == 1
        assert evt["profile_rate_mu"] == 850
        assert evt["commanded_rate_mu"] == 800
        assert evt["commanded_rate"] == 0.8

    def test_decode_base64_error_returns_empty(self):
        """Invalid base64 input returns empty list without raising."""
        events = decode_pump_events("!!!invalid base64!!!")
        assert events == []

    def test_decode_truncated_chunk_skipped(self):
        """A record shorter than EVENT_LEN is skipped gracefully."""
        # Build a valid 26-byte event then truncate to 20 bytes
        payload = b"\x00" * 16
        raw = _build_binary_event(256, 1, 500000000, payload)
        truncated = raw[:20]  # shorter than 26-byte EVENT_LEN
        b64 = base64.b64encode(truncated).decode()
        events = decode_pump_events(b64)
        assert events == []


# ═══════════════════════════════════════════════════════════════════════
# Tests: Computed CGM summary
# ═══════════════════════════════════════════════════════════════════════


class TestComputedCGMSummary:
    """Test _compute_cgm_summary populates avg glucose, TIR, SD, CV, GMI."""

    async def test_cgm_summary_basic(self, hass: HomeAssistant):
        """Test CGM summary with readings across range thresholds."""
        events = [
            # 3 in range, 1 below, 1 above = 60% TIR, 20% below, 20% above
            _make_cgm_event(1, 60, minutes_ago=20),  # below
            _make_cgm_event(2, 100, minutes_ago=15),  # in range
            _make_cgm_event(3, 130, minutes_ago=10),  # in range
            _make_cgm_event(4, 170, minutes_ago=5),  # in range
            _make_cgm_event(5, 200, minutes_ago=0),  # above
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


# ═══════════════════════════════════════════════════════════════════════
# Tests: Battery event decoders (events 36, 37, 53, 81)
# ═══════════════════════════════════════════════════════════════════════


class TestBatteryEventDecoders:
    """Test binary decoding of battery-related event types."""

    def _decode_single(self, event_id: int, payload: bytes, seq: int = 1) -> dict:
        raw = _build_binary_event(event_id, seq, 500000000, payload)
        b64 = base64.b64encode(raw).decode()
        events = decode_pump_events(b64)
        assert len(events) == 1
        return events[0]

    def test_decode_usb_connected(self):
        """Event 36 (USBConnected) decodes negotiated current."""
        payload = struct.pack(">f", 500.0)
        evt = self._decode_single(36, payload)
        assert evt["event_name"] == "USBConnected"
        assert evt["negotiated_current_ma"] == 500.0

    def test_decode_usb_disconnected(self):
        """Event 37 (USBDisconnected) decodes negotiated current."""
        payload = struct.pack(">f", 100.0)
        evt = self._decode_single(37, payload)
        assert evt["event_name"] == "USBDisconnected"
        assert evt["negotiated_current_ma"] == 100.0

    def test_decode_usb_connected_zero_current(self):
        """Event 36 with zero negotiated current."""
        payload = struct.pack(">f", 0.0)
        evt = self._decode_single(36, payload)
        assert evt["negotiated_current_ma"] == 0.0

    def test_decode_shelf_mode(self):
        """Event 53 (ShelfMode) decodes full battery detail."""
        payload = (
            struct.pack(">I", 12345678)  # msec_since_reset
            + struct.pack(">B", 75)  # lipo_ibc (battery %)
            + struct.pack(">B", 73)  # lipo_abc (alt battery %)
            + struct.pack(">h", -120)  # lipo_current (mA, signed — negative = discharging)
            + struct.pack(">I", 280)  # lipo_rem_cap (mAh)
            + struct.pack(">I", 3850)  # lipo_mv (mV)
        )
        evt = self._decode_single(53, payload)
        assert evt["event_name"] == "ShelfMode"
        assert evt["msec_since_reset"] == 12345678
        assert evt["battery_percent"] == 75
        assert evt["battery_percent_alt"] == 73
        assert evt["battery_current_ma"] == -120
        assert evt["battery_remaining_mah"] == 280
        assert evt["battery_voltage_mv"] == 3850

    def test_decode_shelf_mode_zero_battery(self):
        """Event 53 with 0% battery and zero remaining capacity."""
        payload = (
            struct.pack(">I", 0)
            + struct.pack(">B", 0)
            + struct.pack(">B", 0)
            + struct.pack(">h", 0)
            + struct.pack(">I", 0)
            + struct.pack(">I", 3200)
        )
        evt = self._decode_single(53, payload)
        assert evt["battery_percent"] == 0
        assert evt["battery_remaining_mah"] == 0
        assert evt["battery_voltage_mv"] == 3200

    def test_decode_shelf_mode_full_battery(self):
        """Event 53 with 100% battery."""
        payload = (
            struct.pack(">I", 999)
            + struct.pack(">B", 100)
            + struct.pack(">B", 100)
            + struct.pack(">h", 500)  # positive = charging
            + struct.pack(">I", 450)
            + struct.pack(">I", 4200)
        )
        evt = self._decode_single(53, payload)
        assert evt["battery_percent"] == 100
        assert evt["battery_current_ma"] == 500
        assert evt["battery_remaining_mah"] == 450

    def test_decode_daily_basal(self):
        """Event 81 (DailyBasal) decodes battery + insulin data."""
        # Battery formula: min(100, max(0, round((256*(MSB-14)+LSB) / (3*256) * 100, 1)))
        # MSB=16, LSB=128: (256*(16-14)+128) / 768 * 100 = (512+128)/768*100 = 83.3%
        payload = (
            struct.pack(">f", 24.5)  # daily_total_basal
            + struct.pack(">f", 0.8)  # last_basal_rate
            + struct.pack(">f", 3.2)  # iob
            + struct.pack(">B", 16)  # battery_msb_raw
            + struct.pack(">B", 128)  # battery_lsb_raw
        )
        evt = self._decode_single(81, payload)
        assert evt["event_name"] == "DailyBasal"
        assert evt["daily_total_basal"] == 24.5
        assert evt["last_basal_rate"] == 0.8
        assert evt["iob"] == 3.2
        assert evt["battery_percent"] == 83.3
        assert "battery_voltage_mv" not in evt  # voltage only from ShelfMode

    def test_daily_basal_battery_formula_zero_percent(self):
        """Battery formula clamps to 0% for low MSB values."""
        # MSB=14, LSB=0: (256*(14-14)+0) / 768 * 100 = 0%
        payload = (
            struct.pack(">f", 0.0)
            + struct.pack(">f", 0.0)
            + struct.pack(">f", 0.0)
            + struct.pack(">B", 14)
            + struct.pack(">B", 0)
            # bytes 14-15 no longer decoded (not millivolts)
        )
        evt = self._decode_single(81, payload)
        assert evt["battery_percent"] == 0.0

    def test_daily_basal_battery_formula_full(self):
        """Battery formula clamps to 100% for high MSB values."""
        # MSB=17, LSB=255: (256*(17-14)+255) / 768 * 100 = 133.2% → clamped to 100
        payload = (
            struct.pack(">f", 0.0)
            + struct.pack(">f", 0.0)
            + struct.pack(">f", 0.0)
            + struct.pack(">B", 17)
            + struct.pack(">B", 255)
            # bytes 14-15 no longer decoded (not millivolts)
        )
        evt = self._decode_single(81, payload)
        assert evt["battery_percent"] == 100

    def test_daily_basal_battery_formula_underflow(self):
        """Battery formula clamps to 0% when MSB < 14."""
        # MSB=10, LSB=0: (256*(10-14)+0) / 768 * 100 = negative → clamped to 0
        payload = (
            struct.pack(">f", 0.0)
            + struct.pack(">f", 0.0)
            + struct.pack(">f", 0.0)
            + struct.pack(">B", 10)
            + struct.pack(">B", 0)
            # bytes 14-15 no longer decoded (not millivolts)
        )
        evt = self._decode_single(81, payload)
        assert evt["battery_percent"] == 0


# ═══════════════════════════════════════════════════════════════════════
# Tests: Battery sensor population in coordinator
# ═══════════════════════════════════════════════════════════════════════


def _make_daily_basal_event(
    seq: int,
    battery_pct_msb: int = 16,
    battery_pct_lsb: int = 128,
    minutes_ago: int = 0,
) -> dict:
    """Create a pre-decoded DailyBasal event dict (as coordinator receives it).

    DailyBasal no longer includes battery_voltage_mv — the raw value at
    offset 14 is not actual millivolts.  Voltage comes from ShelfMode only.
    """
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    battery_pct = min(100, max(0, round((256 * (battery_pct_msb - 14) + battery_pct_lsb) / (3 * 256) * 100, 1)))
    return {
        "event_id": 81,
        "event_name": "DailyBasal",
        "seq": seq,
        "timestamp": ts,
        "daily_total_basal": 20.0,
        "last_basal_rate": 0.8,
        "iob": 2.5,
        "battery_percent": battery_pct,
    }


def _make_shelf_mode_event(
    seq: int,
    battery_pct: int = 75,
    battery_mv: int = 3850,
    battery_mah: int = 280,
    minutes_ago: int = 0,
) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 53,
        "event_name": "ShelfMode",
        "seq": seq,
        "timestamp": ts,
        "msec_since_reset": 12345,
        "battery_percent": battery_pct,
        "battery_percent_alt": battery_pct - 2,
        "battery_current_ma": -50,
        "battery_remaining_mah": battery_mah,
        "battery_voltage_mv": battery_mv,
    }


def _make_usb_connected_event(seq: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 36,
        "event_name": "USBConnected",
        "seq": seq,
        "timestamp": ts,
        "negotiated_current_ma": 500.0,
    }


def _make_usb_disconnected_event(seq: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 37,
        "event_name": "USBDisconnected",
        "seq": seq,
        "timestamp": ts,
        "negotiated_current_ma": 0.0,
    }


class TestBatterySensorPopulation:
    """Test coordinator battery sensor population from events 36, 37, 53, 81."""

    async def test_daily_basal_provides_battery(self, hass: HomeAssistant):
        """DailyBasal event populates battery % but not voltage."""
        events = [
            _make_cgm_event(1, 120),
            _make_daily_basal_event(2, battery_pct_msb=16, battery_pct_lsb=128),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_PERCENT] == 83.3
        # Voltage only comes from ShelfMode (DailyBasal raw value is not mV)
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_VOLTAGE] is UNAVAILABLE
        # mAh only comes from ShelfMode
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_REMAINING_MAH] is UNAVAILABLE

    async def test_shelf_mode_provides_full_battery(self, hass: HomeAssistant):
        """ShelfMode event populates battery %, voltage, and mAh."""
        events = [
            _make_cgm_event(1, 120),
            _make_shelf_mode_event(2, battery_pct=75, battery_mv=3850, battery_mah=280),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_PERCENT] == 75
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_VOLTAGE] == 3850
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_REMAINING_MAH] == 280

    async def test_shelf_mode_newer_overrides_daily_basal(self, hass: HomeAssistant):
        """When ShelfMode is newer than DailyBasal, ShelfMode values win."""
        events = [
            _make_cgm_event(1, 120),
            _make_daily_basal_event(2, battery_pct_msb=16, battery_pct_lsb=128, minutes_ago=30),
            _make_shelf_mode_event(3, battery_pct=72, battery_mv=3800, battery_mah=260, minutes_ago=5),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_PERCENT] == 72
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_VOLTAGE] == 3800
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_REMAINING_MAH] == 260

    async def test_daily_basal_newer_keeps_daily_basal_pct(self, hass: HomeAssistant):
        """When DailyBasal is newer than ShelfMode, DailyBasal % wins, voltage from ShelfMode."""
        events = [
            _make_cgm_event(1, 120),
            _make_shelf_mode_event(2, battery_pct=80, battery_mv=3900, battery_mah=300, minutes_ago=60),
            _make_daily_basal_event(3, battery_pct_msb=16, battery_pct_lsb=128, minutes_ago=5),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        # DailyBasal is newer → its % used
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_PERCENT] == 83.3
        # Voltage always from ShelfMode (DailyBasal raw value is not mV)
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_VOLTAGE] == 3900
        # mAh still comes from ShelfMode (only source)
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_REMAINING_MAH] == 300

    async def test_usb_connected_shows_charging(self, hass: HomeAssistant):
        """USB connected event sets charging status to 'Charging'."""
        events = [
            _make_cgm_event(1, 120),
            _make_usb_connected_event(2),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_CHARGING_STATUS] == "Charging"

    async def test_usb_disconnected_shows_not_charging(self, hass: HomeAssistant):
        """USB disconnected event sets charging status to 'Not Charging'."""
        events = [
            _make_cgm_event(1, 120),
            _make_usb_disconnected_event(2),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_CHARGING_STATUS] == "Not Charging"

    async def test_usb_connect_then_disconnect(self, hass: HomeAssistant):
        """Latest USB event determines charging status."""
        events = [
            _make_cgm_event(1, 120),
            _make_usb_connected_event(2, minutes_ago=10),
            _make_usb_disconnected_event(3, minutes_ago=5),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_CHARGING_STATUS] == "Not Charging"

    async def test_no_battery_events_all_unavailable(self, hass: HomeAssistant):
        """No battery events → all battery sensors UNAVAILABLE."""
        events = [_make_cgm_event(1, 120)]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_PERCENT] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_VOLTAGE] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_REMAINING_MAH] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_CHARGING_STATUS] is UNAVAILABLE

    async def test_all_battery_events_combined(self, hass: HomeAssistant):
        """All battery event types present — most recent values used."""
        events = [
            _make_cgm_event(1, 120),
            _make_daily_basal_event(2, battery_pct_msb=16, battery_pct_lsb=128, minutes_ago=60),
            _make_shelf_mode_event(3, battery_pct=70, battery_mv=3800, battery_mah=250, minutes_ago=30),
            _make_usb_connected_event(4, minutes_ago=10),
        ]
        data = _make_pump_events_data(events)
        coordinator = await _setup_coordinator(hass, data)

        # ShelfMode is newer than DailyBasal
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_PERCENT] == 70
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_VOLTAGE] == 3800
        assert coordinator.data[TANDEM_SENSOR_KEY_BATTERY_REMAINING_MAH] == 250
        assert coordinator.data[TANDEM_SENSOR_KEY_CHARGING_STATUS] == "Charging"
