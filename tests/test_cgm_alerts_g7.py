"""CGM alerts + G7 sensor lifecycle: "Failed Sensor", "Sensor Session Ended", codes.

Covers the event families Tandem Source shows for a Dexcom G7 that the pump
alert/alarm path (4/5/6/26/28) never sees:

* CGM alerts 171/172 and Dex 369/370/371 (``dalertId``) -> ``tandem_last_cgm_alert``
* G7 data event 399 ``algorithmState`` -> ``tandem_cgm_sensor_state``
* Session stops 214 / G7 447 -> ``tandem_last_cgm_session_end`` (cause, codes, wear)
"""

from __future__ import annotations

from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant

from custom_components.tandem.const import (
    TANDEM_ALARM_MAP,
    TANDEM_ALERT_MAP,
    TANDEM_CGM_ALERT_MAP,
    TANDEM_SENSOR_KEY_CGM_SENSOR_STATE,
    TANDEM_SENSOR_KEY_LAST_CGM_ALERT,
    TANDEM_SENSOR_KEY_LAST_CGM_SESSION_END,
    UNAVAILABLE,
)
from custom_components.tandem.tandem_api import (
    EVT_CGM_ALERT_ACK_DEX,
    EVT_CGM_ALERT_ACTIVATED,
    EVT_CGM_ALERT_ACTIVATED_DEX,
    EVT_CGM_ALERT_CLEARED_DEX,
    EVT_CGM_DATA_G7,
    EVT_CGM_DATA_GXB,
    EVT_CGM_SESSION_JOIN_G7,
    EVT_CGM_SESSION_STOP_G7,
    map_pump_log_event,
)

from .test_expanded_data import (
    BASE_TS,
    _make_cgm_event,
    _make_pump_events_data,
    _make_session_event,
    _setup_coordinator,
)

_DAY = 86400


def _bff(code: int, props: dict) -> dict:
    return {
        "eventCode": code,
        "pumpDateTime": "2026-09-26T14:23:00",
        "sequenceNumber": 11,
        "eventProperties": props,
    }


def _cgm_alert(seq: int, name: str, alert_id: int, *, event_id: int = 369, minutes_ago: int = 0) -> dict:
    return {
        "event_id": event_id,
        "event_name": name,
        "seq": seq,
        "timestamp": BASE_TS - timedelta(minutes=minutes_ago),
        "cgm_alert_id": alert_id,
        "sensor_type_id": 3,
    }


def _g7_reading(seq: int, glucose: int, state: int | None, *, minutes_ago: int = 0) -> dict:
    return {
        "event_id": 399,
        "event_name": "CGM",
        "seq": seq,
        "timestamp": BASE_TS - timedelta(minutes=minutes_ago),
        "glucose_mgdl": glucose,
        "rate_of_change": 0.0,
        "status": 0,
        "algorithm_state": state,
    }


# ── Mapper (BFF pump-logs → decoded event) ────────────────────────────────


