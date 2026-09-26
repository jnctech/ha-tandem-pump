"""Previously dropped BFF data: PLGS (140), Control-IQ preconditions (230), CGM reading flags."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.core import HomeAssistant

from custom_components.tandem.const import (
    TANDEM_SENSOR_KEY_CGM_STATUS,
    TANDEM_SENSOR_KEY_CONTROL_IQ_MODE,
    TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE,
    UNAVAILABLE,
)
from custom_components.tandem.tandem_api import (
    EVT_AA_PCM_CHANGE,
    EVT_CGM_DATA_G7,
    EVT_PLGS_PERIODIC,
    map_pump_log_event,
)

from .test_expanded_data import BASE_TS, _make_cgm_event, _make_pump_events_data, _setup_coordinator


def _bff(code: int, props: dict) -> dict:
    return {"eventCode": code, "pumpDateTime": "2026-09-26T10:00:00", "sequenceNumber": 5, "eventProperties": props}


def _bff_to_coord(code: int, props: dict, seq: int, minutes_ago: int = 0) -> dict:
    """Run a BFF event through the real mapper, then place it on the test timeline."""
    evt = map_pump_log_event(_bff(code, props))
    assert evt is not None
    evt["seq"] = seq
    evt["timestamp"] = BASE_TS - timedelta(minutes=minutes_ago)
    return evt


class TestPlgsMapping:
    def test_valid_prediction(self):
        evt = map_pump_log_event(
            _bff(EVT_PLGS_PERIODIC, {"pgv": 95, "pgvValid": 1, "fmr": 110, "hoMinState": 0, "status": [0, 9]})
        )
        assert evt["event_name"] == "PLGSPeriodic"
        assert evt["predicted_glucose_mgdl"] == 95
        assert evt["homin_state"] == "On and available"
        assert evt["plgs_status"] == ["Suspend Predicted", "Unavailable - CGM Off"]

    def test_invalid_prediction_dropped(self):
        evt = map_pump_log_event(_bff(EVT_PLGS_PERIODIC, {"pgv": 95, "pgvValid": "FALSE"}))
        assert evt["pgv_valid"] is False
        assert evt["predicted_glucose_mgdl"] is None

    def test_absent_valid_flag_keeps_value(self):
        evt = map_pump_log_event(_bff(EVT_PLGS_PERIODIC, {"pgv": 120}))
        assert evt["predicted_glucose_mgdl"] == 120
        assert evt["homin_state"] is None
        assert evt["plgs_status"] is None


class TestPcmPreconditionMapping:
    def test_flags_from_ints_bools_and_strings(self):
        evt = map_pump_log_event(
            _bff(
                EVT_AA_PCM_CHANGE,
                {
                    "currentPcm": 1,
                    "closedLoopPreferred": True,
                    "cgmAvailable": 0,
                    "pumpSuspended": "FALSE",
                    "calculationAvailable": True,
                    "sufficientClosedLoopParams": "TRUE",
                },
            )
        )
        assert evt["cgm_available"] is False
        assert evt["pump_suspended"] is False
        assert evt["calculation_available"] is True
        assert evt["sufficient_closed_loop_params"] is True

    def test_absent_flags_are_none(self):
        evt = map_pump_log_event(_bff(EVT_AA_PCM_CHANGE, {"currentPcm": 3}))
        assert evt["cgm_available"] is None


class TestCgmReadingFlagsMapping:
    def test_index_array(self):
        evt = map_pump_log_event(_bff(EVT_CGM_DATA_G7, {"currentGlucoseDisplayValue": 120, "egvInfoBitmask": [1, 5]}))
        assert evt["egv_info"] == ["Backfill", "Valid Timestamp"]

    def test_absent(self):
        evt = map_pump_log_event(_bff(EVT_CGM_DATA_G7, {"currentGlucoseDisplayValue": 120}))
        assert evt["egv_info"] is None


class TestCoordinator:
    async def test_predicted_glucose_from_bff_event(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 110),
            _bff_to_coord(EVT_PLGS_PERIODIC, {"pgv": 98, "pgvValid": 1, "hoMinState": 0, "status": [0]}, 2),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] == 98
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE}_attributes"]
        assert attrs["prediction_state"] == "On and available"
        assert attrs["status"] == ["Suspend Predicted"]

    async def test_invalid_prediction_unavailable(self, hass: HomeAssistant):
        events = [_make_cgm_event(1, 110), _bff_to_coord(EVT_PLGS_PERIODIC, {"pgv": 98, "pgvValid": 0}, 2)]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_PREDICTED_GLUCOSE] is UNAVAILABLE

    async def test_open_loop_reason_cgm_unavailable(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 110),
            _bff_to_coord(
                EVT_AA_PCM_CHANGE,
                {"currentPcm": 1, "previousPcm": 3, "closedLoopPreferred": True, "cgmAvailable": False},
                2,
            ),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[TANDEM_SENSOR_KEY_CONTROL_IQ_MODE] == "Open Loop"
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_CONTROL_IQ_MODE}_attributes"]
        assert attrs["open_loop_reason"] == "CGM unavailable"
        assert attrs["previous_mode"] == "Closed Loop"

    async def test_no_reason_in_closed_loop(self, hass: HomeAssistant):
        events = [
            _make_cgm_event(1, 110),
            _bff_to_coord(EVT_AA_PCM_CHANGE, {"currentPcm": 3, "closedLoopPreferred": True, "cgmAvailable": True}, 2),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        assert coordinator.data[f"{TANDEM_SENSOR_KEY_CONTROL_IQ_MODE}_attributes"]["open_loop_reason"] is None

    async def test_cgm_status_reading_flags(self, hass: HomeAssistant):
        events = [
            _bff_to_coord(EVT_CGM_DATA_G7, {"currentGlucoseDisplayValue": 120, "egvInfoBitmask": [1, 6]}, 1, 10),
            _bff_to_coord(EVT_CGM_DATA_G7, {"currentGlucoseDisplayValue": 125, "egvInfoBitmask": [0, 5, 6]}, 2, 5),
        ]
        coordinator = await _setup_coordinator(hass, _make_pump_events_data(events))
        attrs = coordinator.data[f"{TANDEM_SENSOR_KEY_CGM_STATUS}_attributes"]
        assert attrs["reading_flags"] == ["Five Minute Reading", "Valid Timestamp", "Valid EGV"]
        assert attrs["backfilled"] is False
        assert attrs["backfilled_readings"] == 1
