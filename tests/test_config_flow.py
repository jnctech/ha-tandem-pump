"""Tests for the Carelink config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.carelink.config_flow import (
    CannotConnect,
    InvalidAuth,
    validate_carelink_input,
    validate_tandem_input,
)
from custom_components.carelink.const import DOMAIN, PLATFORM_CARELINK, PLATFORM_TANDEM, PLATFORM_TYPE


class TestValidateInput:
    """Tests for the validate_carelink_input function."""

    async def test_validate_carelink_input_success(self):
        """Test successful validation."""
        mock_hass = MagicMock()

        with patch("custom_components.carelink.config_flow.CarelinkClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.login = AsyncMock(return_value=True)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            data = {
                "cl_token": "test_token",
                "cl_refresh_token": "test_refresh",
                "cl_client_id": "test_client_id",
                "cl_client_secret": "test_secret",
                "cl_mag_identifier": "test_mag",
                "patientId": "test_patient",
            }

            result = await validate_carelink_input(mock_hass, data)

            assert result == {"title": "Carelink"}
            mock_client.login.assert_called_once()
            mock_client.close.assert_called_once()

    async def test_validate_carelink_input_invalid_auth(self):
        """Test validation with invalid credentials."""
        mock_hass = MagicMock()

        with patch("custom_components.carelink.config_flow.CarelinkClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.login = AsyncMock(return_value=False)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            data = {
                "cl_token": "invalid_token",
                "cl_refresh_token": "invalid_refresh",
            }

            with pytest.raises(InvalidAuth):
                await validate_carelink_input(mock_hass, data)

    async def test_validate_carelink_input_nightscout_success(self):
        """Test validation with valid Nightscout configuration."""
        mock_hass = MagicMock()

        with (
            patch("custom_components.carelink.config_flow.CarelinkClient") as mock_client_class,
            patch("custom_components.carelink.config_flow.NightscoutUploader") as mock_uploader_class,
        ):
            mock_client = MagicMock()
            mock_client.login = AsyncMock(return_value=True)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            mock_uploader = MagicMock()
            mock_uploader.reachServer = AsyncMock(return_value=True)
            mock_uploader.close = AsyncMock()
            mock_uploader_class.return_value = mock_uploader

            data = {
                "cl_token": "test_token",
                "cl_refresh_token": "test_refresh",
                "nightscout_url": "https://nightscout.example.com",
                "nightscout_api": "secret123",
            }

            result = await validate_carelink_input(mock_hass, data)

            assert result == {"title": "Carelink"}
            mock_uploader.reachServer.assert_called_once()

    async def test_validate_carelink_input_nightscout_unreachable(self):
        """Test validation when Nightscout server is unreachable."""
        mock_hass = MagicMock()

        with (
            patch("custom_components.carelink.config_flow.CarelinkClient") as mock_client_class,
            patch("custom_components.carelink.config_flow.NightscoutUploader") as mock_uploader_class,
        ):
            mock_client = MagicMock()
            mock_client.login = AsyncMock(return_value=True)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            mock_uploader = MagicMock()
            mock_uploader.reachServer = AsyncMock(return_value=False)
            mock_uploader.close = AsyncMock()
            mock_uploader_class.return_value = mock_uploader

            data = {
                "cl_token": "test_token",
                "cl_refresh_token": "test_refresh",
                "nightscout_url": "https://nightscout.example.com",
                "nightscout_api": "secret123",
            }

            with pytest.raises(CannotConnect):
                await validate_carelink_input(mock_hass, data)

    async def test_validate_carelink_input_nightscout_url_only(self):
        """Test validation fails when only URL is provided."""
        mock_hass = MagicMock()

        with patch("custom_components.carelink.config_flow.CarelinkClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.login = AsyncMock(return_value=True)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            data = {
                "cl_token": "test_token",
                "cl_refresh_token": "test_refresh",
                "nightscout_url": "https://nightscout.example.com",
                # Missing nightscout_api
            }

            with pytest.raises(CannotConnect):
                await validate_carelink_input(mock_hass, data)

    async def test_validate_carelink_input_nightscout_api_only(self):
        """Test validation fails when only API key is provided."""
        mock_hass = MagicMock()

        with patch("custom_components.carelink.config_flow.CarelinkClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.login = AsyncMock(return_value=True)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            data = {
                "cl_token": "test_token",
                "cl_refresh_token": "test_refresh",
                "nightscout_api": "secret123",
                # Missing nightscout_url
            }

            with pytest.raises(CannotConnect):
                await validate_carelink_input(mock_hass, data)

    async def test_validate_carelink_input_invalid_url_scheme(self):
        """Test validation fails with invalid URL scheme."""
        mock_hass = MagicMock()

        with patch("custom_components.carelink.config_flow.CarelinkClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.login = AsyncMock(return_value=True)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            data = {
                "cl_token": "test_token",
                "cl_refresh_token": "test_refresh",
                "nightscout_url": "ftp://nightscout.example.com",
                "nightscout_api": "secret123",
            }

            with pytest.raises(CannotConnect):
                await validate_carelink_input(mock_hass, data)

    async def test_validate_carelink_input_url_without_host(self):
        """Test validation fails with URL without host."""
        mock_hass = MagicMock()

        with patch("custom_components.carelink.config_flow.CarelinkClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.login = AsyncMock(return_value=True)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            data = {
                "cl_token": "test_token",
                "cl_refresh_token": "test_refresh",
                "nightscout_url": "https://",
                "nightscout_api": "secret123",
            }

            with pytest.raises(CannotConnect):
                await validate_carelink_input(mock_hass, data)

    async def test_validate_carelink_input_strips_url_whitespace(self):
        """Test that URL whitespace is stripped."""
        mock_hass = MagicMock()

        with (
            patch("custom_components.carelink.config_flow.CarelinkClient") as mock_client_class,
            patch("custom_components.carelink.config_flow.NightscoutUploader") as mock_uploader_class,
        ):
            mock_client = MagicMock()
            mock_client.login = AsyncMock(return_value=True)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            mock_uploader = MagicMock()
            mock_uploader.reachServer = AsyncMock(return_value=True)
            mock_uploader.close = AsyncMock()
            mock_uploader_class.return_value = mock_uploader

            data = {
                "cl_token": "test_token",
                "cl_refresh_token": "test_refresh",
                "nightscout_url": "  https://nightscout.example.com  ",
                "nightscout_api": "secret123",
            }

            await validate_carelink_input(mock_hass, data)

            # URL should be stripped
            assert data["nightscout_url"] == "https://nightscout.example.com"


class TestCloseExceptionHandlers:
    """When client.close() raises, the warning is swallowed and validation succeeds."""

    async def test_carelink_close_exception_does_not_propagate(self):
        """validate_carelink_input succeeds even when client.close() raises."""
        mock_hass = MagicMock()

        with patch("custom_components.carelink.config_flow.CarelinkClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.login = AsyncMock(return_value=True)
            mock_client.close = AsyncMock(side_effect=Exception("close failed"))
            mock_cls.return_value = mock_client

            result = await validate_carelink_input(
                mock_hass,
                {"cl_token": "t", "cl_refresh_token": "r"},
            )

        assert result == {"title": "Carelink"}

    async def test_tandem_close_exception_does_not_propagate(self):
        """validate_tandem_input succeeds even when client.close() raises."""
        with patch("custom_components.carelink.config_flow.TandemSourceClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock()
            mock_client.close = AsyncMock(side_effect=Exception("close failed"))
            mock_cls.return_value = mock_client

            result = await validate_tandem_input(
                {"tandem_email": "a@b.com", "tandem_password": "x", "tandem_region": "EU"}
            )

        assert result == {"title": "Tandem t:slim (EU)"}

    async def test_nightscout_close_exception_does_not_propagate(self):
        """_validate_nightscout succeeds even when uploader.close() raises."""
        mock_hass = MagicMock()

        with (
            patch("custom_components.carelink.config_flow.CarelinkClient") as mock_client_class,
            patch("custom_components.carelink.config_flow.NightscoutUploader") as mock_uploader_class,
        ):
            mock_client = MagicMock()
            mock_client.login = AsyncMock(return_value=True)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            mock_uploader = MagicMock()
            mock_uploader.reachServer = AsyncMock(return_value=True)
            mock_uploader.close = AsyncMock(side_effect=Exception("uploader close failed"))
            mock_uploader_class.return_value = mock_uploader

            result = await validate_carelink_input(
                mock_hass,
                {
                    "cl_token": "t",
                    "cl_refresh_token": "r",
                    "nightscout_url": "https://nightscout.example.com",
                    "nightscout_api": "secret",
                },
            )

        assert result == {"title": "Carelink"}


class TestExceptionClasses:
    """Tests for custom exception classes."""

    def test_cannot_connect_exception(self):
        """Test CannotConnect exception can be raised."""
        with pytest.raises(CannotConnect):
            raise CannotConnect()

    def test_invalid_auth_exception(self):
        """Test InvalidAuth exception can be raised."""
        with pytest.raises(InvalidAuth):
            raise InvalidAuth()


class TestValidateTandemInputEdgeCases:
    """Edge cases for validate_tandem_input."""

    async def test_empty_email_raises_invalid_auth(self):
        """Empty email field raises InvalidAuth immediately."""
        with pytest.raises(InvalidAuth):
            await validate_tandem_input({"tandem_email": "", "tandem_password": "x", "tandem_region": "EU"})

    async def test_empty_password_raises_invalid_auth(self):
        """Empty password field raises InvalidAuth immediately."""
        with pytest.raises(InvalidAuth):
            await validate_tandem_input({"tandem_email": "a@b.com", "tandem_password": "", "tandem_region": "EU"})

    async def test_tandem_auth_error_raises_invalid_auth(self):
        """TandemAuthError from login() is re-raised as InvalidAuth."""
        from custom_components.carelink.tandem_api import TandemAuthError

        with patch("custom_components.carelink.config_flow.TandemSourceClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock(side_effect=TandemAuthError("bad creds"))
            mock_client.close = AsyncMock()
            mock_cls.return_value = mock_client

            with pytest.raises(InvalidAuth):
                await validate_tandem_input(
                    {"tandem_email": "a@b.com", "tandem_password": "wrong", "tandem_region": "EU"}
                )


class TestConfigFlowSteps:
    """Tests for ConfigFlow step methods using real hass."""

    async def test_step_user_shows_form(self, hass: HomeAssistant):
        """async_step_user with no input shows the platform selection form."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        assert result["type"] == "form"
        assert result["step_id"] == "user"

    async def test_step_user_selects_tandem(self, hass: HomeAssistant):
        """Selecting Tandem routes to the tandem configuration form."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {PLATFORM_TYPE: PLATFORM_TANDEM})
        assert result["type"] == "form"
        assert result["step_id"] == "tandem"

    async def test_step_user_selects_carelink(self, hass: HomeAssistant):
        """Selecting Carelink routes to the carelink configuration form."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {PLATFORM_TYPE: PLATFORM_CARELINK})
        assert result["type"] == "form"
        assert result["step_id"] == "carelink"

    async def test_step_tandem_cannot_connect(self, hass: HomeAssistant):
        """CannotConnect error sets base error on the tandem form."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {PLATFORM_TYPE: PLATFORM_TANDEM})
        with patch(
            "custom_components.carelink.config_flow.validate_tandem_input",
            side_effect=CannotConnect,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"tandem_email": "a@b.com", "tandem_password": "x", "tandem_region": "EU", "scan_interval": 300},
            )
        assert result["errors"]["base"] == "cannot_connect"

    async def test_step_tandem_invalid_auth(self, hass: HomeAssistant):
        """InvalidAuth error sets base error on the tandem form."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {PLATFORM_TYPE: PLATFORM_TANDEM})
        with patch(
            "custom_components.carelink.config_flow.validate_tandem_input",
            side_effect=InvalidAuth,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"tandem_email": "a@b.com", "tandem_password": "x", "tandem_region": "EU", "scan_interval": 300},
            )
        assert result["errors"]["base"] == "invalid_auth"

    async def test_step_tandem_exception(self, hass: HomeAssistant):
        """Generic exception sets 'unknown' base error on the tandem form."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {PLATFORM_TYPE: PLATFORM_TANDEM})
        with patch(
            "custom_components.carelink.config_flow.validate_tandem_input",
            side_effect=Exception("unexpected"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"tandem_email": "a@b.com", "tandem_password": "x", "tandem_region": "EU", "scan_interval": 300},
            )
        assert result["errors"]["base"] == "unknown"

    async def test_step_tandem_success(self, hass: HomeAssistant):
        """Successful validation creates a config entry."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {PLATFORM_TYPE: PLATFORM_TANDEM})
        with (
            patch(
                "custom_components.carelink.config_flow.validate_tandem_input",
                return_value={"title": "Tandem t:slim (EU)"},
            ),
            patch("custom_components.carelink.async_setup_entry", return_value=True),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"tandem_email": "a@b.com", "tandem_password": "x", "tandem_region": "EU", "scan_interval": 300},
            )
            await hass.async_block_till_done()
        assert result["type"] == "create_entry"
        assert result["title"] == "Tandem t:slim (EU)"

    async def test_step_carelink_cannot_connect(self, hass: HomeAssistant):
        """CannotConnect error sets base error on the carelink form."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {PLATFORM_TYPE: PLATFORM_CARELINK})
        with patch(
            "custom_components.carelink.config_flow.validate_carelink_input",
            side_effect=CannotConnect,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"scan_interval": 60},
            )
        assert result["errors"]["base"] == "cannot_connect"

    async def test_step_carelink_invalid_auth(self, hass: HomeAssistant):
        """InvalidAuth error sets base error on the carelink form."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {PLATFORM_TYPE: PLATFORM_CARELINK})
        with patch(
            "custom_components.carelink.config_flow.validate_carelink_input",
            side_effect=InvalidAuth,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"scan_interval": 60},
            )
        assert result["errors"]["base"] == "invalid_auth"

    async def test_step_carelink_exception(self, hass: HomeAssistant):
        """Generic exception sets 'unknown' base error on the carelink form."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {PLATFORM_TYPE: PLATFORM_CARELINK})
        with patch(
            "custom_components.carelink.config_flow.validate_carelink_input",
            side_effect=Exception("unexpected"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"scan_interval": 60},
            )
        assert result["errors"]["base"] == "unknown"

    async def test_step_carelink_success(self, hass: HomeAssistant):
        """Successful carelink validation creates a config entry."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {PLATFORM_TYPE: PLATFORM_CARELINK})
        with (
            patch(
                "custom_components.carelink.config_flow.validate_carelink_input",
                return_value={"title": "Carelink"},
            ),
            patch("custom_components.carelink.async_setup_entry", return_value=True),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"scan_interval": 60},
            )
            await hass.async_block_till_done()
        assert result["type"] == "create_entry"
        assert result["title"] == "Carelink"


