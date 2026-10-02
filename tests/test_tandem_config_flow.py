"""Tests for the Tandem config flow (single-step, Tandem-only)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.tandem.const import DOMAIN

_CREDS = {
    "tandem_email": "user@test.com",
    "tandem_password": "password123",
    "tandem_region": "EU",
    "scan_interval": 300,
}


class TestUserStep:
    """Tests for the single user configuration step."""

    async def test_user_step_shows_form(self, hass: HomeAssistant):
        """The initial step shows the Tandem credential form directly."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

    async def test_user_step_success(self, hass: HomeAssistant):
        """A valid login creates the entry and stamps platform_type=tandem."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})

        with (
            patch(
                "custom_components.tandem.config_flow.validate_tandem_input",
                new_callable=AsyncMock,
                return_value={"title": "Tandem t:slim (EU)"},
            ),
            patch("custom_components.tandem.async_setup_entry", return_value=True),
        ):
            result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=dict(_CREDS))
            await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Tandem t:slim (EU)"
        assert result["data"]["platform_type"] == "tandem"
        assert result["data"]["tandem_email"] == "user@test.com"
        assert result["data"]["tandem_region"] == "EU"
        assert result["data"]["scan_interval"] == 300

    async def test_user_step_invalid_auth(self, hass: HomeAssistant):
        """Invalid credentials surface an invalid_auth error on the form."""
        from custom_components.tandem.config_flow import InvalidAuth

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        with patch(
            "custom_components.tandem.config_flow.validate_tandem_input",
            new_callable=AsyncMock,
            side_effect=InvalidAuth(),
        ):
            result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=dict(_CREDS))

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_user_step_cannot_connect(self, hass: HomeAssistant):
        """An unreachable server surfaces a cannot_connect error."""
        from custom_components.tandem.config_flow import CannotConnect

        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        with patch(
            "custom_components.tandem.config_flow.validate_tandem_input",
            new_callable=AsyncMock,
            side_effect=CannotConnect(),
        ):
            result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=dict(_CREDS))

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_user_step_unknown_error(self, hass: HomeAssistant):
        """An unexpected error surfaces the unknown base error."""
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        with patch(
            "custom_components.tandem.config_flow.validate_tandem_input",
            new_callable=AsyncMock,
            side_effect=RuntimeError("boom"),
        ):
            result = await hass.config_entries.flow.async_configure(result["flow_id"], user_input=dict(_CREDS))

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "unknown"}


class TestValidateTandemInput:
    """Tests for the validate_tandem_input function."""

    async def test_validate_tandem_input_success(self, hass: HomeAssistant):
        """A successful login returns the region-titled result and closes the client."""
        from custom_components.tandem.config_flow import validate_tandem_input

        with patch("custom_components.tandem.config_flow.TandemSourceClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock(return_value=True)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            result = await validate_tandem_input(
                hass, {"tandem_email": "user@test.com", "tandem_password": "password", "tandem_region": "EU"}
            )

        assert result == {"title": "Tandem t:slim (EU)"}
        mock_client.login.assert_called_once()
        mock_client.close.assert_called_once()

    async def test_validate_tandem_input_injects_managed_session(self, hass: HomeAssistant):
        """The client is built with Home Assistant's managed httpx client, not a self-made one."""
        from custom_components.tandem.config_flow import validate_tandem_input

        with (
            patch("custom_components.tandem.config_flow.TandemSourceClient") as mock_client_class,
            patch("custom_components.tandem.config_flow.get_async_client") as mock_get_client,
        ):
            mock_client_class.return_value = AsyncMock()
            managed = object()
            mock_get_client.return_value = managed

            await validate_tandem_input(
                hass, {"tandem_email": "user@test.com", "tandem_password": "password", "tandem_region": "EU"}
            )

        mock_get_client.assert_called_once_with(hass)
        assert mock_client_class.call_args.kwargs["session"] is managed

    async def test_validate_tandem_input_missing_credentials(self, hass: HomeAssistant):
        """Empty email/password raises InvalidAuth without calling the API."""
        from custom_components.tandem.config_flow import InvalidAuth, validate_tandem_input

        with pytest.raises(InvalidAuth):
            await validate_tandem_input(hass, {"tandem_email": "", "tandem_password": "", "tandem_region": "EU"})

    async def test_validate_tandem_input_network_error_is_cannot_connect(self, hass: HomeAssistant):
        """A TandemApiError from login (network, 5xx) is mapped to CannotConnect, not InvalidAuth."""
        from custom_components.tandem.config_flow import CannotConnect, validate_tandem_input
        from custom_components.tandem.exceptions import TandemApiError

        with patch("custom_components.tandem.config_flow.TandemSourceClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock(side_effect=TandemApiError("Cannot reach login page"))
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            with pytest.raises(CannotConnect):
                await validate_tandem_input(
                    hass, {"tandem_email": "user@test.com", "tandem_password": "pw", "tandem_region": "EU"}
                )

    async def test_validate_tandem_input_login_fails(self, hass: HomeAssistant):
        """A TandemAuthError from login is mapped to InvalidAuth."""
        from custom_components.tandem.config_flow import InvalidAuth, validate_tandem_input
        from custom_components.tandem.exceptions import TandemAuthError

        with patch("custom_components.tandem.config_flow.TandemSourceClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock(side_effect=TandemAuthError("Login failed"))
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            with pytest.raises(InvalidAuth):
                await validate_tandem_input(
                    hass, {"tandem_email": "user@test.com", "tandem_password": "wrong", "tandem_region": "EU"}
                )
