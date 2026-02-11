"""Tests for the Tandem config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.carelink.const import DOMAIN


class TestPlatformSelectionStep:
    """Tests for the platform selection step (async_step_user)."""

    async def test_user_step_shows_platform_form(self, hass: HomeAssistant):
        """Test that user step shows platform selection form."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

    async def test_user_step_to_carelink(self, hass: HomeAssistant):
        """Test that selecting Carelink leads to carelink step."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"platform_type": "carelink"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "carelink"

    async def test_user_step_to_tandem(self, hass: HomeAssistant):
        """Test that selecting Tandem leads to tandem step."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"platform_type": "tandem"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "tandem"


class TestTandemStep:
    """Tests for the Tandem configuration step."""

    async def test_tandem_step_success(self, hass: HomeAssistant):
        """Test successful Tandem login creates entry."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"platform_type": "tandem"},
        )
        assert result["step_id"] == "tandem"

        with patch(
            "custom_components.carelink.config_flow.validate_tandem_input",
            new_callable=AsyncMock,
            return_value={"title": "Tandem t:slim"},
        ), patch(
            "custom_components.carelink.async_setup_entry",
            return_value=True,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    "tandem_email": "user@test.com",
                    "tandem_password": "password123",
                    "tandem_region": "EU",
                    "scan_interval": 300,
                },
            )
            await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Tandem t:slim"
        assert result["data"]["platform_type"] == "tandem"
        assert result["data"]["tandem_email"] == "user@test.com"
        assert result["data"]["tandem_region"] == "EU"
        assert result["data"]["scan_interval"] == 300

    async def test_tandem_step_invalid_auth(self, hass: HomeAssistant):
        """Test Tandem login with invalid credentials shows error."""
        from custom_components.carelink.config_flow import InvalidAuth

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"platform_type": "tandem"},
        )

        with patch(
            "custom_components.carelink.config_flow.validate_tandem_input",
            new_callable=AsyncMock,
            side_effect=InvalidAuth(),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    "tandem_email": "bad@test.com",
                    "tandem_password": "wrong",
                    "tandem_region": "EU",
                    "scan_interval": 300,
                },
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

    async def test_tandem_step_cannot_connect(self, hass: HomeAssistant):
        """Test Tandem login when server is unreachable."""
        from custom_components.carelink.config_flow import CannotConnect

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"platform_type": "tandem"},
        )

        with patch(
            "custom_components.carelink.config_flow.validate_tandem_input",
            new_callable=AsyncMock,
            side_effect=CannotConnect(),
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    "tandem_email": "user@test.com",
                    "tandem_password": "password",
                    "tandem_region": "EU",
                    "scan_interval": 300,
                },
            )

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    async def test_tandem_step_with_nightscout(self, hass: HomeAssistant):
        """Test Tandem config with Nightscout settings."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"platform_type": "tandem"},
        )

        with patch(
            "custom_components.carelink.config_flow.validate_tandem_input",
            new_callable=AsyncMock,
            return_value={"title": "Tandem t:slim"},
        ), patch(
            "custom_components.carelink.async_setup_entry",
            return_value=True,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    "tandem_email": "user@test.com",
                    "tandem_password": "password123",
                    "tandem_region": "EU",
                    "scan_interval": 300,
                    "nightscout_url": "https://my-ns.example.com",
                    "nightscout_api": "secret12chars",
                },
            )
            await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"]["nightscout_url"] == "https://my-ns.example.com"
        assert result["data"]["nightscout_api"] == "secret12chars"


class TestCarelinkStep:
    """Tests for the Carelink configuration step via real HA flow."""

    async def test_carelink_step_success(self, hass: HomeAssistant):
        """Test successful Carelink login creates entry."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"platform_type": "carelink"},
        )
        assert result["step_id"] == "carelink"

        with patch(
            "custom_components.carelink.config_flow.validate_carelink_input",
            new_callable=AsyncMock,
            return_value={"title": "Carelink"},
        ), patch(
            "custom_components.carelink.async_setup_entry",
            return_value=True,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={
                    "cl_token": "test_token",
                    "cl_refresh_token": "test_refresh",
                    "cl_client_id": "test_client",
                    "cl_client_secret": "test_secret",
                    "cl_mag_identifier": "test_mag",
                    "patientId": "test_patient",
                    "scan_interval": 60,
                },
            )
            await hass.async_block_till_done()

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Carelink"
        assert result["data"]["platform_type"] == "carelink"


class TestValidateTandemInput:
    """Tests for the validate_tandem_input function."""

    async def test_validate_tandem_input_success(self):
        """Test successful Tandem credential validation."""
        from custom_components.carelink.config_flow import validate_tandem_input

        mock_hass = MagicMock()

        with patch(
            "custom_components.carelink.config_flow.TandemSourceClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock(return_value=True)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            data = {
                "tandem_email": "user@test.com",
                "tandem_password": "password",
                "tandem_region": "EU",
            }

            result = await validate_tandem_input(mock_hass, data)

        assert result == {"title": "Tandem t:slim (EU)"}
        mock_client.login.assert_called_once()
        mock_client.close.assert_called_once()

    async def test_validate_tandem_input_login_fails(self):
        """Test validation when Tandem login returns False."""
        from custom_components.carelink.config_flow import (
            validate_tandem_input,
            InvalidAuth,
        )

        mock_hass = MagicMock()

        with patch(
            "custom_components.carelink.config_flow.TandemSourceClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock(return_value=False)
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            data = {
                "tandem_email": "user@test.com",
                "tandem_password": "wrong",
                "tandem_region": "EU",
            }

            with pytest.raises(InvalidAuth):
                await validate_tandem_input(mock_hass, data)

    async def test_validate_tandem_input_auth_error(self):
        """Test validation when TandemAuthError is raised."""
        from custom_components.carelink.config_flow import (
            validate_tandem_input,
            InvalidAuth,
        )
        from custom_components.carelink.tandem_api import TandemAuthError

        mock_hass = MagicMock()

        with patch(
            "custom_components.carelink.config_flow.TandemSourceClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.login = AsyncMock(side_effect=TandemAuthError("bad"))
            mock_client.close = AsyncMock()
            mock_client_class.return_value = mock_client

            data = {
                "tandem_email": "user@test.com",
                "tandem_password": "wrong",
                "tandem_region": "EU",
            }

            with pytest.raises(InvalidAuth):
                await validate_tandem_input(mock_hass, data)
