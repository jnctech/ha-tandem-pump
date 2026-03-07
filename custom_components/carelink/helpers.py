"""Helper utilities for the Carelink / Tandem integration."""

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.util import dt as dt_util

from .const import (
    DEVICE_PUMP_MANUFACTURER,
    DEVICE_PUMP_MODEL,
    DEVICE_PUMP_NAME,
    DEVICE_PUMP_SERIAL,
    DOMAIN,
    TANDEM_DATA_STALE_TIMEDELTA,
    TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP,
    TANDEM_SENSOR_KEY_SOFTWARE_VERSION,
)


def is_data_stale(coordinator_data: dict) -> bool:
    """Check whether Tandem pump data is stale.

    Compares the last CGM reading timestamp against current UTC time.
    Returns True if data is older than TANDEM_DATA_STALE_TIMEDELTA (30 min).

    All non-always-available Tandem sensors go stale together because they
    all originate from the same pump upload.
    """
    if not coordinator_data:
        return True

    last_sg_time = coordinator_data.get(TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP)
    if last_sg_time is None or last_sg_time == STATE_UNAVAILABLE:
        return True

    now = dt_util.utcnow()

    if last_sg_time.tzinfo is None:
        last_sg_time = last_sg_time.replace(tzinfo=now.tzinfo)

    return (now - last_sg_time) >= TANDEM_DATA_STALE_TIMEDELTA


def pump_device_info(coordinator) -> DeviceInfo:
    """Build a DeviceInfo object for any pump coordinator.

    Centralises the device identity so all entity types (sensor, binary_sensor,
    number) produce identical DeviceInfo from a single source of truth.
    """
    data = coordinator.data or {}
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.entry_id)},
        name=data.get(DEVICE_PUMP_NAME, "Pump"),
        manufacturer=data.get(DEVICE_PUMP_MANUFACTURER, "Tandem Diabetes Care"),
        model=data.get(DEVICE_PUMP_MODEL),
        sw_version=data.get(TANDEM_SENSOR_KEY_SOFTWARE_VERSION),
        serial_number=data.get(DEVICE_PUMP_SERIAL),
        configuration_url=coordinator.configuration_url,
    )


class PumpEntityMixin:
    """Mixin for Carelink/Tandem entities that have a coordinator + sensor_description.

    Provides device_info, name, unique_id, icon, and entity_category from a single
    shared implementation. Apply to CarelinkSensorEntity and CarelinkConnectivityEntity.
    List this mixin first in the MRO so its property definitions take priority over any
    conflicting defaults in CoordinatorEntity.
    """

    @property
    def device_info(self) -> DeviceInfo:
        """Return shared pump DeviceInfo."""
        return pump_device_info(self.coordinator)

    @property
    def name(self) -> str:
        """Return the sensor name."""
        return self.sensor_description.name

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this sensor."""
        return f"{DOMAIN.lower()}_{self.sensor_description.key}"

    @property
    def icon(self) -> str | None:
        """Return the sensor icon."""
        return self.sensor_description.icon

    @property
    def entity_category(self) -> EntityCategory | None:
        """Return the entity category."""
        return self.sensor_description.entity_category