class TestMapCgmAlertEvents:
    def test_dex_alert_activated(self):
        evt = map_pump_log_event(_bff(EVT_CGM_ALERT_ACTIVATED_DEX, {"dalertId": 11, "sensorType": 3}))
        assert evt is not None
        assert evt["event_name"] == "CGMAlertActivated"
        assert evt["cgm_alert_id"] == 11
        assert evt["sensor_type_id"] == 3

    def test_dex_alert_cleared(self):
        evt = map_pump_log_event(_bff(EVT_CGM_ALERT_CLEARED_DEX, {"dalertId": 11, "sensorType": 3}))
        assert evt["event_name"] == "CGMAlertCleared"
        assert evt["cgm_alert_id"] == 11

    def test_dex_alert_ack_source(self):
        evt = map_pump_log_event(_bff(EVT_CGM_ALERT_ACK_DEX, {"dalertId": 11, "sensorType": 3, "ackSource": 0}))
        assert evt["event_name"] == "CGMAlertAcknowledged"
        assert evt["ack_source"] == "User"

    def test_legacy_cgm_alert_has_no_sensor_type(self):
        evt = map_pump_log_event(_bff(EVT_CGM_ALERT_ACTIVATED, {"dalertId": 13}))
        assert evt["event_name"] == "CGMAlertActivated"
        assert evt["cgm_alert_id"] == 13
        assert evt["sensor_type_id"] is None

    def test_g7_session_stop(self):
        evt = map_pump_log_event(
            _bff(
                EVT_CGM_SESSION_STOP_G7,
                {
                    "currentTransmitterTime": 500000,
                    "sessionStartTime": 100000,
                    "sessionStopTime": 400000,
                    "sessionDuration": 10,
                    "sessionStopReason": 2,
                    "stopSessionCode": 7,
                },
            )
        )
        # Treated as a stop by the coordinator (same name as 214).
        assert evt["event_name"] == "CGMSessionStop"
        assert evt["session_stop_time"] == 400000
        assert evt["session_reason"] == 2
        assert evt["stop_session_code"] == 7

    def test_g7_session_join_carries_sensor_age(self):
        # Live shape (2026-09-26): cgmTimestamp = seconds since the G7 sensor started.
        evt = map_pump_log_event(_bff(EVT_CGM_SESSION_JOIN_G7, {"cgmTimestamp": 1176, "sessionSignature": 147}))
        assert evt["event_name"] == "CGMSessionJoinG7"
        assert evt["cgm_timestamp"] == 1176
        assert evt["session_signature"] == 147

    def test_g7_session_stop_live_shape(self):
        # Live 447: sentinel start, stop time 0; currentTransmitterTime is the wear time.
        evt = map_pump_log_event(
            _bff(
                EVT_CGM_SESSION_STOP_G7,
                {
                    "currentTransmitterTime": 838395,
                    "sessionStartTime": 4294967295,
                    "sessionStopTime": 0,
                    "sessionDuration": 10,
                    "sessionStopReason": 15,
                    "stopSessionCode": 0,
                },
            )
        )
        assert evt["current_transmitter_time"] == 838395
        assert evt["session_start_time"] == 0xFFFFFFFF
        assert evt["session_reason"] == 15

    def test_sensor_failed_alert_carries_stop_state(self):
        # Live 369 at both G7 failures: dalertId 11, param1 35 (= Sensor Failed state).
        evt = map_pump_log_event(
            _bff(EVT_CGM_ALERT_ACTIVATED_DEX, {"dalertId": 11, "sensorType": 3, "param1": 35, "param2": 725})
        )
        assert evt["cgm_alert_id"] == 11
        assert evt["param1"] == 35

    def test_cgm_data_carries_egv_timestamp(self):
        evt = map_pump_log_event(_bff(EVT_CGM_DATA_G7, {"currentGlucoseDisplayValue": 150, "egvTimeStamp": 123456}))
        assert evt["egv_timestamp"] == 123456

    def test_cgm_data_carries_algorithm_state(self):
        evt = map_pump_log_event(
            _bff(EVT_CGM_DATA_G7, {"currentGlucoseDisplayValue": 150, "glucoseValueStatus": 0, "algorithmState": 35})
        )
        assert evt["algorithm_state"] == 35

    def test_cgm_data_missing_algorithm_state_is_none(self):
        evt = map_pump_log_event(_bff(EVT_CGM_DATA_GXB, {"currentGlucoseDisplayValue": 150}))
        assert evt["algorithm_state"] is None


# ── Name maps ─────────────────────────────────────────────────────────────


class TestNameMaps:
    def test_cgm_sensor_failed_is_a_cgm_alert(self):
        assert TANDEM_CGM_ALERT_MAP[11] == "CGM Sensor Failed"
        assert TANDEM_CGM_ALERT_MAP[13] == "CGM Sensor Expired"

    def test_pump_alert_ids_match_upstream(self):
        # Previously mislabelled as CGM alerts ("Sensor Failed", "Sensor Warmup", …);
        # these are pump alert ids per tconnectsync ALERTS_DICT / pumpX2.
        assert TANDEM_ALERT_MAP[24] == "Device Connection Error"
        assert TANDEM_ALERT_MAP[23] == "Pump Rebooting"
        assert TANDEM_ALERT_MAP[25] == "CGM Graph Removed"
        assert 43 not in TANDEM_ALERT_MAP  # upstream DEFAULT_ALERT_43 — no guessed name

    def test_pump_alarm_ids_match_upstream(self):
        assert TANDEM_ALARM_MAP[22] == "Stuck Button"
        assert TANDEM_ALARM_MAP[14] == "Invalid Date"
        assert TANDEM_ALARM_MAP[8] == "Empty Cartridge"


