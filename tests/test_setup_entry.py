"""Tests for async_setup_entry, async_unload_entry, and _migrate_legacy_logindata."""

from __future__ import annotations

import shutil as shutil_module
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.carelink.const import (
    CLIENT,
    COORDINATOR,
    DOMAIN,
    PLATFORM_CARELINK,
    PLATFORM_TANDEM,
    PLATFORM_TYPE,
    TANDEM_CLIENT,
    UPLOADER,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _tandem_entry(hass: HomeAssistant, nightscout: bool = False) -> MockConfigEntry:
    data = {
        PLATFORM_TYPE: PLATFORM_TANDEM,
        "tandem_email": "test@example.com",
        "tandem_password": "testpassword",
        "tandem_region": "EU",
        "scan_interval": 300,
    }
    if nightscout:
        data["nightscout_url"] = "https://nightscout.example.com"
        data["nightscout_api"] = "secret"
    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)
    return entry


def _carelink_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            PLATFORM_TYPE: PLATFORM_CARELINK,
            "cl_refresh_token": "refresh",
            "cl_token": "token",
            "cl_client_id": "client_id",
            "cl_client_secret": "client_secret",
            "cl_mag_identifier": "mag",
            "patientId": "patient",
            "scan_interval": 60,
        },
    )
    entry.add_to_hass(hass)
    return entry


def _tandem_patches(hass: HomeAssistant):
    """Patch out network-touching parts of _async_setup_tandem_entry."""
    mock_coord = MagicMock()
    mock_coord.async_config_entry_first_refresh = AsyncMock()
    mock_coord.data = {}
    return (
        patch("custom_components.carelink.TandemSourceClient"),
        patch("custom_components.carelink.TandemCoordinator", return_value=mock_coord),
        patch.object(hass.config_entries, "async_forward_entry_setups", return_value=None),
    )


def _carelink_patches(hass: HomeAssistant):
    """Patch out network-touching parts of _async_setup_carelink_entry."""
    mock_coord = MagicMock()
    mock_coord.async_config_entry_first_refresh = AsyncMock()
    return (
        patch("custom_components.carelink._migrate_legacy_logindata"),
        patch("custom_components.carelink.CarelinkClient"),
        patch("custom_components.carelink.CarelinkCoordinator", return_value=mock_coord),
        patch.object(hass.config_entries, "async_forward_entry_setups", return_value=None),
    )


# ── async_setup_entry routing ────────────────────────────────────────────────


class TestAsyncSetupEntryRouting:
    """async_setup_entry routes to the correct platform setup function."""

    async def test_routes_to_tandem_setup(self, hass: HomeAssistant):
        """Tandem config entry reaches _async_setup_tandem_entry."""
        from custom_components.carelink import async_setup_entry

        entry = _tandem_entry(hass)
        p_client, p_coord, p_fwd = _tandem_patches(hass)

        with p_client, p_coord, p_fwd:
            result = await async_setup_entry(hass, entry)

        assert result is True

    async def test_routes_to_carelink_setup(self, hass: HomeAssistant):
        """Carelink config entry reaches _async_setup_carelink_entry."""
        from custom_components.carelink import async_setup_entry

        entry = _carelink_entry(hass)
        p_migrate, p_client, p_coord, p_fwd = _carelink_patches(hass)

        with p_migrate, p_client, p_coord, p_fwd:
            result = await async_setup_entry(hass, entry)

        assert result is True


# ── _async_setup_tandem_entry (nightscout branch) ────────────────────────────


class TestTandemSetupNightscout:
    """Nightscout uploader is created when both URL and API key are configured."""

    async def test_tandem_setup_with_nightscout(self, hass: HomeAssistant):
        """Nightscout uploader is stored when nightscout_url and nightscout_api are set."""
        from custom_components.carelink import _async_setup_tandem_entry

        entry = _tandem_entry(hass, nightscout=True)
        p_client, p_coord, p_fwd = _tandem_patches(hass)

        with (
            p_client,
            p_coord,
            p_fwd,
            patch("custom_components.carelink.NightscoutUploader") as mock_ns,
        ):
            await _async_setup_tandem_entry(hass, entry, entry.data)

        mock_ns.assert_called_once_with("https://nightscout.example.com", "secret")
        assert UPLOADER in hass.data[DOMAIN][entry.entry_id]


# ── async_unload_entry — client close paths ──────────────────────────────────


