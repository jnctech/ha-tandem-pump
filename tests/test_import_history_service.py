"""Tests for the carelink.import_history service action."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant, ServiceCall

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.carelink.const import (
    COORDINATOR,
    DOMAIN,
    PLATFORM_TANDEM,
    PLATFORM_TYPE,
    TANDEM_CLIENT,
)


# ── Fixtures / helpers ────────────────────────────────────────────────────────


def _make_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a minimal Tandem config entry registered with hass."""
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
    return entry


def _make_mock_client(device_id: str = "device-abc-123") -> AsyncMock:
    """Return a mock TandemSourceClient with a known device_id."""
    client = AsyncMock()
    client.login = AsyncMock(return_value=True)
    client.get_pump_event_metadata = AsyncMock(
        return_value=[
            {
                "tconnectDeviceId": device_id,
                "serialNumber": "12345678",
                "maxDateWithEvents": "2026-03-06T18:00:00",
            }
        ]
    )
    client.get_pump_events = AsyncMock(return_value=[])
    client.close = AsyncMock()
    return client


def _setup_hass_data(hass: HomeAssistant, entry: MockConfigEntry, client: AsyncMock) -> MagicMock:
    """Store a mock coordinator in hass.data and return it."""
    from custom_components.carelink import TandemCoordinator

    coordinator = MagicMock(spec=TandemCoordinator)
    coordinator.client = client
    coordinator.timezone = "UTC"
    coordinator._import_statistics = AsyncMock()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        TANDEM_CLIENT: client,
        PLATFORM_TYPE: PLATFORM_TANDEM,
        COORDINATOR: coordinator,
    }
    return coordinator


def _make_call(start_date: str, end_date: str | None = None) -> ServiceCall:
    """Build a fake ServiceCall for import_history."""
    data: dict = {"start_date": start_date}
    if end_date is not None:
        data["end_date"] = end_date
    call = MagicMock(spec=ServiceCall)
    call.data = data
    return call


# ── Happy-path tests ─────────────────────────────────────────────────────────


class TestImportHistoryService:
    """Tests for the _handle_import_history service handler."""

    async def test_single_day_fetches_one_chunk(self, hass: HomeAssistant):
        """Single-day range fetches exactly one chunk with the correct dates."""
        from custom_components.carelink import _handle_import_history

        entry = _make_entry(hass)
        client = _make_mock_client()
        sample_event = {
            "event_id": 256,
            "timestamp": datetime(2026, 3, 1, 10, 0, 0),
            "glucose_mgdl": 108,
        }
        client.get_pump_events = AsyncMock(return_value=[sample_event])
        coordinator = _setup_hass_data(hass, entry, client)

        await _handle_import_history(hass, entry.entry_id, _make_call("2026-03-01", "2026-03-01"))

        client.login.assert_called_once()
        client.get_pump_event_metadata.assert_called_once()
        client.get_pump_events.assert_called_once_with("device-abc-123", "2026-03-01", "2026-03-01")
        coordinator._import_statistics.assert_called_once_with([sample_event])

    async def test_multi_day_range_chunks_correctly(self, hass: HomeAssistant):
        """A 10-day range is split into two 7-day chunks."""
        from custom_components.carelink import _handle_import_history

        entry = _make_entry(hass)
        client = _make_mock_client()
        client.get_pump_events = AsyncMock(return_value=[])
        _setup_hass_data(hass, entry, client)

        await _handle_import_history(hass, entry.entry_id, _make_call("2026-03-01", "2026-03-10"))

        # 10 days → chunk 1: Mar 01–07, chunk 2: Mar 08–10
        assert client.get_pump_events.call_count == 2
        calls = client.get_pump_events.call_args_list
        assert calls[0].args == ("device-abc-123", "2026-03-01", "2026-03-07")
        assert calls[1].args == ("device-abc-123", "2026-03-08", "2026-03-10")

    async def test_no_events_does_not_import(self, hass: HomeAssistant):
        """When API returns no events, _import_statistics is not called."""
        from custom_components.carelink import _handle_import_history

        entry = _make_entry(hass)
        client = _make_mock_client()
        client.get_pump_events = AsyncMock(return_value=[])
        coordinator = _setup_hass_data(hass, entry, client)

        await _handle_import_history(hass, entry.entry_id, _make_call("2026-03-01", "2026-03-03"))

        coordinator._import_statistics.assert_not_called()

    async def test_events_from_all_chunks_merged(self, hass: HomeAssistant):
        """Events from all chunks are merged and passed to _import_statistics."""
        from custom_components.carelink import _handle_import_history

        entry = _make_entry(hass)
        client = _make_mock_client()

        chunk1 = [{"event_id": 256, "timestamp": datetime(2026, 3, 1, 8, 0), "glucose_mgdl": 100}]
        chunk2 = [{"event_id": 256, "timestamp": datetime(2026, 3, 8, 8, 0), "glucose_mgdl": 120}]
        client.get_pump_events = AsyncMock(side_effect=[chunk1, chunk2])
        coordinator = _setup_hass_data(hass, entry, client)

        await _handle_import_history(hass, entry.entry_id, _make_call("2026-03-01", "2026-03-10"))

        coordinator._import_statistics.assert_called_once_with(chunk1 + chunk2)

    async def test_end_date_defaults_to_today_when_absent(self, hass: HomeAssistant):
        """Omitting end_date uses today as the upper bound."""
        from custom_components.carelink import _handle_import_history

        entry = _make_entry(hass)
        client = _make_mock_client()
        _setup_hass_data(hass, entry, client)

        fixed_today = "2026-03-06"
        with patch("custom_components.carelink.datetime") as mock_dt:
            now_mock = MagicMock()
            now_mock.strftime.return_value = fixed_today
            mock_dt.now.return_value = now_mock
            # fromisoformat must still work — delegate to real date
            from datetime import date as real_date

            with patch("custom_components.carelink.date", wraps=real_date):
                await _handle_import_history(hass, entry.entry_id, _make_call("2026-03-06"))

        # end_date defaults to "2026-03-06", so one chunk covering that single day
        client.get_pump_events.assert_called_once_with("device-abc-123", "2026-03-06", "2026-03-06")


