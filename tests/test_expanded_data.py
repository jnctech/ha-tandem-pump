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
    # Alert & Alarm sensors (Phase 2)
    TANDEM_SENSOR_KEY_LAST_ALERT,
    TANDEM_SENSOR_KEY_LAST_ALARM,
    TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT,
    TANDEM_ALERT_MAP,
    TANDEM_ALARM_MAP,
    # CGM sensor type (Phase 3)
    TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE,
    # Bolus Calculator (Phase 4)
    TANDEM_SENSOR_KEY_LAST_BOLUS_BG,
    TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS,
    TANDEM_SENSOR_KEY_LAST_BOLUS_CORRECTION,
    TANDEM_SENSOR_KEY_LAST_BOLUS_FOOD,
    TANDEM_SENSOR_KEY_BOLUS_CALC_ATTRS,
    # PLGS & Daily Status (Phase 5)
    TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE,
    # Estimated Remaining Insulin (Phase 6)
    TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING,
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


# ── Alert / Alarm helpers ─────────────────────────────────────────────────


def _make_alert_activated(seq: int, alert_id: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 4,
        "event_name": "AlertActivated",
        "seq": seq,
        "timestamp": ts,
        "alert_id": alert_id,
        "fault_locator": 0,
        "param1": 0,
        "param2": 0.0,
    }


def _make_alert_cleared(seq: int, alert_id: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 26,
        "event_name": "AlertCleared",
        "seq": seq,
        "timestamp": ts,
        "alert_id": alert_id,
    }


def _make_alarm_activated(seq: int, alarm_id: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 5,
        "event_name": "AlarmActivated",
        "seq": seq,
        "timestamp": ts,
        "alert_id": alarm_id,
        "fault_locator": 0,
        "param1": 0,
        "param2": 0.0,
    }


def _make_alarm_cleared(seq: int, alarm_id: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 28,
        "event_name": "AlarmCleared",
        "seq": seq,
        "timestamp": ts,
        "alert_id": alarm_id,
    }


def _make_malfunction_activated(seq: int, malfunction_id: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 6,
        "event_name": "MalfunctionActivated",
        "seq": seq,
        "timestamp": ts,
        "alert_id": malfunction_id,
        "fault_locator": 1,
        "param1": 0,
        "param2": 0.0,
    }


# ── Decoder tests: events 4, 5, 6, 26, 28 ────────────────────────────────


class TestAlertAlarmDecoders:
    """Test binary decoding of alert and alarm event types."""

    def _decode_single(self, event_id: int, payload: bytes, seq: int = 1) -> dict:
        raw = _build_binary_event(event_id, seq, 500000000, payload)
        b64 = base64.b64encode(raw).decode()
        events = decode_pump_events(b64)
        assert len(events) == 1
        return events[0]

    def _alert_payload(self, alert_id: int, fault: int = 0, p1: int = 0, p2: float = 0.0) -> bytes:
        return struct.pack(">I", alert_id) + struct.pack(">I", fault) + struct.pack(">I", p1) + struct.pack(">f", p2)

    def test_decode_alert_activated(self):
        """Event 4 (AlertActivated) decodes alert_id and params."""
        payload = self._alert_payload(alert_id=0, fault=5, p1=10, p2=1.5)
        evt = self._decode_single(4, payload)
        assert evt["event_name"] == "AlertActivated"
        assert evt["alert_id"] == 0
        assert evt["fault_locator"] == 5
        assert evt["param1"] == 10
        assert abs(evt["param2"] - 1.5) < 0.001

    def test_decode_alarm_activated(self):
        """Event 5 (AlarmActivated) decodes alarm_id."""
        payload = self._alert_payload(alert_id=2)
        evt = self._decode_single(5, payload)
        assert evt["event_name"] == "AlarmActivated"
        assert evt["alert_id"] == 2

    def test_decode_malfunction_activated(self):
        """Event 6 (MalfunctionActivated) decodes malfunction_id."""
        payload = self._alert_payload(alert_id=14, fault=99)
        evt = self._decode_single(6, payload)
        assert evt["event_name"] == "MalfunctionActivated"
        assert evt["alert_id"] == 14
        assert evt["fault_locator"] == 99

    def test_decode_alert_cleared(self):
        """Event 26 (AlertCleared) decodes only alert_id."""
        payload = struct.pack(">I", 0) + bytes(12)
        evt = self._decode_single(26, payload)
        assert evt["event_name"] == "AlertCleared"
        assert evt["alert_id"] == 0

    def test_decode_alarm_cleared(self):
        """Event 28 (AlarmCleared) decodes only alarm_id."""
        payload = struct.pack(">I", 8) + bytes(12)
        evt = self._decode_single(28, payload)
        assert evt["event_name"] == "AlarmCleared"
        assert evt["alert_id"] == 8

    def test_decode_alert_activated_known_id(self):
        """AlertActivated with a known ID resolves to name in TANDEM_ALERT_MAP."""
        payload = self._alert_payload(alert_id=0)
        evt = self._decode_single(4, payload)
        assert TANDEM_ALERT_MAP.get(evt["alert_id"]) == "Low Insulin"

    def test_decode_alarm_activated_known_id(self):
        """AlarmActivated with a known ID resolves to name in TANDEM_ALARM_MAP."""
        payload = self._alert_payload(alert_id=2)
        evt = self._decode_single(5, payload)
        assert TANDEM_ALARM_MAP.get(evt["alert_id"]) == "Occlusion"


# ── Coordinator tests: alert/alarm sensor population ─────────────────────