class TestAsyncUnloadEntryClientClose:
    """async_unload_entry closes open HTTP clients."""

    async def test_carelink_client_closed_on_unload(self, hass: HomeAssistant):
        """CLIENT.close() is awaited during unload."""
        from custom_components.carelink import async_unload_entry

        entry = _carelink_entry(hass)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            CLIENT: mock_client,
            COORDINATOR: MagicMock(),
            PLATFORM_TYPE: PLATFORM_CARELINK,
        }

        with patch.object(hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=True)):
            result = await async_unload_entry(hass, entry)

        assert result is True
        mock_client.close.assert_awaited_once()

    async def test_carelink_client_close_exception_swallowed(self, hass: HomeAssistant):
        """Exception in CLIENT.close() is caught and unload still succeeds."""
        from custom_components.carelink import async_unload_entry

        entry = _carelink_entry(hass)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock(side_effect=Exception("close failed"))
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            CLIENT: mock_client,
            COORDINATOR: MagicMock(),
            PLATFORM_TYPE: PLATFORM_CARELINK,
        }

        with patch.object(hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=True)):
            result = await async_unload_entry(hass, entry)

        assert result is True

    async def test_tandem_client_close_exception_swallowed(self, hass: HomeAssistant):
        """Exception in TANDEM_CLIENT.close() is caught and unload still succeeds."""
        from custom_components.carelink import async_unload_entry

        entry = _tandem_entry(hass)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock(side_effect=Exception("close failed"))
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: mock_client,
            COORDINATOR: MagicMock(),
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }

        with patch.object(hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=True)):
            result = await async_unload_entry(hass, entry)

        assert result is True

    async def test_nightscout_uploader_closed_on_unload(self, hass: HomeAssistant):
        """UPLOADER.close() is awaited during unload."""
        from custom_components.carelink import async_unload_entry

        entry = _tandem_entry(hass, nightscout=True)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        mock_uploader = AsyncMock()
        mock_uploader.close = AsyncMock()
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: mock_client,
            UPLOADER: mock_uploader,
            COORDINATOR: MagicMock(),
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }

        with patch.object(hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=True)):
            result = await async_unload_entry(hass, entry)

        assert result is True
        mock_uploader.close.assert_awaited_once()

    async def test_nightscout_uploader_close_exception_swallowed(self, hass: HomeAssistant):
        """Exception in UPLOADER.close() is caught and unload still succeeds."""
        from custom_components.carelink import async_unload_entry

        entry = _tandem_entry(hass, nightscout=True)

        mock_client = AsyncMock()
        mock_client.close = AsyncMock()
        mock_uploader = AsyncMock()
        mock_uploader.close = AsyncMock(side_effect=Exception("uploader close failed"))
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
            TANDEM_CLIENT: mock_client,
            UPLOADER: mock_uploader,
            COORDINATOR: MagicMock(),
            PLATFORM_TYPE: PLATFORM_TANDEM,
        }

        with patch.object(hass.config_entries, "async_unload_platforms", new=AsyncMock(return_value=True)):
            result = await async_unload_entry(hass, entry)

        assert result is True


# ── _migrate_legacy_logindata — shared path ──────────────────────────────────


class TestMigrateLegacyLogindataSharedPath:
    """Tests for the shared-path branch of _migrate_legacy_logindata."""

    def test_shared_path_copy_success(self, tmp_path):
        """Shared auth file is copied to the entry-specific path."""
        from custom_components.carelink import _migrate_legacy_logindata
        from custom_components.carelink.api import AUTH_FILE_PREFIX, SHARED_AUTH_FILE

        shared_file = tmp_path / SHARED_AUTH_FILE
        shared_file.write_text('{"access_token": "shared_token"}')

        entry_id = "test_shared_success"
        _migrate_legacy_logindata(str(tmp_path), entry_id)

        new_file = tmp_path / f"{AUTH_FILE_PREFIX}_{entry_id}.json"
        assert new_file.exists()
        assert new_file.read_text() == '{"access_token": "shared_token"}'

    def test_shared_path_copy_oserror_logged(self, tmp_path):
        """OSError on shared-path copy is logged; function does not raise."""
        from custom_components.carelink import _migrate_legacy_logindata
        from custom_components.carelink.api import AUTH_FILE_PREFIX, SHARED_AUTH_FILE

        shared_file = tmp_path / SHARED_AUTH_FILE
        shared_file.write_text('{"access_token": "shared_token"}')

        entry_id = "test_shared_oserror"

        with patch.object(shutil_module, "copy", side_effect=OSError("disk full")):
            _migrate_legacy_logindata(str(tmp_path), entry_id)

        new_file = tmp_path / f"{AUTH_FILE_PREFIX}_{entry_id}.json"
        assert not new_file.exists()

    def test_legacy_path_copy_oserror_logged(self, tmp_path):
        """OSError on legacy-path copy is logged; function does not raise."""
        from custom_components.carelink import _migrate_legacy_logindata
        from custom_components.carelink.api import AUTH_FILE_PREFIX, LEGACY_AUTH_FILE

        # Build the legacy directory structure
        legacy_parts = LEGACY_AUTH_FILE.replace("\\", "/").split("/")
        legacy_dir = tmp_path
        for part in legacy_parts[:-1]:
            legacy_dir = legacy_dir / part
        legacy_dir.mkdir(parents=True, exist_ok=True)
        legacy_file = legacy_dir / legacy_parts[-1]
        legacy_file.write_text('{"access_token": "legacy_token"}')

        entry_id = "test_legacy_oserror"

        with patch.object(shutil_module, "copy", side_effect=OSError("read-only fs")):
            _migrate_legacy_logindata(str(tmp_path), entry_id)

        new_file = tmp_path / f"{AUTH_FILE_PREFIX}_{entry_id}.json"
        assert not new_file.exists()
