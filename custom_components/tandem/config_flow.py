"""Config flow for the Tandem integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.httpx_client import get_async_client

from .const import CONF_EMAIL, CONF_PASSWORD, CONF_REGION, DOMAIN, PLATFORM_TANDEM, PLATFORM_TYPE, SCAN_INTERVAL
from .exceptions import TandemApiError, TandemAuthError
from .tandem_api import TandemSourceClient

_LOGGER = logging.getLogger(__name__)

REGIONS = {"EU": "Europe", "US": "United States"}


async def validate_tandem_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate Tandem Source credentials by performing a login."""
    email = data.get(CONF_EMAIL, "").strip()
    password = data.get(CONF_PASSWORD, "")
    region = data.get(CONF_REGION, "EU")

    if not email or not password:
        raise InvalidAuth

    client = TandemSourceClient(email, password, region, session=get_async_client(hass))
    try:
        await client.login()
    except TandemAuthError as err:
        _LOGGER.warning("Tandem login failed: %s", err)
        raise InvalidAuth from err
    except TandemApiError as err:
        _LOGGER.warning("Cannot reach Tandem Source: %s", err)
        raise CannotConnect from err
    finally:
        try:
            await client.close()
        except Exception:  # noqa: BLE001 - close must not mask the validation result
            _LOGGER.warning("Failed to close Tandem client during validation")

    return {"title": f"Tandem t:slim ({region})"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tandem."""

    VERSION = 1

    def _schema(self, defaults: dict[str, Any] | None = None, *, include_auth: bool = True) -> vol.Schema:
        """Build the Tandem config schema."""
        defaults = defaults or {}
        schema: dict[Any, Any] = {}
        if include_auth:
            schema.update(
                {
                    vol.Required(CONF_EMAIL, description={"suggested_value": defaults.get(CONF_EMAIL, "")}): str,
                    vol.Required(CONF_PASSWORD, description={"suggested_value": defaults.get(CONF_PASSWORD, "")}): str,
                    vol.Required(CONF_REGION, default=defaults.get(CONF_REGION, "EU")): vol.In(REGIONS),
                }
            )
        schema[vol.Required(SCAN_INTERVAL, description={"suggested_value": defaults.get(SCAN_INTERVAL, 300)})] = (
            vol.All(vol.Coerce(int), vol.Range(min=60, max=900))
        )
        return vol.Schema(schema)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial (and only) configuration step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user_input[PLATFORM_TYPE] = PLATFORM_TANDEM
            try:
                info = await validate_tandem_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001 - surface any unexpected error to the UI
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                email = user_input.get(CONF_EMAIL, "").strip().lower()
                region = user_input.get(CONF_REGION, "EU")
                await self.async_set_unique_id(f"tandem_{email}_{region}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(step_id="user", data_schema=self._schema(user_input), errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle reauth triggered by ConfigEntryAuthFailed."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reauth credential entry."""
        errors: dict[str, str] = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if entry is None:
            return self.async_abort(reason="unknown")

        if user_input is not None:
            full_config = {**entry.data, **user_input}
            try:
                await validate_tandem_input(self.hass, full_config)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                self.hass.config_entries.async_update_entry(entry, data=full_config)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(step_id="reauth_confirm", data_schema=self._schema(dict(entry.data)), errors=errors)

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            full_config = {**entry.data, **user_input}
            try:
                await validate_tandem_input(self.hass, full_config)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(entry, data=full_config)

        defaults = user_input if user_input else dict(entry.data)
        return self.async_show_form(
            step_id="reconfigure", data_schema=self._schema(defaults, include_auth=False), errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
