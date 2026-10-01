"""Carb sensors fed from bolus calculator requests (event 64), as the BFF delivers them.

The BFF pump-logs never carry the standalone CarbsEntered event (48); carbs entered in
the bolus calculator arrive only as ``carbAmount`` on BolusRequestedMsg1 (64), keys
live-verified 2026-09-06. Before this fix the carb sensors read only event 48, so
daily carbs / last carb entry / meal-carb statistics stayed unknown on every BFF
install while ``last_bolus_carbs_entered`` (read from 64) had a value.

Events are built as raw BFF JSON and run through the real ``map_pump_log_event``, so
the tests also pin the mapper's field names. Amounts are synthetic.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from itertools import count

from freezegun import freeze_time
from homeassistant.core import HomeAssistant

from conftest import make_tandem_coordinator

from custom_components.tandem.const import (
    DOMAIN,
    TANDEM_SENSOR_KEY_DAILY_CARBS,
    TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS,
    TANDEM_SENSOR_KEY_LAST_CARBS,
    TANDEM_SENSOR_KEY_LAST_CARBS_TIMESTAMP,
    UNAVAILABLE,
)
from custom_components.tandem.tandem_api import map_pump_log_event

from .test_expanded_data import _make_pump_events_data, _setup_coordinator

# Midday UTC; _setup_coordinator pins the hass zone to UTC, so pump-local == UTC.
_NOW = datetime(2026, 10, 1, 12, 0, 0)
_seq = count(1)


def _bff(code: int, ts: datetime, props: dict) -> dict:
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


def _msg1(ts: datetime, bolus_id: int, carbs: object) -> dict:
    """BolusRequestedMsg1 with the live 2026-09-06 key set."""
    return _bff(
        64,
        ts,
        {
            "bolusId": bolus_id,
            "bolusType": [4] if carbs else [],
            "correctionBolusIncluded": 1,
            "carbAmount": carbs,
            "bg": 0,
            "iob": 0.5,
            "carbRatio": 10000,
        },
    )


def _msg3(ts: datetime, bolus_id: int) -> dict:
    return _bff(66, ts, {"bolusId": bolus_id, "foodBolusSize": 3.0, "correctionBolusSize": 0.0, "totalBolusSize": 3.0})


def _cgm(ts: datetime) -> dict:
    return _bff(256, ts, {"currentGlucoseDisplayValue": 110, "rate": 0, "glucoseValueStatus": 0})


def _carbs48(ts: datetime, carbs: object) -> dict:
    """Standalone CarbsEntered (48) as the mapper emits it."""
    return {"event_id": 48, "event_name": "CarbsEntered", "seq": next(_seq), "timestamp": ts, "carbs": carbs}


def _basal(ts: datetime, rate: float) -> dict:
    return {
        "event_id": 279,
        "event_name": "BasalDelivery",
        "seq": next(_seq),
        "timestamp": ts,
        "commanded_source": 1,
        "commanded_rate": rate,
    }


def _bolus_completed(ts: datetime, bolus_id: int, units: float) -> dict:
    return {
        "event_id": 20,
        "event_name": "BolusCompleted",
        "seq": next(_seq),
        "timestamp": ts,
        "bolus_id": bolus_id,
        "completion_status": 3,
        "iob": units,
        "insulin_delivered": units,
        "insulin_requested": units,
    }


async def _run(hass: HomeAssistant, events: list[dict]):
    with freeze_time(_NOW.replace(tzinfo=timezone.utc)):
        return await _setup_coordinator(hass, _make_pump_events_data(events))


class TestCarbSensorsFromBolusRequests:
    async def test_last_carb_entry_from_calculator(self, hass: HomeAssistant):
        """Latest bolus with carbs sets last carb entry + time; a later correction-only
        bolus (carbAmount 0) is not a carb entry."""
        breakfast = _NOW - timedelta(hours=4)
        lunch = _NOW - timedelta(hours=1)
        events = [
            _cgm(_NOW),
            _msg1(breakfast, 11, 40),
            _msg3(breakfast, 11),
            _msg1(lunch, 12, 55),
            _msg3(lunch, 12),
            _msg1(_NOW - timedelta(minutes=10), 13, 0),
        ]
        coordinator = await _run(hass, events)

        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARBS] == 55
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARBS_TIMESTAMP].replace(tzinfo=None) == lunch

    async def test_daily_carbs_sums_today_only(self, hass: HomeAssistant):
        """Daily carbs sums today's calculator carbs; yesterday's are excluded."""
        events = [
            _cgm(_NOW),
            _msg1(_NOW - timedelta(days=1), 1, 70),  # yesterday
            _msg1(_NOW - timedelta(hours=5), 2, 30),
            _msg1(_NOW - timedelta(hours=2), 3, 45),
        ]
        coordinator = await _run(hass, events)

        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_CARBS] == 75

    async def test_repeated_bolus_id_counted_once(self, hass: HomeAssistant):
        """A msg1 logged twice for one bolus must not double the day's carbs."""
        ts = _NOW - timedelta(hours=1)
        events = [_cgm(_NOW), _msg1(ts, 7, 50), _msg1(ts, 7, 50)]
        coordinator = await _run(hass, events)

        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_CARBS] == 50

    async def test_correction_only_boluses_leave_carbs_unavailable(self, hass: HomeAssistant):
        """No carb amount anywhere -> unavailable, not a fabricated 0 (positive control:
        the bolus-calc sensor still reads the same msg1)."""
        events = [_cgm(_NOW), _msg1(_NOW - timedelta(hours=1), 5, 0), _msg3(_NOW - timedelta(hours=1), 5)]
        coordinator = await _run(hass, events)

        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_BOLUS_CARBS] == 0
        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_CARBS] is UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARBS] is UNAVAILABLE

    async def test_non_numeric_carb_amount_skipped(self, hass: HomeAssistant, caplog):
        """A malformed carbAmount is skipped and logged, never coerced."""
        events = [
            _cgm(_NOW),
            _msg1(_NOW - timedelta(hours=2), 1, 20),
            _msg1(_NOW - timedelta(hours=1), 2, "40"),
        ]
        coordinator = await _run(hass, events)

        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_CARBS] == 20
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARBS] == 20
        assert "carb amount '40'" in caplog.text

    async def test_malformed_amount_warns_once(self, hass: HomeAssistant, caplog, mock_import):
        """The sensor pass and the statistics pass share one warning per bad event."""
        events = [_cgm(_NOW), _msg1(_NOW - timedelta(hours=1), 2, -5)]
        coordinator = await _run(hass, events)
        await hass.async_block_till_done()
        await coordinator._import_statistics(events)  # a later poll's statistics pass

        assert caplog.text.count("ignoring carb amount -5") == 1

    async def test_nan_carb_amount_skipped(self, hass: HomeAssistant):
        events = [
            _cgm(_NOW),
            _msg1(_NOW - timedelta(hours=2), 1, 20),
            _msg1(_NOW - timedelta(hours=1), 2, float("nan")),
        ]
        coordinator = await _run(hass, events)

        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_CARBS] == 20
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARBS] == 20

    async def test_same_meal_on_both_events_counted_once(self, hass: HomeAssistant, caplog):
        """If the pump logs CarbsEntered (48) beside the calculator request for one meal,
        the meal counts once (the 48 amount); a differing amount is logged."""
        meal = _NOW - timedelta(hours=1)
        events = [
            _cgm(_NOW),
            _carbs48(meal - timedelta(minutes=1), 50),
            _msg1(meal, 21, 50),
            _carbs48(_NOW - timedelta(hours=4), 30),
            _msg1(_NOW - timedelta(hours=4) + timedelta(minutes=2), 22, 35),
        ]
        coordinator = await _run(hass, events)

        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_CARBS] == 80
        assert "differ from the carbs-entered event" in caplog.text

    async def test_missing_bolus_id_deduplicated_by_time(self, hass: HomeAssistant, caplog):
        ts = _NOW - timedelta(hours=1)
        events = [_cgm(_NOW), _msg1(ts, None, 25), _msg1(ts, None, 25)]
        coordinator = await _run(hass, events)

        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_CARBS] == 25
        assert "has no bolus id" in caplog.text

    async def test_event_48_without_amount_does_not_break_carbs(self, hass: HomeAssistant):
        """A 48 whose amount the mapper could not read is skipped, not summed as None."""
        events = [_cgm(_NOW), _carbs48(_NOW - timedelta(hours=2), None), _msg1(_NOW - timedelta(hours=1), 3, 45)]
        coordinator = await _run(hass, events)

        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_CARBS] == 45
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARBS] == 45

    async def test_event_48_still_counted_alongside(self, hass: HomeAssistant):
        """The legacy standalone carb event keeps working next to calculator carbs."""
        events = [
            _cgm(_NOW),
            _carbs48(_NOW - timedelta(hours=3), 15),
            _msg1(_NOW - timedelta(hours=1), 9, 35),
        ]
        coordinator = await _run(hass, events)

        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_CARBS] == 50
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARBS] == 35


