from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
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
    BINARY_SENSORS,
    TANDEM_BINARY_SENSORS,
    PLATFORM_TYPE,
    PLATFORM_CARELINK,
    PLATFORM_TANDEM,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up carelink sensor platform."""

    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    platform_type = hass.data[DOMAIN][entry.entry_id].get(PLATFORM_TYPE, PLATFORM_CARELINK)

    # Choose the right binary sensor definitions based on platform
    sensor_definitions = TANDEM_BINARY_SENSORS if platform_type == PLATFORM_TANDEM else BINARY_SENSORS

    entities = []

    for sensor_description in sensor_definitions:

        entity_name = f"{DOMAIN} {sensor_description.name}"

        entities.append(
            # pylint: disable=too-many-function-args
            CarelinkConnectivityEntity(
                coordinator, sensor_description, entity_name)
        )

    async_add_entities(entities)


class CarelinkConnectivityEntity(CoordinatorEntity, BinarySensorEntity):
    """Carelink / Tandem Binary Sensor."""

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
    def device_class(self) -> BinarySensorDeviceClass:
        return self.sensor_description.device_class

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
    def is_on(self) -> bool:
        """Return the status of the requested attribute."""
        return self.coordinator.data.setdefault(self.sensor_description.key, None) is True

    @property
    def entity_category(self):
        return self.sensor_description.entity_category
