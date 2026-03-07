"""Support for Carelink / Tandem binary sensors."""

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
    TANDEM_SENSOR_KEY_SOFTWARE_VERSION,
    PLATFORM_TYPE,
    PLATFORM_CARELINK,
    PLATFORM_TANDEM,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up carelink binary sensor platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    platform_type = hass.data[DOMAIN][entry.entry_id].get(PLATFORM_TYPE, PLATFORM_CARELINK)

    sensor_definitions = TANDEM_BINARY_SENSORS if platform_type == PLATFORM_TANDEM else BINARY_SENSORS

    entities = [CarelinkConnectivityEntity(coordinator, desc) for desc in sensor_definitions]

    async_add_entities(entities)


class CarelinkConnectivityEntity(CoordinatorEntity, BinarySensorEntity):
    """Carelink / Tandem Binary Sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensor_description,
    ):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.sensor_description = sensor_description

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
        data = self.coordinator.data or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.entry_id)},
            name=data.get(DEVICE_PUMP_NAME, "Pump"),
            manufacturer=data.get(DEVICE_PUMP_MANUFACTURER, "Tandem Diabetes Care"),
            model=data.get(DEVICE_PUMP_MODEL),
            sw_version=data.get(TANDEM_SENSOR_KEY_SOFTWARE_VERSION),
            serial_number=data.get(DEVICE_PUMP_SERIAL),
            configuration_url=self.coordinator.configuration_url,
        )

    @property
    def is_on(self) -> bool:
        """Return the status of the requested attribute."""
        return self.coordinator.data.get(self.sensor_description.key) is True

    @property
    def entity_category(self):
        return self.sensor_description.entity_category
