"""Tests for TandemCoordinator error paths and edge-case data branches.

Covers uncovered new-code lines in __init__.py:
- Lines 869-873: TandemAuthError / generic Exception during login
- Lines 883-884: dict metadata branch in _async_update_data
- Lines 911-914, 917: TandemApiError / generic exception / non-dict from get_recent_data
- Lines 1678-1679, 1686, 1693-1704: _parse_dashboard_summary None-field branches + exception
- Lines 1841-1847: _parse_pump_settings exception handler
- Lines 1959: _today_only null-timestamp skip
- Lines 1995-2002: basal_rate_changes fallback in _compute_insulin_summary
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from pytest_homeassistant_custom_component.common import MockConfigEntry
from unittest.mock import AsyncMock

from custom_components.carelink.const import (
    DOMAIN,
    PLATFORM_TANDEM,
    PLATFORM_TYPE,
    TANDEM_CLIENT,
    UNAVAILABLE,
    TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL,
    TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL,
    TANDEM_SENSOR_KEY_CGM_USAGE,
    TANDEM_SENSOR_KEY_TIME_IN_RANGE,
    TANDEM_SENSOR_KEY_ACTIVE_PROFILE,
    TANDEM_SENSOR_KEY_DAILY_BOLUS_TOTAL,
    TANDEM_SENSOR_KEY_DAILY_BASAL_TOTAL,
)


# ─── Helpers ───────────────────────────────────────────────────────────────


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "platform_type": "tandem",
            "tandem_email": "test@example.com",
            "tandem_password": "testpassword",
            "tandem_region": "EU",
            "scan_interval": 300,
        },
    )
    entry.add_to_hass(hass)
    return entry


def _make_client() -> AsyncMock:
    client = AsyncMock()
    client.login = AsyncMock(return_value=True)
    client.get_pump_event_metadata = AsyncMock(return_value=[{"maxDateWithEvents": "2026-03-06T18:00:00"}])
    client.get_recent_data = AsyncMock(
        return_value={
            "pump_metadata": {
                "serialNumber": "12345678",
                "modelNumber": "t:slim X2",
                "softwareVersion": "7.6.0",
                "lastUpload": "/Date(1705320000000)/",
            },
            "pumper_info": {"firstName": "Test", "lastName": "User"},
            "pump_events": [],
            "therapy_timeline": None,
            "dashboard_summary": None,
        }
    )
    client.close = AsyncMock()
    return client


async def _make_coordinator(hass: HomeAssistant):
    """Return a running TandemCoordinator and its mocked client."""
    from custom_components.carelink import TandemCoordinator

    entry = _make_entry(hass)
    client = _make_client()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        TANDEM_CLIENT: client,
        PLATFORM_TYPE: PLATFORM_TANDEM,
    }
    coordinator = TandemCoordinator(hass, entry, update_interval=timedelta(seconds=300))
    await coordinator.async_config_entry_first_refresh()
    return coordinator, client


# ─── _async_update_data error paths ────────────────────────────────────────


class TestUpdateDataLoginErrors:
    """Login failures raise ConfigEntryNotReady (lines 869–873)."""

    async def test_tandemautherror_during_login(self, hass: HomeAssistant):
        """TandemAuthError from login → UpdateFailed → ConfigEntryNotReady."""
        from custom_components.carelink import TandemCoordinator
        from custom_components.carelink.tandem_api import TandemAuthError

        entry = _make_entry(hass)
        client = _make_client()
        client.login = AsyncMock(side_effect=TandemAuthError("bad credentials"))
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: client,
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }
        coordinator = TandemCoordinator(hass, entry, update_interval=timedelta(seconds=300))
        with pytest.raises(ConfigEntryNotReady):
            await coordinator.async_config_entry_first_refresh()
        client.get_pump_event_metadata.assert_not_called()

    async def test_generic_exception_during_login(self, hass: HomeAssistant):
        """Generic exception from login → UpdateFailed → ConfigEntryNotReady."""
        from custom_components.carelink import TandemCoordinator

        entry = _make_entry(hass)
        client = _make_client()
        client.login = AsyncMock(side_effect=Exception("network timeout"))
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: client,
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }
        coordinator = TandemCoordinator(hass, entry, update_interval=timedelta(seconds=300))
        with pytest.raises(ConfigEntryNotReady):
            await coordinator.async_config_entry_first_refresh()
        client.get_pump_event_metadata.assert_not_called()


class TestUpdateDataMetadataBranch:
    """Dict-form metadata is handled (line 883–884)."""

    async def test_dict_metadata_accepted(self, hass: HomeAssistant):
        """When get_pump_event_metadata returns a dict, coordinator proceeds normally."""
        from custom_components.carelink import TandemCoordinator

        entry = _make_entry(hass)
        client = _make_client()
        client.get_pump_event_metadata = AsyncMock(return_value={"maxDateWithEvents": "2026-03-06T18:00:00"})
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: client,
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }
        coordinator = TandemCoordinator(hass, entry, update_interval=timedelta(seconds=300))
        await coordinator.async_config_entry_first_refresh()
        assert coordinator.data is not None


class TestUpdateDataFetchErrors:
    """get_recent_data failures raise ConfigEntryNotReady (lines 911–914, 917)."""

    async def test_tандемapierror_raises_updatefailed(self, hass: HomeAssistant):
        """TandemApiError from get_recent_data → ConfigEntryNotReady."""
        from custom_components.carelink import TandemCoordinator
        from custom_components.carelink.tandem_api import TandemApiError

        entry = _make_entry(hass)
        client = _make_client()
        client.get_recent_data = AsyncMock(side_effect=TandemApiError("server error"))
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: client,
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }
        coordinator = TandemCoordinator(hass, entry, update_interval=timedelta(seconds=300))
        with pytest.raises(ConfigEntryNotReady):
            await coordinator.async_config_entry_first_refresh()

    async def test_generic_exception_from_get_recent_data(self, hass: HomeAssistant):
        """Generic exception from get_recent_data → ConfigEntryNotReady."""
        from custom_components.carelink import TandemCoordinator

        entry = _make_entry(hass)
        client = _make_client()
        client.get_recent_data = AsyncMock(side_effect=Exception("timeout"))
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: client,
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }
        coordinator = TandemCoordinator(hass, entry, update_interval=timedelta(seconds=300))
        with pytest.raises(ConfigEntryNotReady):
            await coordinator.async_config_entry_first_refresh()

    async def test_non_dict_return_raises_updatefailed(self, hass: HomeAssistant):
        """Non-dict return from get_recent_data → ConfigEntryNotReady."""
        from custom_components.carelink import TandemCoordinator

        entry = _make_entry(hass)
        client = _make_client()
        client.get_recent_data = AsyncMock(return_value="not a dict")
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: client,
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }
        coordinator = TandemCoordinator(hass, entry, update_interval=timedelta(seconds=300))
        with pytest.raises(ConfigEntryNotReady):
            await coordinator.async_config_entry_first_refresh()


# ─── _parse_dashboard_summary edge cases ───────────────────────────────────


class TestParseDashboardSummary:
    """Direct tests of _parse_dashboard_summary branches (lines 1678–1704)."""

    async def test_average_reading_none_sets_unavailable(self, hass: HomeAssistant):
        """averageReading=None → both average glucose sensors set to UNAVAILABLE."""
        coordinator, _ = await _make_coordinator(hass)
        data: dict = {}
        coordinator._parse_dashboard_summary(
            {"timeInRangePercent": 72.5, "cgmInactivePercent": 5.0},
            data,
        )
        assert data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] is UNAVAILABLE
        assert data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] is UNAVAILABLE

    async def test_tir_none_sets_unavailable(self, hass: HomeAssistant):
        """timeInRangePercent=None → TIR set to UNAVAILABLE."""
        coordinator, _ = await _make_coordinator(hass)
        data: dict = {}
        coordinator._parse_dashboard_summary(
            {"averageReading": 120, "cgmInactivePercent": 5.0},
            data,
        )
        assert data[TANDEM_SENSOR_KEY_TIME_IN_RANGE] is UNAVAILABLE

    async def test_cgm_inactive_none_uses_time_in_use_percent(self, hass: HomeAssistant):
        """cgmInactivePercent absent + timeInUsePercent present → CGM_USAGE = timeInUsePercent."""
        coordinator, _ = await _make_coordinator(hass)
        data: dict = {}
        coordinator._parse_dashboard_summary(
            {"averageReading": 120, "timeInRangePercent": 70.0, "timeInUsePercent": 85.5},
            data,
        )
        assert data[TANDEM_SENSOR_KEY_CGM_USAGE] == 85.5

    async def test_both_cgm_usage_fields_absent_sets_unavailable(self, hass: HomeAssistant):
        """cgmInactivePercent and timeInUsePercent both absent → CGM_USAGE = UNAVAILABLE."""
        coordinator, _ = await _make_coordinator(hass)
        data: dict = {}
        coordinator._parse_dashboard_summary(
            {"averageReading": 120, "timeInRangePercent": 70.0},
            data,
        )
        assert data[TANDEM_SENSOR_KEY_CGM_USAGE] is UNAVAILABLE

    async def test_exception_sets_all_unavailable(self, hass: HomeAssistant):
        """TypeError from non-numeric averageReading → exception handler sets UNAVAILABLE."""
        coordinator, _ = await _make_coordinator(hass)
        data: dict = {}
        # int(object()) raises TypeError → triggers the except block
        coordinator._parse_dashboard_summary({"averageReading": object()}, data)
        assert data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MMOL] is UNAVAILABLE
        assert data[TANDEM_SENSOR_KEY_AVG_GLUCOSE_MGDL] is UNAVAILABLE
        assert data[TANDEM_SENSOR_KEY_TIME_IN_RANGE] is UNAVAILABLE
        assert data[TANDEM_SENSOR_KEY_CGM_USAGE] is UNAVAILABLE


# ─── _parse_pump_settings exception handler ────────────────────────────────


class TestParsePumpSettingsException:
    """Exception in settings parsing sets keys to UNAVAILABLE (lines 1841–1847)."""

    async def test_bad_profiles_type_triggers_exception(self, hass: HomeAssistant):
        """profiles as a string (not dict) triggers AttributeError → UNAVAILABLE fallback."""
        coordinator, _ = await _make_coordinator(hass)
        data: dict = {}
        # profiles is a string so profiles.get(...) raises AttributeError
        coordinator._parse_pump_settings(
            {"settings": {"profiles": "not_a_dict"}},
            data,
        )
        assert data.get(TANDEM_SENSOR_KEY_ACTIVE_PROFILE) is UNAVAILABLE


# ─── _compute_insulin_summary edge cases ───────────────────────────────────


class TestComputeInsulinSummaryEdgeCases:
    """Null timestamp skip and basal_rate_changes fallback (lines 1959, 1995–2002)."""

    async def test_null_timestamp_event_is_skipped(self, hass: HomeAssistant):
        """Bolus event with timestamp=None is filtered out by _today_only (line 1959)."""
        coordinator, _ = await _make_coordinator(hass)
        tz = ZoneInfo(coordinator.timezone)
        now = datetime.now(tz)
        data: dict = {}
        # Mix: one null-timestamp event (skipped) and one valid today event
        null_bolus = {"timestamp": None, "insulin_delivered": 2.0, "iob": 1.0}
        valid_bolus = {"timestamp": now, "insulin_delivered": 1.5, "iob": 0.5}
        coordinator._compute_insulin_summary([null_bolus, valid_bolus], [], [], [], [], data)
        # null_bolus is skipped; valid_bolus is included → total is 1.5
        assert data[TANDEM_SENSOR_KEY_DAILY_BOLUS_TOTAL] == 1.5

    async def test_basal_rate_changes_used_when_no_delivery_events(self, hass: HomeAssistant):
        """When basal_delivery is empty, basal_rate_changes provides the fallback (lines 1995–2002)."""
        coordinator, _ = await _make_coordinator(hass)
        tz = ZoneInfo(coordinator.timezone)
        now = datetime.now(tz)
        data: dict = {}
        rate1 = {"timestamp": now.replace(hour=8, minute=0, second=0, microsecond=0), "commanded_rate": 0.8}
        rate2 = {"timestamp": now.replace(hour=9, minute=0, second=0, microsecond=0), "commanded_rate": 0.9}
        coordinator._compute_insulin_summary([], [], [], [rate1, rate2], [], data)
        # basal_rate_changes fallback produces a non-UNAVAILABLE positive total
        assert data[TANDEM_SENSOR_KEY_DAILY_BASAL_TOTAL] is not UNAVAILABLE
        assert data[TANDEM_SENSOR_KEY_DAILY_BASAL_TOTAL] > 0