class TestAlertAlarmCoordinator:
    """Test coordinator alert/alarm sensor population from events 4, 5, 6, 26, 28."""

    async def test_no_events_all_unavailable(self, hass: HomeAssistant):
        """No alert/alarm events → sensors are UNAVAILABLE."""
        data = _make_pump_events_data([_make_cgm_event(1, 100)])
        coordinator = await _setup_coordinator(hass, data)
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_ALERT] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_ALARM] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] == 0

    async def test_single_alert_activated(self, hass: HomeAssistant):
        """Single AlertActivated → last_alert = known name, count = 1."""
        events = [
            _make_cgm_event(1, 100),
            _make_alert_activated(2, alert_id=0),  # "Low Insulin"
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_ALERT] == "Low Insulin"
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] == 1

    async def test_alert_activated_unknown_id(self, hass: HomeAssistant):
        """AlertActivated with unknown ID → fallback 'Alert <id>'."""
        events = [
            _make_cgm_event(1, 100),
            _make_alert_activated(2, alert_id=999),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_ALERT] == "Alert 999"

    async def test_alert_cleared_reduces_count(self, hass: HomeAssistant):
        """AlertActivated then AlertCleared → count = 0, last_alert still set."""
        events = [
            _make_cgm_event(1, 100),
            _make_alert_activated(2, alert_id=0, minutes_ago=10),
            _make_alert_cleared(3, alert_id=0, minutes_ago=5),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_ALERT] == "Low Insulin"
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] == 0
        # Attributes reflect cleared=True
        attrs = coordinator.data.get(f"{TANDEM_SENSOR_KEY_LAST_ALERT}_attributes", {})
        assert attrs["cleared"] is True

    async def test_alert_attributes_structure(self, hass: HomeAssistant):
        """last_alert attributes contain expected keys."""
        events = [
            _make_cgm_event(1, 100),
            _make_alert_activated(2, alert_id=0),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        attrs = coordinator.data.get(f"{TANDEM_SENSOR_KEY_LAST_ALERT}_attributes", {})
        assert "alert_id" in attrs
        assert "cleared" in attrs
        assert "timestamp" in attrs
        assert "recent" in attrs
        assert isinstance(attrs["recent"], list)

    async def test_recent_list_capped_at_10(self, hass: HomeAssistant):
        """recent list in attributes is capped at 10 entries."""
        events = [_make_cgm_event(1, 100)] + [
            _make_alert_activated(i + 2, alert_id=i % 5, minutes_ago=100 - i) for i in range(15)
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        attrs = coordinator.data.get(f"{TANDEM_SENSOR_KEY_LAST_ALERT}_attributes", {})
        assert len(attrs["recent"]) <= 10

    async def test_single_alarm_activated(self, hass: HomeAssistant):
        """Single AlarmActivated → last_alarm = known name."""
        events = [
            _make_cgm_event(1, 100),
            _make_alarm_activated(2, alarm_id=2),  # "Occlusion"
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_ALARM] == "Occlusion"
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] == 1

    async def test_malfunction_activates_alarm_sensor(self, hass: HomeAssistant):
        """MalfunctionActivated (event 6) populates last_alarm sensor with resolved name."""
        events = [
            _make_cgm_event(1, 100),
            _make_malfunction_activated(2, malfunction_id=14),  # 14 = "Software Error"
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_ALARM] == "Software Error"
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] == 1

    async def test_malfunction_cleared_by_alarm_cleared(self, hass: HomeAssistant):
        """MalfunctionActivated then AlarmCleared (same ID) → count = 0."""
        events = [
            _make_cgm_event(1, 100),
            _make_malfunction_activated(2, malfunction_id=14, minutes_ago=10),
            _make_alarm_cleared(3, alarm_id=14, minutes_ago=5),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_ALARM] == "Software Error"
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] == 0

    async def test_alarm_cleared_reduces_count(self, hass: HomeAssistant):
        """AlarmActivated then AlarmCleared → count = 0."""
        events = [
            _make_cgm_event(1, 100),
            _make_alarm_activated(2, alarm_id=2, minutes_ago=10),
            _make_alarm_cleared(3, alarm_id=2, minutes_ago=5),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_ALARM] == "Occlusion"
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] == 0

    async def test_mixed_alerts_and_alarms_count(self, hass: HomeAssistant):
        """Two active alerts + one active alarm → count = 3."""
        events = [
            _make_cgm_event(1, 100),
            _make_alert_activated(2, alert_id=0),  # Low Insulin — active
            _make_alert_activated(3, alert_id=2),  # Low Power — active
            _make_alarm_activated(4, alarm_id=2),  # Occlusion — active
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] == 3

    async def test_partial_clears_reduce_count(self, hass: HomeAssistant):
        """Two alerts activated, one cleared → count = 1."""
        events = [
            _make_cgm_event(1, 100),
            _make_alert_activated(2, alert_id=0, minutes_ago=20),
            _make_alert_activated(3, alert_id=2, minutes_ago=15),
            _make_alert_cleared(4, alert_id=0, minutes_ago=5),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] == 1

    async def test_no_alerts_alarm_only(self, hass: HomeAssistant):
        """No alert events but alarm present → last_alert UNAVAILABLE, last_alarm set."""
        events = [
            _make_cgm_event(1, 100),
            _make_alarm_activated(2, alarm_id=8),  # "Empty Cartridge"
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_ALERT] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_ALARM] == "Empty Cartridge"


# ── Helpers: Phase 3 (CGM G7 / Libre 2 / Daily Status) ──────────────────


def _make_cgm_event_g7(seq: int, glucose_mgdl: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 399,
        "event_name": "CGM",
        "seq": seq,
        "timestamp": ts,
        "glucose_mgdl": glucose_mgdl,
        "rate_of_change": 0.3,
        "status": 0,
    }


def _make_cgm_event_fsl2(seq: int, glucose_mgdl: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 372,
        "event_name": "CGM",
        "seq": seq,
        "timestamp": ts,
        "glucose_mgdl": glucose_mgdl,
        "rate_of_change": -0.2,
        "status": 0,
    }


