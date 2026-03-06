"""Number entity for user-configurable cartridge fill volume."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    COORDINATOR,
    DEVICE_PUMP_MODEL,
    DEVICE_PUMP_NAME,
    DEVICE_PUMP_SERIAL,
    DEVICE_PUMP_MANUFACTURER,
    DOMAIN,
    PLATFORM_TYPE,
    PLATFORM_TANDEM,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform."""
    platform_type = hass.data[DOMAIN][entry.entry_id].get(PLATFORM_TYPE)
    if platform_type != PLATFORM_TANDEM:
        return

    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    async_add_entities([CartridgeFillVolumeNumber(coordinator)])


class CartridgeFillVolumeNumber(RestoreEntity, NumberEntity):
    """Number entity for the insulin cartridge fill volume.

    The Tandem API does not report the actual cartridge fill volume,
    so this entity allows the user to set the amount when they change
    their cartridge. The integration uses this value to estimate
    remaining insulin by subtracting cumulative usage.
    """

    _attr_name = "Cartridge fill volume"
    _attr_unique_id = f"{DOMAIN}_cartridge_fill_volume"
    _attr_icon = "mdi:cup-water"
    _attr_native_min_value = 0
    _attr_native_max_value = 300
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "units"
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator: DataUpdateCoordinator) -> None:
        """Initialize the number entity."""
        self._coordinator = coordinator
        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Restore previous value on startup."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_native_value = float(last_state.state)
            except (ValueError, TypeError) as err:
                _LOGGER.warning(
                    "Carelink: Could not restore cartridge fill volume from state %r: %s",
                    last_state.state,
                    err,
                )

    async def async_set_native_value(self, value: float) -> None:
        """Set the cartridge fill volume."""
        self._attr_native_value = value
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._coordinator.data.get(DEVICE_PUMP_SERIAL, "unknown"))},
            name=self._coordinator.data.get(DEVICE_PUMP_NAME, "Tandem Pump"),
            manufacturer=self._coordinator.data.get(DEVICE_PUMP_MANUFACTURER, "Tandem Diabetes Care"),
            model=self._coordinator.data.get(DEVICE_PUMP_MODEL, "t:slim X2"),
        )
