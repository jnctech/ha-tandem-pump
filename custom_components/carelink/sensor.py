"""Support for Carelink / Tandem sensors."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    COORDINATOR,
    DOMAIN,
    SENSORS,
    TANDEM_SENSORS,
    PLATFORM_TYPE,
    PLATFORM_CARELINK,
    PLATFORM_TANDEM,
)
from .helpers import PumpEntityMixin

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up carelink sensor platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    platform_type = hass.data[DOMAIN][entry.entry_id].get(PLATFORM_TYPE, PLATFORM_CARELINK)

    sensor_definitions = TANDEM_SENSORS if platform_type == PLATFORM_TANDEM else SENSORS

    entities = [CarelinkSensorEntity(coordinator, desc, platform_type) for desc in sensor_definitions]

    async_add_entities(entities)
    _LOGGER.info("Sensor setup: %d entities for %s", len(entities), platform_type)


class CarelinkSensorEntity(PumpEntityMixin, CoordinatorEntity, SensorEntity):
    """Carelink / Tandem Sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensor_description,
        platform_type=PLATFORM_CARELINK,
    ):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.sensor_description = sensor_description
        self._platform_type = platform_type

    @property
    def available(self) -> bool:
        """Return True if the coordinator is available.

        DIAGNOSTIC MODE: staleness check bypassed so sensors always show their
        last known value instead of becoming unavailable.  The coordinator logs
        [Tandem] stale_check=True/False on every update so staleness is still
        visible in the HA log without hiding data from the UI.
        """
        return super().available

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data is None:
            return None
        value = self.coordinator.data.get(self.sensor_description.key)
        if value is None:
            _LOGGER.debug(
                "Sensor %s has None value (key: %s not in coordinator.data)",
                self.sensor_description.name,
                self.sensor_description.key,
            )
        return value

    @property
    def device_class(self) -> SensorDeviceClass:
        return self.sensor_description.device_class

    @property
    def native_unit_of_measurement(self) -> str:
        return self.sensor_description.native_unit_of_measurement

    @property
    def state_class(self) -> SensorStateClass | None:
        return self.sensor_description.state_class

    @property
    def extra_state_attributes(self):
        if self.coordinator.data is None:
            return {}
        return self.coordinator.data.get(f"{self.sensor_description.key}_attributes", {})