def _make_daily_status(seq: int, sensor_type: str, sensor_type_id: int, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 313,
        "event_name": "AADailyStatus",
        "seq": seq,
        "timestamp": ts,
        "sensor_type": sensor_type,
        "sensor_type_id": sensor_type_id,
        "user_mode": 0,
        "pump_control_state": 3,
    }


# ── Decoder tests: Phase 3 events ───────────────────────────────────────


class TestCGMPhase3Decoder:
    """Binary decoder tests for events 399 (G7), 372 (FSL2), 313 (DailyStatus)."""

    @staticmethod
    def _decode_single(event_id: int, payload: bytes, seq: int = 1) -> dict:
        raw = _build_binary_event(event_id, seq, 500000000, payload)
        b64 = base64.b64encode(raw).decode()
        events = decode_pump_events(b64)
        assert len(events) == 1
        return events[0]

    def test_decode_cgm_g7(self):
        """Event 399 (CGM_DATA_G7) decodes with same layout as event 256."""
        # int8 @ offset 0 (rate_raw), uint16 @ offset 2 (status), uint16 @ offset 4 (glucose)
        payload = struct.pack(">b", 8) + b"\x00" + struct.pack(">H", 0) + struct.pack(">H", 145)
        evt = self._decode_single(399, payload)
        assert evt["event_name"] == "CGM"
        assert evt["glucose_mgdl"] == 145
        assert evt["rate_of_change"] == 0.8
        assert evt["status"] == 0

    def test_decode_cgm_g7_negative_rate(self):
        """Event 399 with negative rate of change."""
        payload = struct.pack(">b", -3) + b"\x00" + struct.pack(">H", 2) + struct.pack(">H", 70)
        evt = self._decode_single(399, payload)
        assert evt["glucose_mgdl"] == 70
        assert evt["rate_of_change"] == -0.3
        assert evt["status"] == 2  # Low

    def test_decode_cgm_fsl2(self):
        """Event 372 (CGM_DATA_FSL2) decodes with int16 rate and uint8 status."""
        # int16 @ offset 0 (rate_raw), uint8 @ offset 2 (status), pad, uint16 @ offset 4 (glucose)
        payload = struct.pack(">h", 12) + struct.pack(">B", 1) + b"\x00" + struct.pack(">H", 200)
        evt = self._decode_single(372, payload)
        assert evt["event_name"] == "CGM"
        assert evt["glucose_mgdl"] == 200
        assert evt["rate_of_change"] == 1.2
        assert evt["status"] == 1  # High

    def test_decode_cgm_fsl2_large_negative_rate(self):
        """Event 372 int16 rate allows larger values than event 256's int8."""
        payload = struct.pack(">h", -200) + struct.pack(">B", 0) + b"\x00" + struct.pack(">H", 55)
        evt = self._decode_single(372, payload)
        assert evt["rate_of_change"] == -20.0
        assert evt["glucose_mgdl"] == 55

    def test_decode_daily_status_g6(self):
        """Event 313 (AA_DAILY_STATUS) decodes sensor type G6."""
        # byte 0 = unused, byte 1 = sensor_type, byte 2 = user_mode, byte 3 = pump_control_state
        payload = b"\x00" + struct.pack(">B", 1) + struct.pack(">B", 0) + struct.pack(">B", 3)
        evt = self._decode_single(313, payload)
        assert evt["event_name"] == "AADailyStatus"
        assert evt["sensor_type"] == "G6"
        assert evt["sensor_type_id"] == 1
        assert evt["user_mode"] == 0
        assert evt["pump_control_state"] == 3

    def test_decode_daily_status_g7(self):
        """Event 313 with sensor type G7."""
        payload = b"\x00" + struct.pack(">B", 3) + struct.pack(">B", 1) + struct.pack(">B", 2)
        evt = self._decode_single(313, payload)
        assert evt["sensor_type"] == "G7"
        assert evt["sensor_type_id"] == 3
        assert evt["user_mode"] == 1
        assert evt["pump_control_state"] == 2

    def test_decode_daily_status_libre2(self):
        """Event 313 with sensor type Libre 2."""
        payload = b"\x00" + struct.pack(">B", 2) + struct.pack(">B", 0) + struct.pack(">B", 0)
        evt = self._decode_single(313, payload)
        assert evt["sensor_type"] == "Libre 2"
        assert evt["sensor_type_id"] == 2

    def test_decode_daily_status_none(self):
        """Event 313 with sensor type None (no CGM paired)."""
        payload = b"\x00" + struct.pack(">B", 0) + struct.pack(">B", 0) + struct.pack(">B", 0)
        evt = self._decode_single(313, payload)
        assert evt["sensor_type"] == "No CGM"
        assert evt["sensor_type_id"] == 0

    def test_decode_daily_status_unknown(self):
        """Event 313 with unknown sensor type ID falls back to Unknown (N)."""
        payload = b"\x00" + struct.pack(">B", 99) + struct.pack(">B", 0) + struct.pack(">B", 0)
        evt = self._decode_single(313, payload)
        assert evt["sensor_type"] == "Unknown (99)"


# ── Coordinator tests: Phase 3 CGM routing and sensor type ──────────────