# ── Error-handling tests ──────────────────────────────────────────────────────


class TestImportHistoryServiceErrors:
    """Tests that the service handler handles API failures gracefully."""

    async def test_login_failure_returns_early(self, hass: HomeAssistant):
        """Login failure causes handler to return without fetching events."""
        from custom_components.carelink import _handle_import_history

        entry = _make_entry(hass)
        client = _make_mock_client()
        client.login = AsyncMock(side_effect=Exception("auth error"))
        coordinator = _setup_hass_data(hass, entry, client)

        await _handle_import_history(hass, entry.entry_id, _make_call("2026-03-01", "2026-03-03"))

        client.get_pump_event_metadata.assert_not_called()
        coordinator._import_statistics.assert_not_called()

    async def test_metadata_failure_returns_early(self, hass: HomeAssistant):
        """Metadata fetch failure causes handler to return without fetching events."""
        from custom_components.carelink import _handle_import_history

        entry = _make_entry(hass)
        client = _make_mock_client()
        client.get_pump_event_metadata = AsyncMock(side_effect=Exception("network error"))
        coordinator = _setup_hass_data(hass, entry, client)

        await _handle_import_history(hass, entry.entry_id, _make_call("2026-03-01", "2026-03-03"))

        client.get_pump_events.assert_not_called()
        coordinator._import_statistics.assert_not_called()

    async def test_missing_device_id_returns_early(self, hass: HomeAssistant):
        """Missing tconnectDeviceId in metadata causes handler to return early."""
        from custom_components.carelink import _handle_import_history

        entry = _make_entry(hass)
        client = _make_mock_client()
        # Metadata response has no tconnectDeviceId
        client.get_pump_event_metadata = AsyncMock(return_value=[{"serialNumber": "12345678"}])
        coordinator = _setup_hass_data(hass, entry, client)

        await _handle_import_history(hass, entry.entry_id, _make_call("2026-03-01", "2026-03-03"))

        client.get_pump_events.assert_not_called()
        coordinator._import_statistics.assert_not_called()

    async def test_chunk_failure_skipped_remaining_processed(self, hass: HomeAssistant):
        """A failing chunk is logged and skipped; remaining chunks are still processed."""
        from custom_components.carelink import _handle_import_history

        entry = _make_entry(hass)
        client = _make_mock_client()

        good_events = [{"event_id": 256, "timestamp": datetime(2026, 3, 8, 8, 0), "glucose_mgdl": 110}]
        # chunk 1 (Mar 01–07) fails; chunk 2 (Mar 08–10) succeeds
        client.get_pump_events = AsyncMock(side_effect=[Exception("timeout"), good_events])
        coordinator = _setup_hass_data(hass, entry, client)

        await _handle_import_history(hass, entry.entry_id, _make_call("2026-03-01", "2026-03-10"))

        assert client.get_pump_events.call_count == 2
        coordinator._import_statistics.assert_called_once_with(good_events)

    async def test_empty_metadata_list_returns_early(self, hass: HomeAssistant):
        """Empty metadata list is handled gracefully (no device_id found)."""
        from custom_components.carelink import _handle_import_history

        entry = _make_entry(hass)
        client = _make_mock_client()
        client.get_pump_event_metadata = AsyncMock(return_value=[])
        coordinator = _setup_hass_data(hass, entry, client)

        await _handle_import_history(hass, entry.entry_id, _make_call("2026-03-01", "2026-03-03"))

        client.get_pump_events.assert_not_called()
        coordinator._import_statistics.assert_not_called()