class TestDailyCarbsZeroDay:
    """A day the pump has logged with no carb entries reads 0 g, as Tandem Source shows it."""

    async def test_logged_day_without_carbs_is_zero(self, hass: HomeAssistant):
        events = [
            _cgm(_NOW),
            _basal(_NOW - timedelta(hours=3), 0.8),
            _bolus_completed(_NOW - timedelta(hours=2), 31, 0.5),  # Control-IQ auto bolus
            _msg1(_NOW - timedelta(days=1), 30, 45),  # yesterday's meal
        ]
        coordinator = await _run(hass, events)

        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_CARBS] == 0
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARBS] == 45  # positive control

    async def test_no_pump_events_today_stays_unknown(self, hass: HomeAssistant):
        """Only yesterday's pump events: today's carbs are unknown, not 0."""
        events = [_cgm(_NOW), _basal(_NOW - timedelta(days=1), 0.8), _msg1(_NOW - timedelta(days=1), 30, 45)]
        coordinator = await _run(hass, events)

        assert coordinator.data[TANDEM_SENSOR_KEY_DAILY_CARBS] is UNAVAILABLE


class TestMealCarbStatisticsFromBolusRequests:
    async def test_calculator_carbs_imported_as_meal_carbs(self, hass: HomeAssistant, mock_import):
        coordinator = await make_tandem_coordinator(hass)
        events = [
            _msg1(datetime(2026, 10, 1, 8, 15), 1, 40),
            _msg1(datetime(2026, 10, 1, 8, 15), 1, 40),  # repeat of bolus 1
            _msg1(datetime(2026, 10, 1, 13, 5), 2, 0),  # correction only
            _msg1(datetime(2026, 10, 1, 18, 40), 3, 60),
        ]
        await coordinator._import_statistics(events)

        call = next(c for c in mock_import.call_args_list if c[0][1]["statistic_id"] == f"sensor.{DOMAIN}_meal_carbs")
        stats = call[0][2]
        assert [(s["start"].hour, s["mean"]) for s in stats] == [(8, 40.0), (18, 60.0)]

    async def test_meals_in_one_hour_are_summed(self, hass: HomeAssistant, mock_import):
        """HA keeps one row per hour; two meals in it must not overwrite each other."""
        coordinator = await make_tandem_coordinator(hass)
        events = [
            _msg1(datetime(2026, 10, 1, 18, 5), 1, 60),
            _msg1(datetime(2026, 10, 1, 18, 40), 2, 20),
        ]
        await coordinator._import_statistics(events)

        call = next(c for c in mock_import.call_args_list if c[0][1]["statistic_id"] == f"sensor.{DOMAIN}_meal_carbs")
        assert [(s["start"].hour, s["mean"]) for s in call[0][2]] == [(18, 80.0)]