class TestCGMPhase3Coordinator:
    """Test coordinator routes G7/FSL2 CGM events and parses daily status."""

    async def test_g7_event_used_for_glucose(self, hass: HomeAssistant):
        """Event 399 (G7) routes to cgm_readings and populates glucose sensor."""
        from custom_components.carelink.const import TANDEM_SENSOR_KEY_LASTSG_MGDL

        events = [_make_cgm_event_g7(1, 155)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == 155

    async def test_fsl2_event_used_for_glucose(self, hass: HomeAssistant):
        """Event 372 (FSL2) routes to cgm_readings and populates glucose sensor."""
        from custom_components.carelink.const import TANDEM_SENSOR_KEY_LASTSG_MGDL

        events = [_make_cgm_event_fsl2(1, 180)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == 180

    async def test_mixed_cgm_sources_latest_wins(self, hass: HomeAssistant):
        """When G6 (256) and G7 (399) events exist, most recent timestamp wins."""
        from custom_components.carelink.const import TANDEM_SENSOR_KEY_LASTSG_MGDL

        events = [
            _make_cgm_event(1, 100, minutes_ago=10),  # older G6
            _make_cgm_event_g7(2, 160, minutes_ago=5),  # newer G7
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == 160

    async def test_daily_status_sensor_type_g7(self, hass: HomeAssistant):
        """Event 313 with sensor_type=G7 populates CGM sensor type."""
        events = [
            _make_cgm_event(1, 100),
            _make_daily_status(2, "G7", 3),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE] == "G7"

    async def test_daily_status_sensor_type_libre2(self, hass: HomeAssistant):
        """Event 313 with sensor_type=Libre 2 populates CGM sensor type."""
        events = [
            _make_cgm_event(1, 100),
            _make_daily_status(2, "Libre 2", 2),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE] == "Libre 2"

    async def test_daily_status_latest_wins(self, hass: HomeAssistant):
        """Multiple daily status events — most recent sensor type wins."""
        events = [
            _make_cgm_event(1, 100),
            _make_daily_status(2, "G6", 1, minutes_ago=60),
            _make_daily_status(3, "G7", 3, minutes_ago=5),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE] == "G7"

    async def test_no_daily_status_sensor_type_unavailable(self, hass: HomeAssistant):
        """No event 313 → sensor type is UNAVAILABLE."""
        events = [_make_cgm_event(1, 100)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_TYPE] is UNAVAILABLE

    async def test_g7_cgm_summary_computed(self, hass: HomeAssistant):
        """G7 events contribute to CGM summary statistics (avg glucose, TIR)."""
        from custom_components.carelink.const import TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL

        events = [_make_cgm_event_g7(i, 120 + i, minutes_ago=i * 5) for i in range(10)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        # Average of 120..129 = 124.5, int() truncates to 124
        assert coordinator.data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] == 124


# ── Phase 4: Bolus Calculator decoder tests ──────────────────────────────


def _make_bolus_req_msg1(
    seq: int,
    bolus_id: int,
    bg: int,
    iob: float,
    carbs: int,
    carb_ratio: float = 10.0,
    bolus_type: int = 0,
    correction_included: int = 1,
    minutes_ago: int = 0,
) -> dict:
    """Create a BolusRequestedMsg1 event dict (as returned by decoder)."""
    ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=minutes_ago)
    return {
        "event_id": 64,
        "event_name": "BolusRequestedMsg1",
        "timestamp": ts,
        "seq": seq,
        "correction_included": bool(correction_included),
        "bolus_type": bolus_type,
        "bolus_id": bolus_id,
        "bg_mgdl": bg,
        "iob": round(iob, 2),
        "carb_amount": carbs,
        "carb_ratio": carb_ratio,
    }


def _make_bolus_req_msg2(
    seq: int,
    bolus_id: int,
    target_bg: int = 110,
    isf: int = 50,
    declined_correction: bool = False,
    user_override: bool = False,
    minutes_ago: int = 0,
) -> dict:
    """Create a BolusRequestedMsg2 event dict."""
    ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=minutes_ago)
    return {
        "event_id": 65,
        "event_name": "BolusRequestedMsg2",
        "timestamp": ts,
        "seq": seq,
        "standard_percent": 100,
        "bolus_id": bolus_id,
        "target_bg": target_bg,
        "isf": isf,
        "duration_minutes": 0,
        "declined_correction": declined_correction,
        "user_override": user_override,
    }


def _make_bolus_req_msg3(
    seq: int,
    bolus_id: int,
    food: float,
    correction: float,
    total: float,
    minutes_ago: int = 0,
) -> dict:
    """Create a BolusRequestedMsg3 event dict."""
    ts = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=minutes_ago)
    return {
        "event_id": 66,
        "event_name": "BolusRequestedMsg3",
        "timestamp": ts,
        "seq": seq,
        "bolus_id": bolus_id,
        "food_bolus_size": round(food, 2),
        "correction_bolus_size": round(correction, 2),
        "total_bolus_size": round(total, 2),
    }