# ── Service registration / constant tests ────────────────────────────────────


def _tandem_setup_patches(hass: HomeAssistant):
    """Context manager that patches away network-touching internals of _async_setup_tandem_entry."""
    mock_coord = MagicMock()
    mock_coord.async_config_entry_first_refresh = AsyncMock()
    mock_coord.data = {}

    return (
        patch("custom_components.carelink.TandemSourceClient"),
        patch("custom_components.carelink.TandemCoordinator", return_value=mock_coord),
        patch.object(hass.config_entries, "async_forward_entry_setups", return_value=None),
    )


class TestImportHistoryServiceRegistration:
    """Tests for service register/unregister lifecycle and module constant."""

    def test_service_constant_value(self):
        """SERVICE_IMPORT_HISTORY constant matches the expected string."""
        from custom_components.carelink import SERVICE_IMPORT_HISTORY

        assert SERVICE_IMPORT_HISTORY == "import_history"

    async def test_service_registered_on_tandem_setup(self, hass: HomeAssistant):
        """Service is registered when a Tandem entry is set up."""
        from custom_components.carelink import SERVICE_IMPORT_HISTORY, _async_setup_tandem_entry

        entry = _make_entry(hass)
        p_client, p_coord, p_fwd = _tandem_setup_patches(hass)

        with p_client, p_coord, p_fwd:
            await _async_setup_tandem_entry(hass, entry, entry.data)

        assert hass.services.has_service(DOMAIN, SERVICE_IMPORT_HISTORY)

    async def test_service_not_registered_twice(self, hass: HomeAssistant):
        """Setting up a second Tandem entry does not double-register the service."""
        from custom_components.carelink import SERVICE_IMPORT_HISTORY, _async_setup_tandem_entry

        entry = _make_entry(hass)
        p_client, p_coord, p_fwd = _tandem_setup_patches(hass)

        with p_client, p_coord, p_fwd:
            await _async_setup_tandem_entry(hass, entry, entry.data)
            # Second setup with a new entry — service already registered
            entry2 = _make_entry(hass)
            await _async_setup_tandem_entry(hass, entry2, entry2.data)

        # Still only one registration, no exception raised
        assert hass.services.has_service(DOMAIN, SERVICE_IMPORT_HISTORY)

    async def test_service_removed_on_unload(self, hass: HomeAssistant):
        """async_unload_entry removes the service when it is registered."""
        from custom_components.carelink import (
            SERVICE_IMPORT_HISTORY,
            _async_setup_tandem_entry,
            async_unload_entry,
        )

        entry = _make_entry(hass)
        p_client, p_coord, p_fwd = _tandem_setup_patches(hass)

        with p_client, p_coord, p_fwd:
            await _async_setup_tandem_entry(hass, entry, entry.data)

        assert hass.services.has_service(DOMAIN, SERVICE_IMPORT_HISTORY)

        # Restore entry_data so async_unload_entry can pop it
        client = _make_mock_client()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: client,
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }

        with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
            await async_unload_entry(hass, entry)

        assert not hass.services.has_service(DOMAIN, SERVICE_IMPORT_HISTORY)
