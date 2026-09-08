"""Tests for the fast-start / startup-latency behaviour.

Covers two changes made to reduce how long the integration blocks Home
Assistant setup:

1. The first refresh fetches only a short history window (STARTUP_HISTORY_DAYS)
   so entry setup completes quickly; the full window (FULL_HISTORY_DAYS) is
   backfilled off the setup critical path by ``async_backfill_full_history``.
2. ``get_recent_data`` reuses metadata the coordinator already fetched for its
   freshness check (``prefetched_metadata``) instead of fetching it twice.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.tandem.const import DOMAIN
from custom_components.tandem.coordinator import (
    FULL_HISTORY_DAYS,
    STARTUP_HISTORY_DAYS,
    TandemCoordinator,
)
from custom_components.tandem.tandem_api import TandemSourceClient

_MAX_DATE = "2024-01-15T12:00:00"


def _recent_data() -> dict[str, Any]:
    """Minimal get_recent_data payload sufficient for the coordinator to parse."""
    return {
        "pump_metadata": {
            "serialNumber": "12345678",
            "modelNumber": "t:slim X2",
            "softwareVersion": "7.6.0",
            "lastUpload": "/Date(1705320000000)/",
            "maxDateWithEvents": _MAX_DATE,
        },
        "pumper_info": {"firstName": "Test", "lastName": "User"},
        "pump_events": None,
        "therapy_timeline": {
            "cgm": [{"EventDateTime": "/Date(1705320000000)/", "Readings": [{"Value": 120, "Type": "EGV"}]}],
            "bolus": [],
            "basal": [],
        },
        "dashboard_summary": None,
    }


def _recent_data_with_sg(value: int, max_date: str) -> dict[str, Any]:
    """recent_data payload carrying a single CGM reading and a given maxDate."""
    data = _recent_data()
    data["pump_metadata"]["maxDateWithEvents"] = max_date
    data["therapy_timeline"]["cgm"] = [
        {"EventDateTime": "/Date(1705320000000)/", "Readings": [{"Value": value, "Type": "EGV"}]}
    ]
    return data


async def _make_coordinator(
    hass: HomeAssistant,
    recent_data_side_effect: list[Any] | None = None,
    metadata_side_effect: list[Any] | None = None,
) -> tuple[TandemCoordinator, AsyncMock]:
    """Build a TandemCoordinator wired to a mock client (no first refresh yet)."""
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
    entry.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)

    client = AsyncMock()
    client.login = AsyncMock(return_value=True)
    if metadata_side_effect is not None:
        client.get_pump_event_metadata = AsyncMock(side_effect=metadata_side_effect)
    else:
        client.get_pump_event_metadata = AsyncMock(return_value=[{"maxDateWithEvents": _MAX_DATE}])
    client.close = AsyncMock()
    if recent_data_side_effect is not None:
        client.get_recent_data = AsyncMock(side_effect=recent_data_side_effect)
    else:
        client.get_recent_data = AsyncMock(return_value=_recent_data())

    coordinator = TandemCoordinator(hass, entry, client, update_interval=timedelta(seconds=300))
    return coordinator, client


class TestFastStartWindow:
    """First refresh uses the short window; the backfill uses the full window."""

    async def test_first_refresh_uses_short_window(self, hass: HomeAssistant):
        coordinator, client = await _make_coordinator(hass)

        await coordinator.async_config_entry_first_refresh()

        client.get_recent_data.assert_called_once()
        assert client.get_recent_data.call_args.kwargs["history_days"] == STARTUP_HISTORY_DAYS

    async def test_backfill_uses_full_window(self, hass: HomeAssistant):
        coordinator, client = await _make_coordinator(hass)

        await coordinator.async_config_entry_first_refresh()
        await coordinator.async_backfill_full_history()

        assert client.get_recent_data.call_count == 2
        assert client.get_recent_data.call_args_list[1].kwargs["history_days"] == FULL_HISTORY_DAYS
        assert FULL_HISTORY_DAYS > STARTUP_HISTORY_DAYS

    async def test_coordinator_passes_prefetched_metadata(self, hass: HomeAssistant):
        """The coordinator hands its already-fetched metadata to get_recent_data."""
        coordinator, client = await _make_coordinator(hass)

        await coordinator.async_config_entry_first_refresh()

        prefetched = client.get_recent_data.call_args.kwargs["prefetched_metadata"]
        assert prefetched is not None
        assert prefetched["maxDateWithEvents"] == _MAX_DATE


class TestBackfillFailSafe:
    """A backfill failure must not downgrade the good short-window data."""

    async def test_backfill_failure_keeps_short_window_data(self, hass: HomeAssistant):
        coordinator, client = await _make_coordinator(
            hass,
            recent_data_side_effect=[_recent_data(), Exception("backfill network error")],
        )

        await coordinator.async_config_entry_first_refresh()
        assert coordinator.last_update_success is True
        good = dict(coordinator.data)

        # Backfill raises internally; it must be swallowed, not propagated.
        await coordinator.async_backfill_full_history()

        assert coordinator.last_update_success is True
        assert coordinator.data == good

    async def test_backfill_failure_resets_freshness_gate(self, hass: HomeAssistant):
        """A backfill failure clears _last_max_date so the next poll re-fetches.

        Guards the case where the backfill fails after having cached
        maxDateWithEvents: without the reset, the freshness short-circuit would
        keep serving the short-window stats until the pump produced a new maxDate.
        """
        coordinator, _client = await _make_coordinator(hass)
        await coordinator.async_config_entry_first_refresh()

        # Simulate the backfill update failing after it had cached maxDate.
        coordinator._last_max_date = _MAX_DATE
        with patch.object(coordinator, "_async_update_data", side_effect=Exception("boom")):
            await coordinator.async_backfill_full_history()

        assert coordinator._last_max_date is None
        assert coordinator.last_update_success is True


class TestSGDeltaBaseline:
    """The backfill must not fabricate a poll-to-poll glucose delta at startup."""

    _SG_DELTA = "tandem_last_sg_delta"

    async def test_no_spurious_delta_after_backfill(self, hass: HomeAssistant):
        """Short refresh + backfill see the same reading → delta stays unavailable."""
        coordinator, _client = await _make_coordinator(
            hass,
            recent_data_side_effect=[
                _recent_data_with_sg(120, _MAX_DATE),  # first refresh
                _recent_data_with_sg(120, _MAX_DATE),  # backfill (same reading)
            ],
            metadata_side_effect=[
                [{"maxDateWithEvents": _MAX_DATE}],  # first refresh
                [{"maxDateWithEvents": _MAX_DATE}],  # backfill
            ],
        )

        await coordinator.async_config_entry_first_refresh()
        await coordinator.async_backfill_full_history()

        # No genuine change observed yet → delta is unavailable, not 0.0.
        assert coordinator.data.get(self._SG_DELTA) is None

    async def test_delta_appears_on_next_genuine_poll(self, hass: HomeAssistant):
        """The real poll-to-poll delta is produced on the first scheduled poll."""
        coordinator, _client = await _make_coordinator(
            hass,
            recent_data_side_effect=[
                _recent_data_with_sg(120, _MAX_DATE),  # first refresh
                _recent_data_with_sg(120, _MAX_DATE),  # backfill
                _recent_data_with_sg(130, "2024-01-15T12:05:00"),  # next poll — new reading
            ],
            metadata_side_effect=[
                [{"maxDateWithEvents": _MAX_DATE}],  # first refresh
                [{"maxDateWithEvents": _MAX_DATE}],  # backfill
                [{"maxDateWithEvents": "2024-01-15T12:05:00"}],  # poll — changed
            ],
        )

        await coordinator.async_config_entry_first_refresh()
        await coordinator.async_backfill_full_history()
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # 130 - 120 mg/dL, established against the backfill's baseline.
        assert coordinator.data.get(self._SG_DELTA) == 10.0


class TestPrefetchedMetadataDedup:
    """get_recent_data reuses prefetched metadata instead of fetching twice."""

    def _client(self) -> TandemSourceClient:
        client = TandemSourceClient("user@test.com", "pass")
        client.pumper_id = "pump-123"
        client.account_id = "acct-456"
        client.access_token = "valid_token"
        return client

    async def test_prefetched_metadata_skips_metadata_fetch(self):
        client = self._client()
        prefetched = {"serialNumber": "SN123", "tconnectDeviceId": None}

        with (
            patch.object(client, "get_pump_event_metadata", new_callable=AsyncMock) as mock_meta,
            patch.object(client, "get_pumper_info", new_callable=AsyncMock, return_value={"firstName": "Test"}),
            patch.object(client, "get_therapy_timeline", new_callable=AsyncMock, return_value=None),
            patch.object(client, "get_dashboard_summary", new_callable=AsyncMock, return_value=None),
        ):
            data = await client.get_recent_data(prefetched_metadata=prefetched)

        mock_meta.assert_not_called()
        assert data["pump_metadata"] == prefetched

    async def test_without_prefetched_metadata_fetches(self):
        client = self._client()

        with (
            patch.object(
                client,
                "get_pump_event_metadata",
                new_callable=AsyncMock,
                return_value=[{"serialNumber": "SN123"}],
            ) as mock_meta,
            patch.object(client, "get_pumper_info", new_callable=AsyncMock, return_value={"firstName": "Test"}),
            patch.object(client, "get_therapy_timeline", new_callable=AsyncMock, return_value=None),
            patch.object(client, "get_dashboard_summary", new_callable=AsyncMock, return_value=None),
        ):
            data = await client.get_recent_data()

        mock_meta.assert_called_once()
        assert data["pump_metadata"] == {"serialNumber": "SN123"}


class TestHistoryDaysWindow:
    """history_days controls the pump-events date span passed to get_pump_events."""

    async def test_history_days_sets_fetch_span(self):
        client = TandemSourceClient("user@test.com", "pass")
        client.pumper_id = "pump-123"
        client.account_id = "acct-456"
        client.access_token = "valid_token"

        prefetched = {"tconnectDeviceId": "dev-1"}

        with (
            patch.object(client, "get_pumper_info", new_callable=AsyncMock, return_value={}),
            patch.object(client, "get_pump_events", new_callable=AsyncMock, return_value=[{"x": 1}]) as mock_events,
        ):
            await client.get_recent_data(history_days=1, prefetched_metadata=prefetched)
            start_1, end_1 = mock_events.call_args.args[1], mock_events.call_args.args[2]

            mock_events.reset_mock()
            await client.get_recent_data(history_days=7, prefetched_metadata=prefetched)
            start_7, end_7 = mock_events.call_args.args[1], mock_events.call_args.args[2]

        from datetime import date

        # Same end date; the 7-day window starts earlier than the 1-day window.
        assert end_1 == end_7
        assert date.fromisoformat(start_7) < date.fromisoformat(start_1)
        assert (date.fromisoformat(end_1) - date.fromisoformat(start_1)).days == 1
        assert (date.fromisoformat(end_7) - date.fromisoformat(start_7)).days == 7