class TestBolusCalcDecoder:
    """Binary decoder tests for events 64, 65, 66 (BolusRequested Msg1/Msg2/Msg3)."""

    @staticmethod
    def _decode_single(event_id: int, payload: bytes, seq: int = 1) -> dict:
        raw = _build_binary_event(event_id, seq, 500000000, payload)
        b64 = base64.b64encode(raw).decode()
        events = decode_pump_events(b64)
        assert len(events) == 1
        return events[0]

    def test_decode_msg1_basic(self):
        """Event 64 decodes BG, IOB, carbs, carb_ratio, bolus_type."""
        # correction_included=1, bolus_type=0, bolus_id=42, bg=180, iob=2.5, carbs=45, ratio=12000 (=12.0)
        payload = struct.pack(">B", 1)  # correction_included
        payload += struct.pack(">B", 0)  # bolus_type
        payload += struct.pack(">H", 42)  # bolus_id
        payload += struct.pack(">H", 180)  # bg
        payload += struct.pack(">f", 2.5)  # iob
        payload += struct.pack(">H", 45)  # carb_amount
        payload += struct.pack(">I", 12000)  # carb_ratio * 1000
        evt = self._decode_single(64, payload)
        assert evt["event_name"] == "BolusRequestedMsg1"
        assert evt["correction_included"] is True
        assert evt["bolus_type"] == 0
        assert evt["bolus_id"] == 42
        assert evt["bg_mgdl"] == 180
        assert evt["iob"] == 2.5
        assert evt["carb_amount"] == 45
        assert evt["carb_ratio"] == 12.0

    def test_decode_msg1_no_correction(self):
        """Event 64 with correction_included=0."""
        payload = struct.pack(">B", 0)
        payload += struct.pack(">B", 1)  # bolus_type=1
        payload += struct.pack(">H", 7)
        payload += struct.pack(">H", 95)
        payload += struct.pack(">f", 0.0)
        payload += struct.pack(">H", 0)
        payload += struct.pack(">I", 15000)
        evt = self._decode_single(64, payload)
        assert evt["correction_included"] is False
        assert evt["bolus_type"] == 1
        assert evt["bg_mgdl"] == 95
        assert evt["iob"] == 0.0
        assert evt["carb_amount"] == 0
        assert evt["carb_ratio"] == 15.0

    def test_decode_msg2_basic(self):
        """Event 65 decodes target_bg, ISF, declined/override flags."""
        payload = struct.pack(">B", 100)  # standard_percent
        payload += b"\x00"  # pad
        payload += struct.pack(">H", 88)  # bolus_id
        payload += struct.pack(">H", 110)  # target_bg
        payload += struct.pack(">H", 50)  # isf
        payload += struct.pack(">H", 0)  # duration
        payload += struct.pack(">B", 0)  # declined_correction
        payload += struct.pack(">B", 1)  # user_override
        evt = self._decode_single(65, payload)
        assert evt["event_name"] == "BolusRequestedMsg2"
        assert evt["standard_percent"] == 100
        assert evt["bolus_id"] == 88
        assert evt["target_bg"] == 110
        assert evt["isf"] == 50
        assert evt["duration_minutes"] == 0
        assert evt["declined_correction"] is False
        assert evt["user_override"] is True

    def test_decode_msg2_declined_correction(self):
        """Event 65 with declined_correction=1."""
        payload = struct.pack(">B", 100)
        payload += b"\x00"
        payload += struct.pack(">H", 99)
        payload += struct.pack(">H", 120)
        payload += struct.pack(">H", 40)
        payload += struct.pack(">H", 120)  # duration=120 minutes (extended)
        payload += struct.pack(">B", 1)  # declined
        payload += struct.pack(">B", 0)
        evt = self._decode_single(65, payload)
        assert evt["declined_correction"] is True
        assert evt["user_override"] is False
        assert evt["duration_minutes"] == 120

    def test_decode_msg3_basic(self):
        """Event 66 decodes food_bolus, correction_bolus, total_bolus."""
        payload = struct.pack(">H", 42)  # bolus_id
        payload += struct.pack(">f", 3.25)  # food_bolus_size
        payload += struct.pack(">f", 1.5)  # correction_bolus_size
        payload += struct.pack(">f", 4.75)  # total_bolus_size
        evt = self._decode_single(66, payload)
        assert evt["event_name"] == "BolusRequestedMsg3"
        assert evt["bolus_id"] == 42
        assert evt["food_bolus_size"] == 3.25
        assert evt["correction_bolus_size"] == 1.5
        assert evt["total_bolus_size"] == 4.75

    def test_decode_msg3_zero_correction(self):
        """Event 66 with no correction (food only)."""
        payload = struct.pack(">H", 10)
        payload += struct.pack(">f", 5.0)
        payload += struct.pack(">f", 0.0)
        payload += struct.pack(">f", 5.0)
        evt = self._decode_single(66, payload)
        assert evt["food_bolus_size"] == 5.0
        assert evt["correction_bolus_size"] == 0.0
        assert evt["total_bolus_size"] == 5.0


# ── Phase 4: Bolus Calculator coordinator tests ─────────────────────────