class TestReconfigureFlow:
    """Tests for ConfigFlow.async_step_reconfigure."""

    async def test_reconfigure_tandem_shows_form(self, hass: HomeAssistant):
        """Reconfigure for a Tandem entry shows the reconfigure form."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                PLATFORM_TYPE: PLATFORM_TANDEM,
                "tandem_email": "a@b.com",
                "tandem_password": "x",
                "tandem_region": "EU",
                "scan_interval": 300,
            },
        )
        entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "reconfigure"

    async def test_reconfigure_carelink_shows_form(self, hass: HomeAssistant):
        """Reconfigure for a Carelink entry shows the reconfigure form."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                PLATFORM_TYPE: PLATFORM_CARELINK,
                "cl_token": "t",
                "cl_refresh_token": "r",
                "scan_interval": 60,
            },
        )
        entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "reconfigure"

    async def test_reconfigure_tandem_success(self, hass: HomeAssistant):
        """Successful reconfiguration updates the entry and aborts."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                PLATFORM_TYPE: PLATFORM_TANDEM,
                "tandem_email": "a@b.com",
                "tandem_password": "old",
                "tandem_region": "EU",
                "scan_interval": 300,
            },
        )
        entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        with (
            patch(
                "custom_components.carelink.config_flow.validate_tandem_input",
                return_value={"title": "Tandem t:slim (EU)"},
            ),
            patch(
                "homeassistant.config_entries.ConfigFlow.async_update_reload_and_abort",
                return_value={"type": "abort", "reason": "reconfigure_successful"},
                create=True,
            ),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"scan_interval": 600},
            )
        assert result["type"] == "abort"
        assert result["reason"] == "reconfigure_successful"

    async def test_reconfigure_tandem_cannot_connect(self, hass: HomeAssistant):
        """CannotConnect error on reconfigure shows error on form."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                PLATFORM_TYPE: PLATFORM_TANDEM,
                "tandem_email": "a@b.com",
                "tandem_password": "x",
                "tandem_region": "EU",
                "scan_interval": 300,
            },
        )
        entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        with patch(
            "custom_components.carelink.config_flow.validate_tandem_input",
            side_effect=CannotConnect,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"scan_interval": 300},
            )
        assert result["errors"]["base"] == "cannot_connect"

    async def test_reconfigure_tandem_invalid_auth(self, hass: HomeAssistant):
        """InvalidAuth error on reconfigure shows error on form."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                PLATFORM_TYPE: PLATFORM_TANDEM,
                "tandem_email": "a@b.com",
                "tandem_password": "x",
                "tandem_region": "EU",
                "scan_interval": 300,
            },
        )
        entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        with patch(
            "custom_components.carelink.config_flow.validate_tandem_input",
            side_effect=InvalidAuth,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"scan_interval": 300},
            )
        assert result["errors"]["base"] == "invalid_auth"

    async def test_reconfigure_tandem_exception(self, hass: HomeAssistant):
        """Generic exception on reconfigure shows 'unknown' error."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                PLATFORM_TYPE: PLATFORM_TANDEM,
                "tandem_email": "a@b.com",
                "tandem_password": "x",
                "tandem_region": "EU",
                "scan_interval": 300,
            },
        )
        entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        with patch(
            "custom_components.carelink.config_flow.validate_tandem_input",
            side_effect=Exception("unexpected"),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"scan_interval": 300},
            )
        assert result["errors"]["base"] == "unknown"

    async def test_reconfigure_carelink_success(self, hass: HomeAssistant):
        """Successful carelink reconfiguration updates the entry and aborts."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                PLATFORM_TYPE: PLATFORM_CARELINK,
                "cl_token": "t",
                "cl_refresh_token": "r",
                "scan_interval": 60,
            },
        )
        entry.add_to_hass(hass)
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reconfigure", "entry_id": entry.entry_id}
        )
        with (
            patch(
                "custom_components.carelink.config_flow.validate_carelink_input",
                return_value={"title": "Carelink"},
            ),
            patch(
                "homeassistant.config_entries.ConfigFlow.async_update_reload_and_abort",
                return_value={"type": "abort", "reason": "reconfigure_successful"},
                create=True,
            ),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {"scan_interval": 120},
            )
        assert result["type"] == "abort"
        assert result["reason"] == "reconfigure_successful"
