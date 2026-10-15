"""Helper utilities for the Tandem integration (staleness + device identity)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import (
    DEVICE_PUMP_MANUFACTURER,
    DEVICE_PUMP_MODEL,
    DEVICE_PUMP_SERIAL,
    DOMAIN,
    TANDEM_DATA_STALE_TIMEDELTA,
    TANDEM_IOB_MAX_AGE,
    TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP,
    TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP,
    TANDEM_SENSOR_KEY_SOFTWARE_VERSION,
)

if TYPE_CHECKING:
    from .coordinator import TandemCoordinator


def is_data_stale(coordinator_data: dict[str, Any] | None) -> bool:
    """Check whether Tandem pump data is stale.

    Compares the last CGM reading timestamp against current UTC time. Returns
    True if data is older than ``TANDEM_DATA_STALE_TIMEDELTA``. All
    non-always-available Tandem sensors go stale together because they all
    originate from the same pump upload.
    """
    if not coordinator_data:
        return True
    return _older_than(coordinator_data.get(TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP), TANDEM_DATA_STALE_TIMEDELTA)


def is_iob_stale(coordinator_data: dict[str, Any] | None) -> bool:
    """Check whether the IOB value is too old to show as current.

    IOB comes from the last bolus event and is not decayed, so its age is the
    age of that bolus. Missing timestamp counts as stale (null-not-guess).
    """
    if not coordinator_data:
        return True
    return _older_than(coordinator_data.get(TANDEM_SENSOR_KEY_LAST_BOLUS_TIMESTAMP), TANDEM_IOB_MAX_AGE)


def _older_than(ts: Any, max_age: timedelta) -> bool:
    """True if ``ts`` is not a datetime (missing/unavailable/malformed) or at least ``max_age`` old."""
    if not isinstance(ts, datetime):
        return True
    now = dt_util.utcnow()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=now.tzinfo)
    return bool((now - ts) >= max_age)


def pump_device_info(coordinator: TandemCoordinator) -> DeviceInfo:
    """Build a DeviceInfo for the pump coordinator (single source of truth)."""
    data = coordinator.data or {}
    return DeviceInfo(
        identifiers={(DOMAIN, coordinator.entry_id)},
        name="Tandem",
        manufacturer=data.get(DEVICE_PUMP_MANUFACTURER, "Tandem Diabetes Care"),
        model=data.get(DEVICE_PUMP_MODEL),
        sw_version=data.get(TANDEM_SENSOR_KEY_SOFTWARE_VERSION),
        serial_number=data.get(DEVICE_PUMP_SERIAL),
        configuration_url=coordinator.configuration_url,
    )