class TestBolusCalcCoordinator:
    """Test coordinator 3-way join and sensor population for bolus calculator."""

    async def test_complete_bolus_calc_record(self, hass: HomeAssistant):
        """All 3 messages join correctly and populate sensors."""
        events = [
            _make_bolus_req_msg1(1, 42, bg=180, iob=2.5, carbs=45, carb_ratio=10.0),
            _make_bolus_req_msg2(2, 42, target_bg=110, isf=50),
            _make_bolus_req_msg3(3, 42, food=4.5, correction=1.4, total=5.9),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_BG] == 180
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS] == 45
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_CORRECTION] == 1.4
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_FOOD] == 4.5
        attrs = coordinator.data[TANDEM_SENSOR_KEY_BOLUS_CALC_ATTRS]
        assert attrs["bolus_id"] == 42
        assert attrs["total_bolus"] == 5.9
        assert attrs["iob_at_request"] == 2.5
        assert attrs["carb_ratio"] == 10.0
        assert attrs["target_bg"] == 110
        assert attrs["isf"] == 50
        assert attrs["correction_included"] is True
        assert "timestamp" in attrs

    async def test_latest_bolus_selected(self, hass: HomeAssistant):
        """With multiple bolus records, the most recent (by msg3 timestamp) is used."""
        events = [
            # Older bolus (bolus_id=10)
            _make_bolus_req_msg1(1, 10, bg=150, iob=1.0, carbs=30, minutes_ago=30),
            _make_bolus_req_msg3(2, 10, food=3.0, correction=0.5, total=3.5, minutes_ago=30),
            # Newer bolus (bolus_id=20)
            _make_bolus_req_msg1(3, 20, bg=200, iob=3.0, carbs=60, minutes_ago=5),
            _make_bolus_req_msg3(4, 20, food=6.0, correction=2.0, total=8.0, minutes_ago=5),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_BG] == 200
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS] == 60
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_FOOD] == 6.0

    async def test_msg3_only_no_msg1_still_populates_partial(self, hass: HomeAssistant):
        """msg3 without matching msg1 → bg is None so record is incomplete, sensors stay UNAVAILABLE."""
        events = [
            _make_bolus_req_msg3(1, 99, food=2.0, correction=0.0, total=2.0),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        # No msg1 → bg is None → not "complete" → sensors stay at default
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_BG] is UNAVAILABLE

    async def test_no_bolus_calc_events(self, hass: HomeAssistant):
        """No events 64/65/66 → all bolus calc sensors are UNAVAILABLE."""
        events = [_make_cgm_event(1, 100)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_BG] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_CORRECTION] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_FOOD] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_BOLUS_CALC_ATTRS] == {}

    async def test_zero_bg_excluded(self, hass: HomeAssistant):
        """BG value of 0 means 'not entered' — sensor stays UNAVAILABLE."""
        events = [
            _make_bolus_req_msg1(1, 50, bg=0, iob=1.0, carbs=20),
            _make_bolus_req_msg3(2, 50, food=2.0, correction=0.0, total=2.0),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        # bg=0 is treated as "not entered" → passes completeness check (bg is not None,
        # it's 0) but BG sensor stays UNAVAILABLE because bg <= 0
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_BG] is UNAVAILABLE
        # But carbs/food/correction should still populate
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS] == 20
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_FOOD] == 2.0

    async def test_zero_bg_shadows_older_valid_bg(self, hass: HomeAssistant):
        """Newer bolus with bg=0 shadows older bolus with valid BG.

        This is intentional: the latest bolus calculator context is what
        matters, even if BG was not entered for that bolus.
        """
        events = [
            # Older bolus with valid BG
            _make_bolus_req_msg1(1, 10, bg=150, iob=1.0, carbs=30, minutes_ago=30),
            _make_bolus_req_msg3(2, 10, food=3.0, correction=0.5, total=3.5, minutes_ago=30),
            # Newer bolus without BG entry (bg=0)
            _make_bolus_req_msg1(3, 20, bg=0, iob=2.0, carbs=50, minutes_ago=5),
            _make_bolus_req_msg3(4, 20, food=5.0, correction=0.0, total=5.0, minutes_ago=5),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        # Latest bolus (id=20) is selected; its bg=0 → BG sensor UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_BG] is UNAVAILABLE
        # But carbs/food from the latest bolus are populated
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS] == 50
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_FOOD] == 5.0

    async def test_declined_correction_in_attrs(self, hass: HomeAssistant):
        """Declined correction flag surfaces in attributes."""
        events = [
            _make_bolus_req_msg1(1, 77, bg=140, iob=0.5, carbs=30),
            _make_bolus_req_msg2(2, 77, declined_correction=True, user_override=True),
            _make_bolus_req_msg3(3, 77, food=3.0, correction=0.0, total=3.0),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        attrs = coordinator.data[TANDEM_SENSOR_KEY_BOLUS_CALC_ATTRS]
        assert attrs["declined_correction"] is True
        assert attrs["user_override"] is True

    async def test_corrupted_bolus_event_resets_all_sensors(self, hass: HomeAssistant):
        """Corrupted timestamp in msg3 triggers catch block, resets all sensors."""
        events = [
            _make_bolus_req_msg1(1, 42, bg=180, iob=2.5, carbs=45),
            _make_bolus_req_msg3(2, 42, food=4.5, correction=1.4, total=5.9),
        ]
        # Corrupt the msg3 timestamp to trigger an error in the join logic
        events[1]["timestamp"] = "not-a-datetime"
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        # All sensors should be reset to UNAVAILABLE after error
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_BG] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_CORRECTION] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_FOOD] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_BOLUS_CALC_ATTRS] == {}


# ═══════════════════════════════════════════════════════════════════════
# Phase 5: PLGS & Daily Status — decoder + coordinator tests
# ═══════════════════════════════════════════════════════════════════════


def _make_plgs_event(
    seq: int, pgv: int, fmr: int = 100, homin_state: int = 1, rule_state: int = 0, minutes_ago: int = 0
) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    homin_state_map = {
        0: "No Prediction",
        1: "BG Rising",
        2: "BG Falling Mildly",
        3: "BG Falling Rapidly",
        4: "BG Falling - Suspend",
    }
    return {
        "event_id": 140,
        "event_name": "PLGSPeriodic",
        "seq": seq,
        "timestamp": ts,
        "homin_state": homin_state_map.get(homin_state, f"State_{homin_state}"),
        "homin_state_id": homin_state,
        "rule_state": rule_state,
        "predicted_glucose_mgdl": pgv,
        "fmr_mgdl": fmr,
    }


def _make_new_day_event(seq: int, basal_rate: float = 0.8, features: int = 0, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 90,
        "event_name": "NewDay",
        "seq": seq,
        "timestamp": ts,
        "commanded_basal_rate": basal_rate,
        "features_bitmask": features,
    }