# ── Coordinator: last CGM alert ───────────────────────────────────────────


class TestLastCgmAlert:
    async def test_no_cgm_alerts_unavailable(self, hass: HomeAssistant):
        coordinator = await _setup_coordinator(hass, _make_pump_events_data([_make_cgm_event(1, 100)]))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CGM_ALERT] is UNAVAILABLE

    async def test_failed_sensor_alert(self, hass: HomeAssistant):
        events = [_make_cgm_event(1, 100, minutes_ago=10), _cgm_alert(2, "CGMAlertActivated", 11)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CGM_ALERT] == "CGM Sensor Failed"
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_LAST_CGM_ALERT}_attributes"]
        assert attrs["cgm_alert_id"] == 11
        assert attrs["sensor_type"] == "G7"
        assert attrs["cleared"] is False
        assert attrs["acknowledged"] is False
        assert attrs["active_count"] == 1
        assert attrs["active"] == ["CGM Sensor Failed"]

    async def test_ack_then_clear(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 100),
            _cgm_alert(2, "CGMAlertActivated", 11, minutes_ago=30),
            _cgm_alert(3, "CGMAlertAcknowledged", 11, event_id=371, minutes_ago=20),
            _cgm_alert(4, "CGMAlertCleared", 11, event_id=370, minutes_ago=10),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_LAST_CGM_ALERT}_attributes"]
        assert attrs["cleared"] is True
        assert attrs["acknowledged"] is True
        assert attrs["active_count"] == 0

    async def test_unknown_id_fallback_and_dedup(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 100),
            # Same alert logged on both the legacy (171) and Dex (369) events.
            _cgm_alert(2, "CGMAlertActivated", 99, event_id=171, minutes_ago=5),
            _cgm_alert(3, "CGMAlertActivated", 99, event_id=369, minutes_ago=5),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CGM_ALERT] == "CGM Alert 99"
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_LAST_CGM_ALERT}_attributes"]
        assert len(attrs["recent"]) == 1

    async def test_cgm_alerts_do_not_change_pump_alert_count(self, hass: HomeAssistant):
        from custom_components.tandem.const import TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT

        events = [_make_cgm_event(1, 100), _cgm_alert(2, "CGMAlertActivated", 11)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_ACTIVE_ALERTS_COUNT] == 0


# ── Coordinator: CGM sensor state ─────────────────────────────────────────


class TestCgmSensorState:
    async def test_g7_in_session(self, hass: HomeAssistant):
        coordinator = await _setup_coordinator(hass, _make_pump_events_data([_g7_reading(1, 120, 32)]))
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_STATE] == "In Session"
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_CGM_SENSOR_STATE}_attributes"]
        assert attrs["algorithm_state_code"] == 32
        assert attrs["session_stopped"] is False

    async def test_g7_failed_sensor_state_without_glucose(self, hass: HomeAssistant):
        # A failed sensor sends no usable glucose — the state must still surface.
        events = [_g7_reading(1, 120, 32, minutes_ago=10), _g7_reading(2, 0, 35)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_STATE] == "Session Stopped (Sensor Failed)"
        assert coordinator.data[f"{TANDEM_SENSOR_KEY_CGM_SENSOR_STATE}_attributes"]["session_stopped"] is True

    async def test_g6_state_not_decoded(self, hass: HomeAssistant):
        evt = _make_cgm_event(1, 100)
        evt["algorithm_state"] = 32  # G6 has no documented enum
        coordinator = await _setup_coordinator(hass, _make_pump_events_data([evt]))
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_STATE] is UNAVAILABLE

    async def test_unknown_g7_state_stays_visible(self, hass: HomeAssistant):
        coordinator = await _setup_coordinator(hass, _make_pump_events_data([_g7_reading(1, 120, 77)]))
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_STATE] == "State 77"


# ── Coordinator: last CGM session end ─────────────────────────────────────


