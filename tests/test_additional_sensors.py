"""Tests for v1.4.0 additional sensors parsed from pump events.

Covers:
- TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE  (event 256, rate_of_change field)
- TANDEM_SENSOR_KEY_CGM_STATUS          (event 256, status field → mapped string)
- TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL (event 33, insulin_volume field)
- TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON (event 11, suspend_reason field)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant

from conftest import make_tandem_coordinator

from custom_components.carelink.const import (
    UNAVAILABLE,
    TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE,
    TANDEM_SENSOR_KEY_CGM_STATUS,
    TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL,
    TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON,
)

_BASE_TS = datetime(2026, 3, 1, 12, 0, 0)


# ── Event factories ────────────────────────────────────────────────────────


def _cgm_event(
    seq: int = 1,
    glucose_mgdl: int = 120,
    rate_of_change: float | None = 0.3,
    status: int | None = 0,
    minutes_ago: int = 0,
) -> dict[str, Any]:
    evt: dict[str, Any] = {
        "event_id": 256,
        "event_name": "CGM_DATA_GXB",
        "seq": seq,
        "timestamp": _BASE_TS - timedelta(minutes=minutes_ago),
        "glucose_mgdl": glucose_mgdl,
    }
    if rate_of_change is not None:
        evt["rate_of_change"] = rate_of_change
    if status is not None:
        evt["status"] = status
    return evt


def _cartridge_event(
    seq: int = 1,
    insulin_volume: float | None = 300.0,
    minutes_ago: int = 0,
) -> dict[str, Any]:
    evt: dict[str, Any] = {
        "event_id": 33,
        "event_name": "CartridgeFilled",
        "seq": seq,
        "timestamp": _BASE_TS - timedelta(minutes=minutes_ago),
    }
    if insulin_volume is not None:
        evt["insulin_volume"] = insulin_volume
    return evt


def _suspend_event(
    seq: int = 1,
    event_id: int = 11,
    suspend_reason: str | None = "User",
    minutes_ago: int = 0,
) -> dict[str, Any]:
    """Build a suspend/resume event matching tandem_api.py output.

    suspend_reason is a human-readable string (e.g. "User", "Alarm")
    as produced by tandem_api.py's binary decoder, not the raw int code.
    """
    evt: dict[str, Any] = {
        "event_id": event_id,
        "event_name": "PumpingSuspended" if event_id == 11 else "PumpingResumed",
        "seq": seq,
        "timestamp": _BASE_TS - timedelta(minutes=minutes_ago),
    }
    if suspend_reason is not None:
        evt["suspend_reason"] = suspend_reason
    return evt


# ── Coordinator factory (delegates to shared conftest helper) ──────────────


async def _make_coordinator(hass: HomeAssistant, pump_events: list[dict]):
    """Create a minimal TandemCoordinator with specific pump_events."""
    return await make_tandem_coordinator(hass, pump_events=pump_events)


# ===========================================================================
# Tests: CGM rate of change
# ===========================================================================


class TestCGMRateOfChange:
    """Tests for TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE from event 256."""

    async def test_rate_of_change_populated(self, hass: HomeAssistant):
        """CGM event with rate_of_change produces the sensor value rounded to 1 dp."""
        coordinator = await _make_coordinator(hass, [_cgm_event(rate_of_change=1.23)])
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] == 1.2

    async def test_rate_of_change_negative(self, hass: HomeAssistant):
        """Negative rate_of_change (falling BG) is stored correctly."""
        coordinator = await _make_coordinator(hass, [_cgm_event(rate_of_change=-0.82)])
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] == -0.8

    async def test_rate_of_change_zero(self, hass: HomeAssistant):
        """Zero rate_of_change (flat) is stored as 0.0 (not UNAVAILABLE)."""
        coordinator = await _make_coordinator(hass, [_cgm_event(rate_of_change=0.0)])
        # rate_of_change=0.0 — round(0.0, 1) = 0.0, not None so not UNAVAILABLE
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] == 0.0

    async def test_rate_of_change_absent_is_unavailable(self, hass: HomeAssistant):
        """CGM event without rate_of_change field produces UNAVAILABLE."""
        coordinator = await _make_coordinator(hass, [_cgm_event(rate_of_change=None)])
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] is UNAVAILABLE

    async def test_rate_of_change_no_cgm_events_is_unavailable(self, hass: HomeAssistant):
        """No CGM events produces UNAVAILABLE for rate_of_change."""
        coordinator = await _make_coordinator(hass, [])
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_RATE_OF_CHANGE] is UNAVAILABLE


# ===========================================================================
# Tests: CGM status
# ===========================================================================


class TestCGMStatus:
    """Tests for TANDEM_SENSOR_KEY_CGM_STATUS from event 256 status field."""

    async def test_cgm_status_normal(self, hass: HomeAssistant):
        """Status 0 maps to 'Normal'."""
        coordinator = await _make_coordinator(hass, [_cgm_event(status=0)])
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_STATUS] == "Normal"

    async def test_cgm_status_high(self, hass: HomeAssistant):
        """Status 1 maps to 'High'."""
        coordinator = await _make_coordinator(hass, [_cgm_event(status=1)])
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_STATUS] == "High"

    async def test_cgm_status_low(self, hass: HomeAssistant):
        """Status 2 maps to 'Low'."""
        coordinator = await _make_coordinator(hass, [_cgm_event(status=2)])
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_STATUS] == "Low"

    async def test_cgm_status_unknown_code_is_unavailable(self, hass: HomeAssistant):
        """Unrecognised status code falls back to UNAVAILABLE."""
        coordinator = await _make_coordinator(hass, [_cgm_event(status=99)])
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_STATUS] is UNAVAILABLE

    async def test_cgm_status_absent_field_is_unavailable(self, hass: HomeAssistant):
        """CGM event with no status field produces UNAVAILABLE."""
        coordinator = await _make_coordinator(hass, [_cgm_event(status=None)])
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_STATUS] is UNAVAILABLE

    async def test_cgm_status_no_cgm_events_is_unavailable(self, hass: HomeAssistant):
        """No CGM events produces UNAVAILABLE for CGM status."""
        coordinator = await _make_coordinator(hass, [])
        assert coordinator.data[TANDEM_SENSOR_KEY_CGM_STATUS] is UNAVAILABLE


# ===========================================================================
# Tests: last cartridge fill amount
# ===========================================================================


class TestLastCartridgeFillAmount:
    """Tests for TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL from event 33."""

    async def test_fill_amount_populated(self, hass: HomeAssistant):
        """Cartridge event with insulin_volume > 0 populates the sensor."""
        coordinator = await _make_coordinator(hass, [_cartridge_event(insulin_volume=287.5)])
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL] == 287.5

    async def test_fill_amount_rounded(self, hass: HomeAssistant):
        """Fill amount is rounded to 1 decimal place."""
        coordinator = await _make_coordinator(hass, [_cartridge_event(insulin_volume=299.99)])
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL] == 300.0

    async def test_zero_fill_volume_is_unavailable(self, hass: HomeAssistant):
        """insulin_volume of 0.0 produces UNAVAILABLE."""
        coordinator = await _make_coordinator(hass, [_cartridge_event(insulin_volume=0.0)])
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL] is UNAVAILABLE

    async def test_none_fill_volume_is_unavailable(self, hass: HomeAssistant):
        """Missing insulin_volume field produces UNAVAILABLE."""
        coordinator = await _make_coordinator(hass, [_cartridge_event(insulin_volume=None)])
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL] is UNAVAILABLE

    async def test_no_cartridge_events_is_unavailable(self, hass: HomeAssistant):
        """No cartridge events produces UNAVAILABLE for fill amount."""
        coordinator = await _make_coordinator(hass, [])
        assert coordinator.data[TANDEM_SENSOR_KEY_LAST_CARTRIDGE_FILL] is UNAVAILABLE


# ===========================================================================
# Tests: pump suspend reason
# ===========================================================================


class TestPumpSuspendReason:
    """Tests for TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON from event 11."""

    async def test_suspend_reason_user(self, hass: HomeAssistant):
        """Suspend reason 'User' passed through from API decoder."""
        coordinator = await _make_coordinator(hass, [_suspend_event(event_id=11, suspend_reason="User")])
        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] == "User"

    async def test_suspend_reason_alarm(self, hass: HomeAssistant):
        """Suspend reason 'Alarm' passed through from API decoder."""
        coordinator = await _make_coordinator(hass, [_suspend_event(event_id=11, suspend_reason="Alarm")])
        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] == "Alarm"

    async def test_suspend_reason_malfunction(self, hass: HomeAssistant):
        """Suspend reason 'Malfunction' passed through from API decoder."""
        coordinator = await _make_coordinator(hass, [_suspend_event(event_id=11, suspend_reason="Malfunction")])
        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] == "Malfunction"

    async def test_suspend_reason_auto_plgs(self, hass: HomeAssistant):
        """Suspend reason 'Auto-PLGS' passed through from API decoder."""
        coordinator = await _make_coordinator(hass, [_suspend_event(event_id=11, suspend_reason="Auto-PLGS")])
        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] == "Auto-PLGS"

    async def test_resumed_event_reason_is_unavailable(self, hass: HomeAssistant):
        """Last event is a RESUME (event_id=12) — reason not applicable → UNAVAILABLE."""
        coordinator = await _make_coordinator(hass, [_suspend_event(event_id=12, suspend_reason=None)])
        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] is UNAVAILABLE

    async def test_unknown_suspend_reason_passed_through(self, hass: HomeAssistant):
        """Unrecognised suspend reason from API decoder is passed through as-is.

        tandem_api.py produces 'Unknown (N)' for unknown codes. The coordinator
        passes it through without re-interpreting.
        """
        coordinator = await _make_coordinator(hass, [_suspend_event(event_id=11, suspend_reason="Unknown (99)")])
        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] == "Unknown (99)"

    async def test_no_suspend_events_is_unavailable(self, hass: HomeAssistant):
        """No suspend/resume events produces UNAVAILABLE for suspend reason."""
        coordinator = await _make_coordinator(hass, [])
        assert coordinator.data[TANDEM_SENSOR_KEY_PUMP_SUSPEND_REASON] is UNAVAILABLE