class TestPLGSDecoders:
    """Test binary decoding of PLGS (event 140) and NewDay (event 90)."""

    def _decode_single(self, event_id: int, payload: bytes, seq: int = 1) -> dict:
        raw = _build_binary_event(event_id, seq, 500000000, payload)
        b64 = base64.b64encode(raw).decode()
        events = decode_pump_events(b64)
        assert len(events) == 1
        return events[0]

    def test_decode_plgs_periodic(self):
        """Event 140 (PLGS_Periodic) decodes predicted glucose and state."""
        payload = (
            b"\x00\x00\x00\x00"  # bytes 0-3 (unused in our decoder)
            + struct.pack(">B", 1)  # homin_state = BG Rising
            + struct.pack(">B", 3)  # rule_state bitmask
            + b"\x00\x00\x00\x00"  # bytes 6-9 (unused)
            + struct.pack(">H", 145)  # predicted glucose (PGV)
            + struct.pack(">H", 120)  # FMR
        )
        evt = self._decode_single(140, payload)
        assert evt["event_name"] == "PLGSPeriodic"
        assert evt["predicted_glucose_mgdl"] == 145
        assert evt["fmr_mgdl"] == 120
        assert evt["homin_state"] == "BG Rising"
        assert evt["homin_state_id"] == 1
        assert evt["rule_state"] == 3

    def test_decode_plgs_falling_rapidly(self):
        """PLGS with BG Falling Rapidly state."""
        payload = (
            b"\x00\x00\x00\x00"
            + struct.pack(">B", 3)  # BG Falling Rapidly
            + struct.pack(">B", 0)
            + b"\x00\x00\x00\x00"
            + struct.pack(">H", 70)  # low predicted glucose
            + struct.pack(">H", 65)
        )
        evt = self._decode_single(140, payload)
        assert evt["homin_state"] == "BG Falling Rapidly"
        assert evt["predicted_glucose_mgdl"] == 70

    def test_decode_plgs_suspend_state(self):
        """PLGS with BG Falling - Suspend state."""
        payload = (
            b"\x00\x00\x00\x00"
            + struct.pack(">B", 4)  # BG Falling - Suspend
            + struct.pack(">B", 5)  # rule_state
            + b"\x00\x00\x00\x00"
            + struct.pack(">H", 55)
            + struct.pack(">H", 50)
        )
        evt = self._decode_single(140, payload)
        assert evt["homin_state"] == "BG Falling - Suspend"
        assert evt["predicted_glucose_mgdl"] == 55

    def test_decode_plgs_unknown_state(self):
        """Unknown PLGS homin_state produces fallback string."""
        payload = (
            b"\x00\x00\x00\x00"
            + struct.pack(">B", 99)  # unknown state
            + struct.pack(">B", 0)
            + b"\x00\x00\x00\x00"
            + struct.pack(">H", 130)
            + struct.pack(">H", 110)
        )
        evt = self._decode_single(140, payload)
        assert evt["homin_state"] == "State_99"

    def test_decode_plgs_no_prediction(self):
        """PLGS with No Prediction state and zero PGV."""
        payload = (
            b"\x00\x00\x00\x00"
            + struct.pack(">B", 0)  # No Prediction
            + struct.pack(">B", 0)
            + b"\x00\x00\x00\x00"
            + struct.pack(">H", 0)  # PGV = 0
            + struct.pack(">H", 0)
        )
        evt = self._decode_single(140, payload)
        assert evt["homin_state"] == "No Prediction"
        assert evt["predicted_glucose_mgdl"] == 0

    def test_decode_new_day(self):
        """Event 90 (NewDay) decodes commanded basal rate and features."""
        payload = (
            struct.pack(">f", 0.85)  # commanded_basal_rate
            + struct.pack(">I", 0x0F)  # features_bitmask
        )
        evt = self._decode_single(90, payload)
        assert evt["event_name"] == "NewDay"
        assert evt["commanded_basal_rate"] == 0.85
        assert evt["features_bitmask"] == 0x0F

    def test_decode_new_day_zero_rate(self):
        """NewDay with zero basal rate."""
        payload = struct.pack(">f", 0.0) + struct.pack(">I", 0)
        evt = self._decode_single(90, payload)
        assert evt["commanded_basal_rate"] == 0.0
        assert evt["features_bitmask"] == 0


class TestPLGSCoordinator:
    """Test coordinator handling of PLGS predicted glucose sensor."""

    async def test_plgs_predicted_glucose(self, hass: HomeAssistant):
        """PLGS event populates predicted glucose sensor."""
        events = [
            _make_cgm_event(1, 120),
            _make_plgs_event(2, pgv=145),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] == 145

    async def test_plgs_latest_wins(self, hass: HomeAssistant):
        """Most recent PLGS event provides predicted glucose."""
        events = [
            _make_cgm_event(1, 120),
            _make_plgs_event(2, pgv=130, minutes_ago=10),
            _make_plgs_event(3, pgv=145, minutes_ago=5),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] == 145

    async def test_plgs_zero_pgv_unavailable(self, hass: HomeAssistant):
        """PGV of 0 is treated as unavailable (No Prediction state)."""
        events = [
            _make_cgm_event(1, 120),
            _make_plgs_event(2, pgv=0, homin_state=0),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] is UNAVAILABLE

    async def test_no_plgs_events_unavailable(self, hass: HomeAssistant):
        """No PLGS events results in unavailable predicted glucose."""
        events = [_make_cgm_event(1, 120)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] is UNAVAILABLE

    async def test_new_day_does_not_affect_predicted_glucose(self, hass: HomeAssistant):
        """NewDay events are decoded but don't produce a sensor (no crash)."""
        events = [
            _make_cgm_event(1, 120),
            _make_new_day_event(2, basal_rate=0.8, features=15),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        # No crash, predicted glucose is unavailable (no PLGS events)
        assert coordinator.data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] is UNAVAILABLE

    async def test_plgs_with_new_day_combined(self, hass: HomeAssistant):
        """Both PLGS and NewDay events are handled without interference."""
        events = [
            _make_cgm_event(1, 120),
            _make_new_day_event(2, basal_rate=0.8, features=15),
            _make_plgs_event(3, pgv=160),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] == 160

    async def test_no_pump_events_predicted_glucose_unavailable(self, hass: HomeAssistant):
        """Empty pump events results in unavailable predicted glucose."""
        coordinator = await _setup_coordinator(hass, _make_pump_events_data([]))
        assert coordinator.data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] is UNAVAILABLE


# ── Phase 6: Estimated Remaining Insulin ──────────────────────────────


def _make_bolex_completed(seq: int, delivered: float, minutes_ago: int = 0) -> dict:
    ts = BASE_TS - timedelta(minutes=minutes_ago)
    return {
        "event_id": 21,
        "event_name": "BolexCompleted",
        "seq": seq,
        "timestamp": ts,
        "bolus_id": 200 + seq,
        "completion_status": 3,
        "insulin_delivered": delivered,
    }


