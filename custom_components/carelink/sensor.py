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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    COORDINATOR,
    DEVICE_PUMP_MODEL,
    DEVICE_PUMP_NAME,
    DEVICE_PUMP_SERIAL,
    DEVICE_PUMP_MANUFACTURER,
    DOMAIN,
    SENSORS,
    TANDEM_SENSORS,
    PLATFORM_TYPE,
    PLATFORM_CARELINK,
    PLATFORM_TANDEM,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up carelink sensor platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    platform_type = hass.data[DOMAIN][entry.entry_id].get(PLATFORM_TYPE, PLATFORM_CARELINK)

    _LOGGER.info("Setting up sensor platform for %s (entry: %s)", platform_type, entry.entry_id)

    # Choose the right sensor definitions based on platform
    sensor_definitions = TANDEM_SENSORS if platform_type == PLATFORM_TANDEM else SENSORS

    _LOGGER.info("Creating %d sensor entities for %s", len(sensor_definitions), platform_type)

    entities = []

    for sensor_description in sensor_definitions:

        entity_name = f"{DOMAIN} {sensor_description.name}"

        entities.append(
            # pylint: disable=too-many-function-args
            CarelinkSensorEntity(coordinator, sensor_description, entity_name)
        )

    _LOGGER.debug("Adding %d entities to Home Assistant", len(entities))
    async_add_entities(entities)
    _LOGGER.info("Sensor setup completed - %d entities added", len(entities))


class CarelinkSensorEntity(CoordinatorEntity, SensorEntity):
    """Carelink / Tandem Sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensor_description,
        entity_name,
    ):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.sensor_description = sensor_description
        self.entity_name = entity_name

    @property
    def name(self) -> str:
        return self.sensor_description.name

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN.lower()}_{self.sensor_description.key}"

    @property
    def native_value(self) -> float:
        value = self.coordinator.data.setdefault(self.sensor_description.key, None)
        if value is None:
            _LOGGER.debug(
                "Sensor %s has None value (key: %s not in coordinator.data)",
                self.sensor_description.name,
                self.sensor_description.key
            )
        return value

    @property
    def device_class(self) -> SensorDeviceClass:
        return self.sensor_description.device_class

    @property
    def native_unit_of_measurement(self) -> str:
        return self.sensor_description.native_unit_of_measurement

    @property
    def state_class(self) -> SensorStateClass:
        return self.sensor_description.state_class

    @property
    def icon(self) -> str:
        return self.sensor_description.icon

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        manufacturer = self.coordinator.data.get(
            DEVICE_PUMP_MANUFACTURER, "Medtronic"
        )
        return DeviceInfo(
            identifiers={
                # Serial numbers are unique identifiers within a specific domain
                (DOMAIN, self.coordinator.data[DEVICE_PUMP_SERIAL])
            },
            name=self.coordinator.data[DEVICE_PUMP_NAME],
            manufacturer=manufacturer,
            model=self.coordinator.data[DEVICE_PUMP_MODEL],
        )

    @property
    def entity_category(self):
        return self.sensor_description.entity_category

    @property
    def extra_state_attributes(self):
        attrKey = "{}_attributes".format(self.sensor_description.key)

        return self.coordinator.data.setdefault(attrKey, {})
