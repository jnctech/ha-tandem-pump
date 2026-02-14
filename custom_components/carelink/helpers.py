"""Helper utilities for the Carelink / Tandem integration."""

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.util import dt as dt_util

from .const import TANDEM_DATA_STALE_TIMEDELTA, TANDEM_SENSOR_KEY_LASTSG_TIMESTAMP


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

    # Ensure timezone-aware comparison
    if last_sg_time.tzinfo is None:
        last_sg_time = last_sg_time.replace(tzinfo=now.tzinfo)

    return (now - last_sg_time) >= TANDEM_DATA_STALE_TIMEDELTA