class TestEstimatedRemainingInsulin:
    """Test coordinator computation of estimated remaining insulin."""

    async def test_basic_remaining_after_bolus(self, hass: HomeAssistant):
        """Fill volume minus bolus deliveries gives remaining insulin."""
        events = [
            _make_cgm_event(1, 120),
            _make_cartridge_event(10, volume=200.0, minutes_ago=120),
            _make_bolus_completed(20, delivered=5.0, iob=5.0, minutes_ago=60),
            _make_bolus_completed(21, delivered=3.0, iob=8.0, minutes_ago=30),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        remaining = coordinator.data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING]
        # 200 - 5 - 3 = 192, minus some basal (0 basal events)
        assert remaining == 192.0

    async def test_remaining_with_bolex(self, hass: HomeAssistant):
        """Extended bolus (bolex) deliveries are included in the sum."""
        events = [
            _make_cgm_event(1, 120),
            _make_cartridge_event(10, volume=150.0, minutes_ago=120),
            _make_bolus_completed(20, delivered=4.0, iob=4.0, minutes_ago=60),
            _make_bolex_completed(21, delivered=2.5, minutes_ago=30),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        remaining = coordinator.data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING]
        assert remaining == 143.5  # 150 - 4 - 2.5

    async def test_remaining_with_basal(self, hass: HomeAssistant):
        """Basal delivery events after fill are subtracted."""
        events = [
            _make_cgm_event(1, 120),
            _make_cartridge_event(10, volume=200.0, minutes_ago=180),
            # Two basal delivery events 60 min apart at 1.0 U/hr = 1.0 U
            _make_basal_delivery(20, rate=1.0, minutes_ago=120),
            _make_basal_delivery(21, rate=1.0, minutes_ago=60),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        remaining = coordinator.data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING]
        # basal: 1.0 U/hr × 1 hr = 1.0 U, plus last segment 1.0 × 5/60 ≈ 0.083
        expected = round(200.0 - 1.0 - (1.0 * 5 / 60), 1)
        assert remaining == expected

    async def test_remaining_clamped_at_zero(self, hass: HomeAssistant):
        """Remaining never goes below zero."""
        events = [
            _make_cgm_event(1, 120),
            _make_cartridge_event(10, volume=10.0, minutes_ago=120),
            _make_bolus_completed(20, delivered=15.0, iob=15.0, minutes_ago=60),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING] == 0.0

    async def test_no_cartridge_fill_unavailable(self, hass: HomeAssistant):
        """No cartridge fill event results in unavailable."""
        events = [
            _make_cgm_event(1, 120),
            _make_bolus_completed(20, delivered=5.0, iob=5.0, minutes_ago=60),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING] is UNAVAILABLE

    async def test_zero_fill_volume_unavailable(self, hass: HomeAssistant):
        """Tandem API returning 0.0 for fill volume results in unavailable."""
        events = [
            _make_cgm_event(1, 120),
            _make_cartridge_event(10, volume=0.0, minutes_ago=120),
            _make_bolus_completed(20, delivered=5.0, iob=5.0, minutes_ago=60),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING] is UNAVAILABLE

    async def test_new_fill_resets_tracking(self, hass: HomeAssistant):
        """A newer cartridge fill resets the delivered total."""
        events = [
            _make_cgm_event(1, 120),
            # Old fill + bolus
            _make_cartridge_event(10, volume=200.0, minutes_ago=240),
            _make_bolus_completed(15, delivered=50.0, iob=50.0, minutes_ago=180),
            # New fill (higher seq) + smaller bolus
            _make_cartridge_event(20, volume=150.0, minutes_ago=60),
            _make_bolus_completed(25, delivered=3.0, iob=3.0, minutes_ago=30),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        remaining = coordinator.data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING]
        # Should use new fill (150), only count bolus after it (3.0)
        assert remaining == 147.0

    async def test_bolus_before_fill_not_counted(self, hass: HomeAssistant):
        """Bolus events before the cartridge fill are excluded."""
        events = [
            _make_cgm_event(1, 120),
            _make_bolus_completed(5, delivered=10.0, iob=10.0, minutes_ago=180),
            _make_cartridge_event(10, volume=200.0, minutes_ago=120),
            _make_bolus_completed(20, delivered=2.0, iob=2.0, minutes_ago=60),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        remaining = coordinator.data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING]
        # Only 2.0 U counted (after fill), not the 10.0 before fill
        assert remaining == 198.0

    async def test_empty_events_unavailable(self, hass: HomeAssistant):
        """Empty pump events results in unavailable."""
        coordinator = await _setup_coordinator(hass, _make_pump_events_data([]))
        assert coordinator.data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING] is UNAVAILABLE

    async def test_state_persists_across_polls(self, hass: HomeAssistant):
        """Fill state persists when cartridge fill is no longer in event window."""
        # First poll: cartridge fill + bolus
        events1 = [
            _make_cgm_event(1, 120),
            _make_cartridge_event(10, volume=200.0, minutes_ago=120),
            _make_bolus_completed(20, delivered=5.0, iob=5.0, minutes_ago=60),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events1))
        assert coordinator.data[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING] == 195.0

        # Second poll: no cartridge fill in events, new bolus only
        # State (_last_cartridge_fill_volume, _cumulative_delivered) persists
        events2 = [
            _make_cgm_event(30, 115),
            _make_bolus_completed(31, delivered=3.0, iob=3.0, minutes_ago=10),
        ]
        # Re-parse with same coordinator (simulating second poll)
        data2 = {}
        coordinator._parse_pump_events(_make_pump_events_data(events2)["pump_events"], data2)
        remaining = data2[TANDEM_SENSOR_KEY_ESTIMATED_INSULIN_REMAINING]
        # Cumulative: 5.0 (poll 1) + 3.0 (poll 2) = 8.0 delivered
        # 200 - 8.0 = 192.0
        assert remaining == 192.0
