"""CGM sensor sessions on the real G6 → G7 event shapes (live-verified 2026-10-01).

Replays the clock fields of an actual September 2026 sequence — a G6 ending at full
life, a G7 failing inside its grace window, a G7 failing at 9.7 days, and an active
G7 — shifted so the active sensor is ~5 days old. Only session/alert clock fields
are used (no glucose values).

* G6 (212/213/214): clock = reusable transmitter's age; wear = stop clock - the
  join's ``sessionStartTime``.
* G7 (394 join / 447 stop): clock = sensor's age; start = join time - cgmTimestamp,
  wear = stop's ``currentTransmitterTime``. The 447 start field is a sentinel.
* "Failed Sensor" = CGM alert 369 dalertId 11 with param1 35, logged with the 447.

Events are built as raw BFF JSON and run through the real ``map_pump_log_event``,
so the tests also pin the mapper's field names.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from itertools import count
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant

from custom_components.tandem.const import (
    TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING,
    TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY,
    TANDEM_SENSOR_KEY_CGM_SESSION_START,
    TANDEM_SENSOR_KEY_CGM_USAGE,
    TANDEM_SENSOR_KEY_LAST_CGM_SESSION_END,
    TANDEM_SENSOR_KEY_TIME_IN_RANGE,
    UNAVAILABLE,
)

from custom_components.tandem.tandem_api import map_pump_log_event

from .test_expanded_data import _make_pump_events_data, _setup_coordinator

_DAY = 86400
_SENTINEL = 0xFFFFFFFF
_seq = count(1)


def _now(hass: HomeAssistant) -> datetime:
    """Pump-local "now" (naive). _setup_coordinator pins the zone to UTC; match it."""
    hass.config.time_zone = "UTC"
    return datetime.now(ZoneInfo(hass.config.time_zone)).replace(tzinfo=None)


def _bff(code: int, ts: datetime, props: dict) -> dict:
    """A pump-logs event exactly as the BFF returns it, through the real mapper."""
    evt = map_pump_log_event(
        {
            "eventCode": code,
            "pumpDateTime": ts.replace(microsecond=0).isoformat(),
            "sequenceNumber": next(_seq),
            "eventProperties": props,
        }
    )
    assert evt is not None
    return evt


# Property sets below are verbatim from the live September 2026 pump-logs (only the
# clock values vary per call).


def _g6_join(ts: datetime, ct: int, sst: int, dur: int = 10, reason: int = 10) -> dict:
    return _bff(
        213,
        ts,
        {
            "currentTransmitterTime": ct,
            "sessionStartTime": sst,
            "spareC8": 0,
            "sessionDuration": dur,
            "sessionJoinReason": reason,
        },
    )


def _g6_stop(ts: datetime, ct: int, reason: int = 6) -> dict:
    return _bff(
        214,
        ts,
        {
            "currentTransmitterTime": ct,
            "sessionStartTime": _SENTINEL,
            "sessionStopTime": 0,
            "sessionDuration": 10,
            "sessionStopReason": reason,
        },
    )


def _g7_join(ts: datetime, cgm_ts: int, sig: int = 147) -> dict:
    return _bff(394, ts, {"cgmTimestamp": cgm_ts, "sessionSignature": sig})


def _g7_stop(ts: datetime, ct: int, dur: int = 10, reason: int = 15) -> dict:
    return _bff(
        447,
        ts,
        {
            "currentTransmitterTime": ct,
            "sessionStartTime": _SENTINEL,
            "sessionStopTime": 0,
            "sessionDuration": dur,
            "sessionStopReason": reason,
            "stopSessionCode": 0,
        },
    )


def _alert(ts: datetime, aid: int, param1: int | None = None, sensor: int = 3) -> dict:
    props = {"dalertId": aid, "sensorType": sensor, "spareA2": 0, "faultLocatorData": 8481, "param2": 725}
    if param1 is not None:
        props["param1"] = param1
    return _bff(369, ts, props)


def _reading(ts: datetime, glucose: int, *, eid: int = 399, egv: int | None = None, state: int | None = 32) -> dict:
    props = {
        "currentGlucoseDisplayValue": glucose,
        "glucoseValueStatus": 0,
        "rate": 0,
        "egvInfoBitmask": [],
        "egvTimeStamp": egv,
    }
    if state is not None:
        props["algorithmState"] = state
    return _bff(eid, ts, props)


def _september_sequence(now: datetime) -> tuple[list[dict], datetime]:
    """The live Sept 2026 G6 → G7 → G7 → G7 sequence; returns (events, active start)."""
    start3 = now - timedelta(days=5)  # active G7, ~5 days in
    stop2 = start3 - timedelta(seconds=9000)  # G7 #2 failed ~2.5 h before #3 started
    start2 = stop2 - timedelta(seconds=838395)  # worn 9.70 days
    stop1 = start2 - timedelta(seconds=160)
    start1 = stop1 - timedelta(seconds=868743)  # worn 10.05 days (in the 12 h grace)
    g6_stop = start1 - timedelta(seconds=4000)
    g6_join = g6_stop - timedelta(seconds=1769181 - 1673785)  # transmitter-clock delta
    events = [
        _g6_join(g6_join, ct=1673785, sst=905139),
        _alert(g6_stop, 13, sensor=1),  # CGM Sensor Expired
        _g6_stop(g6_stop, ct=1769181, reason=6),  # Transmitter Not In Session
        _g7_join(start1 + timedelta(seconds=853), 853, sig=118),
        _alert(stop1, 11, param1=35),
        _g7_stop(stop1, ct=868743),
        _g7_join(start2 + timedelta(seconds=69504), 69504, sig=72),
        _g7_join(start2 + timedelta(seconds=515903), 515903, sig=72),  # re-join after a pump reset
        _alert(stop2, 11, param1=35),
        _g7_stop(stop2, ct=838395),
        _g7_join(start3 + timedelta(seconds=1176), 1176, sig=147),
        _g7_join(start3 + timedelta(seconds=74670), 74670, sig=147),  # re-join after a pump reset
        _reading(now - timedelta(minutes=5), 120),
    ]
    events.sort(key=lambda e: e["timestamp"])
    return events, start3


class TestSeptemberSequence:
    async def test_session_ends_wear_cause_and_replacement(self, hass: HomeAssistant):
        events, _ = _september_sequence(_now(hass))
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_LAST_CGM_SESSION_END}_attributes"]
        g6, g7_grace, g7_early = attrs["recent"]

        # G6: full 10-day life, ended normally — not a failure.
        assert g6["sensor"] == "G6"
        assert g6["sensor_wear_days"] == 10.0
        assert g6["cause"] == "CGM Sensor Expired"
        assert g6["stop_reason"] == "Transmitter Not In Session"
        assert g6["ended_early"] is False
        assert g6["replacement_eligible"] is False

        # G7 #1: "Failed Sensor" at 10.05 days — inside the 12 h grace, not early.
        assert g7_grace["sensor"] == "G7"
        assert g7_grace["sensor_wear_days"] == 10.05
        assert g7_grace["cause"] == "Session Stopped (Sensor Failed)"
        assert g7_grace["ended_early"] is False
        assert g7_grace["ended_in_grace_period"] is True
        assert g7_grace["replacement_eligible"] is False

        # G7 #2: "Failed Sensor" at 9.70 days — early, under Dexcom's 10-day rule.
        assert attrs["sensor"] == "G7"
        assert attrs["sensor_wear_days"] == 9.7
        assert attrs["cause"] == "Session Stopped (Sensor Failed)"
        assert attrs["cause_alert_id"] == 11
        assert attrs["stop_reason"] is None  # 447 reason enum undocumented → raw only
        assert attrs["stop_reason_code"] == 15
        assert attrs["ended_early"] is True
        assert attrs["ended_in_grace_period"] is False
        assert attrs["replacement_eligible"] is True

    async def test_active_g7_session_from_join(self, hass: HomeAssistant):
        now = _now(hass)
        events, start3 = _september_sequence(now)
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        tz = ZoneInfo(hass.config.time_zone)
        start = coordinator.data[TANDEM_SENSOR_KEY_CGM_SESSION_START]
        expiry = coordinator.data[TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY]
        assert abs((start - start3.replace(tzinfo=tz)).total_seconds()) < 1
        assert expiry - start == timedelta(days=10)
        assert 4.9 < coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING] < 5.1
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY}_attributes"]
        assert attrs["sensor"] == "G7"
        assert attrs["session_duration_source"] == "previous G7 stop"
        assert attrs["grace_period_hours"] == 12
        assert attrs["in_grace_period"] is False
        # Integrated sensor-transmitter: no separate transmitter life.
        assert attrs["transmitter_expiry"] is None


class TestG7Session:
    async def test_first_g7_uses_standard_rating(self, hass: HomeAssistant):
        now = _now(hass)
        events = [_g7_join(now - timedelta(days=2), 3600), _reading(now - timedelta(minutes=5), 120)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY}_attributes"]
        assert attrs["session_duration_days"] == 10
        assert attrs["session_duration_source"] == "G7 standard rating"
        assert 7.9 < coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING] < 8.0

    async def test_15_day_g7_duration_from_previous_stop(self, hass: HomeAssistant):
        now = _now(hass)
        events = [
            _g7_stop(now - timedelta(days=12, hours=1), ct=15 * _DAY, dur=15),
            _g7_join(now - timedelta(days=12), 600),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[f"{TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY}_attributes"]["session_duration_days"] == 15
        assert 2.9 < coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING] < 3.1

    async def test_in_grace_window_stays_current(self, hass: HomeAssistant):
        now = _now(hass)
        # Started 10 d 6 h ago → past the rating, inside the 12 h grace window.
        events = [_g7_join(now - timedelta(minutes=10), 10 * _DAY + 6 * 3600 - 600)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING] == 0.0
        assert coordinator.data[f"{TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY}_attributes"]["in_grace_period"] is True

    # Each "session ended" case is paired with a control: the same join WITHOUT the
    # ending condition must be active, so the test cannot pass merely because no
    # session was ever recognised.

    async def test_past_grace_window_unavailable(self, hass: HomeAssistant):
        now = _now(hass)
        control = await _setup_coordinator(
            hass, _make_pump_events_data([_g7_join(now - timedelta(minutes=10), 10 * _DAY + 11 * 3600)])
        )
        assert control.data[f"{TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY}_attributes"]["in_grace_period"] is True
        events = [_g7_join(now - timedelta(minutes=10), 10 * _DAY + 13 * 3600)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY] is UNAVAILABLE

    async def test_stop_after_join_ends_session(self, hass: HomeAssistant):
        now = _now(hass)
        join = _g7_join(now - timedelta(days=3), 600)
        control = await _setup_coordinator(hass, _make_pump_events_data([join]))
        assert isinstance(control.data[TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY], datetime)
        events = [join, _g7_stop(now - timedelta(hours=1), ct=4 * _DAY)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY] is UNAVAILABLE

    async def test_failed_state_reading_ends_session(self, hass: HomeAssistant):
        """A G7 'Session Stopped' reading after the join (stop not uploaded yet)."""
        now = _now(hass)
        join = _g7_join(now - timedelta(days=3), 600)
        control = await _setup_coordinator(
            hass, _make_pump_events_data([join, _reading(now - timedelta(minutes=5), 120, state=32)])
        )
        assert isinstance(control.data[TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING], float)
        events = [join, _reading(now - timedelta(minutes=5), 0, state=35)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING] is UNAVAILABLE

    async def test_stop_cause_falls_back_to_reading_state(self, hass: HomeAssistant):
        now = _now(hass)
        events = [
            _reading(now - timedelta(minutes=10), 0, state=36),
            _g7_stop(now - timedelta(minutes=5), ct=3 * _DAY),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_LAST_CGM_SESSION_END}_attributes"]
        assert attrs["cause"] == "Session Stopped (Manual Stop)"
        assert attrs["cause_alert_id"] is None
        assert attrs["sensor_wear_days"] == 3.0


class TestG6Session:
    async def test_transmitter_age_and_expiry(self, hass: HomeAssistant):
        now = _now(hass)
        # Transmitter 20 days old; this sensor started on it at day 18.
        events = [
            _g6_join(now - timedelta(hours=1), ct=20 * _DAY, sst=18 * _DAY),
            _reading(now - timedelta(minutes=5), 120, eid=256, state=None),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert 7.9 < coordinator.data[TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING] < 8.0
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY}_attributes"]
        assert attrs["sensor"] == "G6"
        assert attrs["grace_period_hours"] == 0
        assert attrs["transmitter_age_days"] == 20.0
        assert attrs["transmitter_days_remaining"] == 70.0

    async def test_stop_on_new_transmitter_has_no_wear(self, hass: HomeAssistant):
        """The stop's clock is behind the join's → a different transmitter: no wear."""
        now = _now(hass)
        events = [
            _g6_join(now - timedelta(days=2), ct=40 * _DAY, sst=38 * _DAY),
            _g6_stop(now - timedelta(hours=1), ct=1 * _DAY, reason=0),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_LAST_CGM_SESSION_END}_attributes"]
        assert attrs["sensor_wear_days"] is None
        assert attrs["replacement_eligible"] is None


class TestCgmSummaryWindow:
    async def test_duplicates_dropped_and_period_bounded(self, hass: HomeAssistant):
        now = _now(hass)
        rows = [_reading(now - timedelta(minutes=5 * i), 120, egv=10_000 - 300 * i) for i in range(10)]
        # The same reading logged twice (identical egv/value/status) counts once.
        rows.append(_reading(now - timedelta(minutes=5), 120, egv=10_000 - 300))
        # Older than the 7-day period → excluded (would otherwise drag TIR down).
        rows += [_reading(now - timedelta(days=8, minutes=i), 300, egv=1_000 + i) for i in range(5)]
        rows.sort(key=lambda r: r["timestamp"])
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(rows))
        assert coordinator.data[TANDEM_SENSOR_KEY_TIME_IN_RANGE] == 100.0
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_TIME_IN_RANGE}_attributes"]
        assert attrs["readings"] == 10
        assert attrs["period_days"] == 7
        # Usage = readings / expected 5-min readings over the 7-day period.
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_USAGE] == 0.5  # 10 of 2016

    async def test_day_time_in_range(self, hass: HomeAssistant):
        now = _now(hass).replace(hour=12, minute=0, second=0, microsecond=0)
        rows = [
            _reading(now - timedelta(days=1), 300, egv=1),  # yesterday: excluded from the day figure
            _reading(now - timedelta(hours=2), 100, egv=2),
            _reading(now - timedelta(hours=1), 250, egv=3),
            _reading(now, 60, egv=4),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(rows))
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_TIME_IN_RANGE}_attributes"]
        assert attrs["day"] == now.date().isoformat()
        assert attrs["day_readings"] == 3
        assert attrs["day_time_in_range"] == 33.3
        assert attrs["day_time_below_range"] == 33.3
        assert attrs["day_time_above_range"] == 33.3
        assert coordinator.data[TANDEM_SENSOR_KEY_TIME_IN_RANGE] == 25.0  # 7-day period


class TestDaylightSaving:
    async def test_expiry_is_ten_real_days_across_dst(self, hass: HomeAssistant):
        """Live case: G7 started 2026-09-26 16:51:42 ACST; Adelaide moves to ACDT on
        2026-10-04, so wall-clock arithmetic put expiry an hour early (06:21Z)."""
        from datetime import timezone

        from freezegun import freeze_time

        coordinator = await _setup_coordinator(hass, _make_pump_events_data([_reading(_now(hass), 120)]))
        coordinator.timezone = "Australia/Adelaide"
        # Re-join after a pump reset, exactly as logged (pump-local time).
        events = [_g7_join(datetime(2026, 9, 27, 13, 36, 12), 74670)]
        data: dict = {}
        with freeze_time("2026-10-01T11:00:00+00:00"):
            coordinator._parse_cgm_session_events(events, data, [])
        assert data[TANDEM_SENSOR_KEY_CGM_SESSION_START] == datetime(2026, 9, 26, 7, 21, 42, tzinfo=timezone.utc)
        assert data[TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY] == datetime(2026, 10, 6, 7, 21, 42, tzinfo=timezone.utc)
        assert data[TANDEM_SENSOR_KEY_CGM_SENSOR_DAYS_REMAINING] == 4.85
        attrs = data[f"{TANDEM_SENSOR_KEY_CGM_SESSION_EXPIRY}_attributes"]
        assert attrs["grace_period_end"] == "2026-10-07T05:51:42+10:30"  # 19:21:42Z
