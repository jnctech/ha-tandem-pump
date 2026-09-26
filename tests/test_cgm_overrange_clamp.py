"""Over-range CGM clamp — safety regression tests (ISS-260908-glucose-g7).

Root cause (confirmed 2026-09-08 via a live event-399 probe): when the CGM reports
out-of-range (``glucoseValueStatus`` High/Low), the BFF ``currentGlucoseDisplayValue``
is not a valid display reading. G6 (event 256) sends a ~0 sentinel; G7 (event 399)
sends a LARGE raw estimate (observed 400–1200 mg/dL at status=High), which the old code
surfaced verbatim → 33–66 mmol/L, a fabricated extreme presented as a live decision-input.

The coordinator now clamps glucose_mgdl to the sensor's reportable bound at the source
(High → 400 mg/dL / 22.2 mmol, Low → 40 mg/dL / 2.2 mmol) so BOTH the latest-glucose
sensor and every derived summary stat (avg / TIR / GMI / SG-delta) use the bounded value.
In-range (status=0/Normal) readings are untouched.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from conftest import make_tandem_coordinator

from custom_components.tandem.const import (
    CGM_GLUCOSE_MGDL_MAX,
    CGM_GLUCOSE_MGDL_MIN,
    CGM_STATUS_HIGH,
    CGM_STATUS_LOW,
    DOMAIN,
    TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL,
    TANDEM_SENSOR_KEY_CGM_STATUS,
    TANDEM_SENSOR_KEY_LASTSG_MGDL,
    TANDEM_SENSOR_KEY_LASTSG_MMOL,
)
from custom_components.tandem.coordinator import _clamp_cgm_over_range
from custom_components.tandem.tandem_api import map_pump_log_event

_BASE_TS = datetime(2026, 9, 8, 12, 0, 0)

EVT_G7 = 399  # EVT_CGM_DATA_G7 — the sensor that exposed the bug
EVT_G6 = 256  # EVT_CGM_DATA_GXB — regression guard


def _cgm(event_id: int, glucose_mgdl: int, status: int | str | None, minutes_ago: int = 0) -> dict[str, Any]:
    """Build a decoded CGM pump event as the mapper/decoder would produce."""
    evt: dict[str, Any] = {
        "event_id": event_id,
        "event_name": "CGM",
        "seq": 1000 - minutes_ago,
        "timestamp": _BASE_TS - timedelta(minutes=minutes_ago),
        "glucose_mgdl": glucose_mgdl,
        "rate_of_change": 0.0,
    }
    if status is not None:
        evt["status"] = status
    return evt


class TestCgmOverRangeClamp:
    """glucoseValueStatus High/Low must clamp; Normal must pass through."""

    async def test_g7_high_clamps_to_ceiling(self, hass: HomeAssistant):
        """G7 High-status raw 810 mg/dL (→45 mmol) must clamp to 400 mg/dL / 22.2 mmol."""
        coordinator = await make_tandem_coordinator(hass, pump_events=[_cgm(EVT_G7, 810, CGM_STATUS_HIGH)])
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == CGM_GLUCOSE_MGDL_MAX
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MMOL] == round(CGM_GLUCOSE_MGDL_MAX * 0.0555, 2)
        # Status label still reports High so the UI shows the over-range condition.
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_STATUS] == "High"

    async def test_g7_low_clamps_to_floor(self, hass: HomeAssistant):
        """G7 Low-status must clamp up to the reportable floor (40 mg/dL / 2.2 mmol)."""
        coordinator = await make_tandem_coordinator(hass, pump_events=[_cgm(EVT_G7, 5, CGM_STATUS_LOW)])
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == CGM_GLUCOSE_MGDL_MIN
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MMOL] == round(CGM_GLUCOSE_MGDL_MIN * 0.0555, 2)
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_STATUS] == "Low"

    async def test_g7_normal_passes_through(self, hass: HomeAssistant):
        """In-range (status=0/Normal) G7 readings are NOT clamped."""
        coordinator = await make_tandem_coordinator(hass, pump_events=[_cgm(EVT_G7, 150, 0)])
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == 150
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MMOL] == round(150 * 0.0555, 2)
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_STATUS] == "Normal"

    async def test_g6_high_also_clamped(self, hass: HomeAssistant):
        """G6 High (sentinel ~0) now clamps to the ceiling too (was: gated unavailable)."""
        coordinator = await make_tandem_coordinator(hass, pump_events=[_cgm(EVT_G6, 0, CGM_STATUS_HIGH)])
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == CGM_GLUCOSE_MGDL_MAX
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_STATUS] == "High"

    async def test_missing_status_in_band_passes_through(self, hass: HomeAssistant):
        """A plausible reading with no status passes through unchanged (no false clamp)."""
        coordinator = await make_tandem_coordinator(hass, pump_events=[_cgm(EVT_G7, 150, None)])
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == 150

    async def test_missing_status_out_of_band_clamped(self, hass: HomeAssistant):
        """An out-of-band magnitude with NO status must NOT slip through unclamped.

        This is the safety hole: the original bug re-appears if the raw over-range
        value arrives while its status trigger is missing/malformed. Clamp defensively.
        """
        coordinator = await make_tandem_coordinator(hass, pump_events=[_cgm(EVT_G7, 810, None)])
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == CGM_GLUCOSE_MGDL_MAX

    async def test_string_status_coerced(self, hass: HomeAssistant):
        """A stringified status ("1") must still clamp (type coercion)."""
        coordinator = await make_tandem_coordinator(hass, pump_events=[_cgm(EVT_G7, 810, "1")])
        assert coordinator.data[TANDEM_SENSOR_KEY_LASTSG_MGDL] == CGM_GLUCOSE_MGDL_MAX

    async def test_downstream_summary_uses_clamped_values(self, hass: HomeAssistant):
        """Derived stats must consume the clamped value, not the raw extreme.

        Readings [150, 810(High), 900(High)] clamp to [150, 400, 400] → avg 317 mg/dL.
        Unclamped would be (150+810+900)/3 = 620 — the bug this guards against.
        """
        coordinator = await make_tandem_coordinator(
            hass,
            pump_events=[
                _cgm(EVT_G7, 150, 0, minutes_ago=10),
                _cgm(EVT_G7, 810, CGM_STATUS_HIGH, minutes_ago=5),
                _cgm(EVT_G7, 900, CGM_STATUS_HIGH, minutes_ago=0),
            ],
        )
        expected = round((150 + CGM_GLUCOSE_MGDL_MAX + CGM_GLUCOSE_MGDL_MAX) / 3)
        assert coordinator.data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] == expected


class TestClampHelperFailVisible:
    """The clamp must be fail-visible: log every substitution, WARN on decode-fault signatures."""

    def test_expected_high_logs_debug_not_warning(self, caplog):
        """A genuine peg (High + large raw) clamps and logs at DEBUG, not WARNING."""
        evt = {"event_id": EVT_G7, "glucose_mgdl": 810, "status": CGM_STATUS_HIGH}
        with caplog.at_level(logging.DEBUG, logger="custom_components.tandem.coordinator"):
            _clamp_cgm_over_range(evt)
        assert evt["glucose_mgdl"] == CGM_GLUCOSE_MGDL_MAX
        assert "over-range clamp" in caplog.text
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_contradictory_high_warns(self, caplog):
        """High status with an in-band raw is a decode-fault signature → WARNING."""
        evt = {"event_id": EVT_G7, "glucose_mgdl": 150, "status": CGM_STATUS_HIGH}
        with caplog.at_level(logging.DEBUG, logger="custom_components.tandem.coordinator"):
            _clamp_cgm_over_range(evt)
        assert evt["glucose_mgdl"] == CGM_GLUCOSE_MGDL_MAX
        assert [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_out_of_band_no_status_warns(self, caplog):
        """Out-of-band magnitude with no status → clamp + WARNING (missing-status hole)."""
        evt = {"event_id": EVT_G7, "glucose_mgdl": 810}
        with caplog.at_level(logging.DEBUG, logger="custom_components.tandem.coordinator"):
            _clamp_cgm_over_range(evt)
        assert evt["glucose_mgdl"] == CGM_GLUCOSE_MGDL_MAX
        assert [r for r in caplog.records if r.levelno >= logging.WARNING]

    def test_in_band_normal_untouched_and_silent(self, caplog):
        """A normal in-band reading is neither clamped nor logged."""
        evt = {"event_id": EVT_G7, "glucose_mgdl": 150, "status": 0}
        with caplog.at_level(logging.DEBUG, logger="custom_components.tandem.coordinator"):
            _clamp_cgm_over_range(evt)
        assert evt["glucose_mgdl"] == 150
        assert "over-range clamp" not in caplog.text


class TestMapperStatusIsInt:
    """The clamp's == comparison rests on glucoseValueStatus mapping to a scalar int."""

    def test_map_pump_log_event_yields_int_status(self):
        """The BFF mapper must produce an int status (not a list/bitmask/string)."""
        raw = {
            "eventCode": EVT_G7,
            "pumpDateTime": "2026-09-08T12:00:00",
            "sequenceNumber": 1,
            "eventProperties": {
                "currentGlucoseDisplayValue": 810,
                "glucoseValueStatus": 1,
                "rate": 0,
            },
        }
        evt = map_pump_log_event(raw)
        assert evt is not None
        assert evt["status"] == 1
        assert isinstance(evt["status"], int)
        # Mapper does NOT clamp — that is the coordinator's job (single source).
        assert evt["glucose_mgdl"] == 810


class TestLtsImportUsesClampedValue:
    """The LTS statistics import consumes the same in-place-clamped event dicts."""

    async def test_cgm_stat_import_is_clamped(self, hass: HomeAssistant, mock_import):
        """A High reading must import the clamped bound (22.2 mmol), not the raw extreme."""
        coordinator = await make_tandem_coordinator(hass)
        events = [_cgm(EVT_G7, 810, CGM_STATUS_HIGH)]
        data: dict[str, Any] = {}
        # Parse mutates the events in place (the clamp), exactly as production does
        # before the scheduled statistics-import task reads them.
        coordinator._parse_pump_events(events, data)
        await coordinator._import_statistics(events)

        full_id = f"sensor.{DOMAIN}_last_glucose_level_mmol"
        call = next(c for c in mock_import.call_args_list if c[0][1]["statistic_id"] == full_id)
        stats = call[0][2]
        expected_mmol = round(CGM_GLUCOSE_MGDL_MAX * 0.0555, 2)
        assert stats[0]["mean"] == expected_mmol