class TestLastCgmSessionEnd:
    async def test_no_stop_unavailable(self, hass: HomeAssistant):
        coordinator = await _setup_coordinator(hass, _make_pump_events_data([_make_cgm_event(1, 100)]))
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CGM_SESSION_END] is UNAVAILABLE

    async def test_214_stop_wear_from_transmitter_clock_and_cause(self, hass: HomeAssistant):
        """214 carries a sentinel start; wear = stop clock - the join's session start
        on the same G6 transmitter. Cause from the CGM Sensor Failed alert."""
        events = [
            # Joined 60 min ago, 2 days into the session.
            _make_session_event(1, name="CGMSessionJoin", event_id=213, ct=2 * _DAY, sst=0, minutes_ago=60),
            _make_cgm_event(2, 120, minutes_ago=5),
            _cgm_alert(3, "CGMAlertActivated", 11, minutes_ago=0),
            _make_session_event(
                4, name="CGMSessionStop", event_id=214, ct=2 * _DAY + 3600, sst=0xFFFFFFFF, stop_time=0, reason=4
            ),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        end = coordinator.data[TANDEM_SENSOR_KEY_LAST_CGM_SESSION_END]
        assert isinstance(end, datetime)
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_LAST_CGM_SESSION_END}_attributes"]
        assert attrs["cause"] == "CGM Sensor Failed"  # no G7 param1 -> the alert name
        assert attrs["cause_alert_id"] == 11
        assert attrs["stop_reason"] == "Transmitter Error"
        assert attrs["stop_reason_code"] == 4
        assert attrs["sensor"] == "G6"
        assert attrs["sensor_wear_hours"] == 49.0
        assert attrs["ended_early"] is True
        assert attrs["replacement_eligible"] is True
        assert attrs["source_event"] == 214
        assert len(attrs["recent"]) == 1

    async def test_447_stop_wear_from_own_fields_and_dedup(self, hass: HomeAssistant):
        """A G7 stop on both 214 and 447 collapses to the 447 record."""
        g7_stop = _make_session_event(
            3,
            name="CGMSessionStop",
            event_id=447,
            ct=10 * _DAY,
            sst=_DAY,
            stop_time=_DAY + 240 * 3600 + 6 * 3600,  # worn 246 h (10 days + 6 h grace)
            reason=2,
        )
        g7_stop["stop_session_code"] = 1
        events = [
            _make_cgm_event(1, 100, minutes_ago=5),
            _make_session_event(
                2, name="CGMSessionStop", event_id=214, ct=0, sst=0xFFFFFFFF, stop_time=0, reason=5, minutes_ago=1
            ),
            g7_stop,
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_LAST_CGM_SESSION_END}_attributes"]
        assert attrs["source_event"] == 447
        assert attrs["stop_reason"] is None  # 447 reason enum is undocumented → raw only
        assert attrs["stop_reason_code"] == 2
        assert attrs["stop_session_code"] == 1
        assert attrs["sensor_wear_hours"] == 246.0
        assert attrs["ended_early"] is False
        assert len(attrs["recent"]) == 1

    async def test_unknown_wear_is_none(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 100),
            _make_session_event(2, name="CGMSessionStop", event_id=214, ct=0, sst=0xFFFFFFFF, stop_time=0, reason=0),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_LAST_CGM_SESSION_END}_attributes"]
        assert attrs["sensor_wear_hours"] is None
        assert attrs["ended_early"] is None
        assert attrs["stop_reason"] == "User"


# ── Client: unmapped event codes are reported (codes only) ────────────────


async def test_get_pump_events_logs_unmapped_codes(caplog):
    """Dropped event codes are counted in a debug log so a user can see what their CGM sends."""
    import logging
    from unittest.mock import AsyncMock

    from custom_components.tandem.tandem_api import TandemSourceClient

    client = TandemSourceClient("user@test.com", "pass")
    client.pumper_id = "p"
    client._api_get = AsyncMock(
        return_value={
            "events": [
                {
                    "eventCode": 369,
                    "pumpDateTime": "2026-09-26T14:23:00",
                    "sequenceNumber": 1,
                    "eventProperties": {"dalertId": 11},
                },
                {"eventCode": 8, "pumpDateTime": "2026-09-26T14:24:00", "sequenceNumber": 2, "eventProperties": {}},
                {"eventCode": 8, "pumpDateTime": "2026-09-26T14:25:00", "sequenceNumber": 3, "eventProperties": {}},
            ]
        }
    )
    with caplog.at_level(logging.DEBUG, logger="custom_components.tandem.tandem_api"):
        events = await client.get_pump_events("dev", "2026-09-26", "2026-09-26")
    assert [e["event_id"] for e in events] == [369]
    assert "Unmapped pump-logs event codes {code: count}: {8: 2}" in caplog.text
