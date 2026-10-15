"""Shared entity base for the Tandem integration.

`TandemEntity` centralises device identity, naming, unique_id, and — critically —
availability. Availability is *fail-visible*: decision-input sensors (glucose,
IOB, basal) become unavailable when the pump upload is stale, so Home Assistant
never serves a stale reading as if it were current. Timestamp/diagnostic sensors
stay available so the user can always see *when* data was last received.

Safety basis: STANDARD-stable-anchor-reconciliation-2026-07-02 (relayed) — for an
insulin/glucose integration a silently-dead decision-input entity is a safety
event, not cosmetic. The pre-refactor code defeated this with a "diagnostic mode"
that bypassed the staleness check (sensor.py); this base restores the original
intent (const.py:667-674) and makes it the single source of truth.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.typing import UndefinedType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, TANDEM_IOB_MAX_AGE, TANDEM_SENSOR_KEY_ACTIVE_INSULIN
from .helpers import is_data_stale, is_iob_stale, pump_device_info
from .sensor_types import TANDEM_SENSORS_ALWAYS_AVAILABLE

if TYPE_CHECKING:
    from .coordinator import TandemCoordinator

_LOGGER = logging.getLogger(__name__)

# The coordinator centralises all polling; entity updates perform no per-entity
# device I/O, so no parallelism limit is needed.
PARALLEL_UPDATES = 0


class TandemEntity(CoordinatorEntity["TandemCoordinator"]):
    """Base entity for all Tandem platforms.

    List this class first in a platform entity's MRO so its property definitions
    take priority over CoordinatorEntity defaults, e.g.
    ``class TandemSensor(TandemEntity, SensorEntity)``.
    """

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION

    sensor_description: EntityDescription

    def __init__(self, coordinator: TandemCoordinator, sensor_description: EntityDescription) -> None:
        """Store the coordinator and the entity description."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.sensor_description = sensor_description
        self._iob_gated = False

    @property
    def device_info(self) -> DeviceInfo:
        """Return shared pump DeviceInfo (single source of truth)."""
        return pump_device_info(self.coordinator)

    @property
    def name(self) -> str | UndefinedType | None:
        """Return the entity name."""
        return self.sensor_description.name

    @property
    def unique_id(self) -> str:
        """Return a stable unique ID.

        Anchored on the config entry_id (an immutable HA UUID), never a mutable
        or externally-owned label — so the entity_id cannot silently re-derive
        (STANDARD-stable-anchor-reconciliation, relayed).
        """
        return f"{DOMAIN}_{self.coordinator.entry_id}_{self.sensor_description.key}"

    @property
    def icon(self) -> str | None:
        """Return the entity icon."""
        return self.sensor_description.icon

    @property
    def entity_category(self) -> EntityCategory | None:
        """Return the entity category."""
        return self.sensor_description.entity_category

    @property
    def available(self) -> bool:
        """Return whether the entity should report a live value.

        Timestamp/diagnostic sensors stay available so the user can see *when*
        data was last received. All other (decision-input) sensors go
        unavailable when the pump upload is stale, so HA never records a stale
        glucose/insulin value as if it were current.
        """
        if not super().available:
            return False
        if self.sensor_description.key in TANDEM_SENSORS_ALWAYS_AVAILABLE:
            return True
        if is_data_stale(self.coordinator.data):
            return False
        if self.sensor_description.key == TANDEM_SENSOR_KEY_ACTIVE_INSULIN:
            iob_stale = is_iob_stale(self.coordinator.data)
            if iob_stale and not self._iob_gated:
                _LOGGER.info(
                    "Tandem: IOB unavailable — the last pump IOB (from the last bolus) is older than %s",
                    TANDEM_IOB_MAX_AGE,
                )
            self._iob_gated = iob_stale
            return not iob_stale
        return True
