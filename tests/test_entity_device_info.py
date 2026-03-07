"""Tests for stable DeviceInfo using entry_id as the device identifier.

All entity types (sensor, binary_sensor, number) must produce identical
identifiers, serial_number, sw_version, and configuration_url because they
all delegate to the shared pump_device_info() helper / PumpEntityMixin.
"""

from unittest.mock import MagicMock

from custom_components.carelink.const import (
    DEVICE_PUMP_MODEL,
    DEVICE_PUMP_NAME,
    DEVICE_PUMP_SERIAL,
    DEVICE_PUMP_MANUFACTURER,
    DOMAIN,
    TANDEM_SENSOR_KEY_SOFTWARE_VERSION,
)
from custom_components.carelink.helpers import PumpEntityMixin, pump_device_info
from custom_components.carelink.sensor import CarelinkSensorEntity
from custom_components.carelink.binary_sensor import CarelinkConnectivityEntity
from custom_components.carelink.number import CartridgeFillVolumeNumber

_TEST_ENTRY_ID = "test-entry-id-abc123"
_TANDEM_URL = "https://source.tandemdiabetes.com"
_CARELINK_URL = "https://carelink.minimed.eu"


def _make_coordinator(
    data: dict,
    entry_id: str = _TEST_ENTRY_ID,
    configuration_url: str = _TANDEM_URL,
) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.entry_id = entry_id
    coordinator.configuration_url = configuration_url
    coordinator.last_update_success = True
    return coordinator


def _make_sensor(data: dict, **kwargs) -> CarelinkSensorEntity:
    coordinator = _make_coordinator(data, **kwargs)
    desc = MagicMock()
    desc.key = "test_key"
    desc.name = "Test Sensor"
    desc.icon = None
    desc.device_class = None
    desc.native_unit_of_measurement = None
    desc.state_class = None
    desc.entity_category = None
    return CarelinkSensorEntity(coordinator, desc, "test sensor")


def _make_binary_sensor(data: dict, **kwargs) -> CarelinkConnectivityEntity:
    coordinator = _make_coordinator(data, **kwargs)
    desc = MagicMock()
    desc.key = "test_key"
    desc.name = "Test Binary Sensor"
    desc.icon = None
    desc.device_class = None
    desc.entity_category = None
    return CarelinkConnectivityEntity(coordinator, desc)


def _make_number(data: dict, **kwargs) -> CartridgeFillVolumeNumber:
    coordinator = _make_coordinator(data, **kwargs)
    entity = CartridgeFillVolumeNumber(coordinator)
    entity._coordinator = coordinator
    return entity


# ── pump_device_info() helper ──────────────────────────────────────────────


class TestPumpDeviceInfoHelper:
    """pump_device_info() is the single source of truth for all entity types."""

    def test_returns_device_info_with_entry_id(self):
        """Returns DeviceInfo with (DOMAIN, entry_id) as identifier."""
        coordinator = _make_coordinator({})
        info = pump_device_info(coordinator)
        assert (DOMAIN, _TEST_ENTRY_ID) in info["identifiers"]

    def test_serial_number_from_data(self):
        """serial_number comes from DEVICE_PUMP_SERIAL in coordinator data."""
        coordinator = _make_coordinator({DEVICE_PUMP_SERIAL: "SN-HELPER"})
        info = pump_device_info(coordinator)
        assert info.get("serial_number") == "SN-HELPER"

    def test_serial_number_none_when_absent(self):
        coordinator = _make_coordinator({})
        info = pump_device_info(coordinator)
        assert info.get("serial_number") is None

    def test_sw_version_from_data(self):
        coordinator = _make_coordinator({TANDEM_SENSOR_KEY_SOFTWARE_VERSION: "8.0.0"})
        info = pump_device_info(coordinator)
        assert info.get("sw_version") == "8.0.0"

    def test_configuration_url_from_coordinator(self):
        coordinator = _make_coordinator({}, configuration_url=_TANDEM_URL)
        info = pump_device_info(coordinator)
        assert info.get("configuration_url") == _TANDEM_URL

    def test_name_fallback_is_pump(self):
        """Default name is 'Pump' when DEVICE_PUMP_NAME not in data."""
        coordinator = _make_coordinator({})
        info = pump_device_info(coordinator)
        assert info["name"] == "Pump"

    def test_name_from_data(self):
        coordinator = _make_coordinator({DEVICE_PUMP_NAME: "My t:slim X2"})
        info = pump_device_info(coordinator)
        assert info["name"] == "My t:slim X2"

    def test_coordinator_data_none_safe(self):
        """Does not crash when coordinator.data is None."""
        coordinator = _make_coordinator({})
        coordinator.data = None
        info = pump_device_info(coordinator)
        assert (DOMAIN, _TEST_ENTRY_ID) in info["identifiers"]
        assert info["name"] == "Pump"


# ── PumpEntityMixin ────────────────────────────────────────────────────────


class TestPumpEntityMixinProperties:
    """PumpEntityMixin provides name, unique_id, icon, entity_category from description."""

    def _make_mixin_instance(self, key="pump_key", name="Pump Sensor", icon="mdi:heart"):
        """Create a minimal object that satisfies PumpEntityMixin requirements."""
        obj = PumpEntityMixin()
        obj.coordinator = _make_coordinator({})
        obj.sensor_description = MagicMock()
        obj.sensor_description.key = key
        obj.sensor_description.name = name
        obj.sensor_description.icon = icon
        obj.sensor_description.entity_category = None
        return obj

    def test_name_from_sensor_description(self):
        obj = self._make_mixin_instance(name="CGM Glucose")
        assert obj.name == "CGM Glucose"

    def test_unique_id_format(self):
        obj = self._make_mixin_instance(key="last_glucose_level")
        assert obj.unique_id == f"{DOMAIN.lower()}_last_glucose_level"

    def test_icon_from_sensor_description(self):
        obj = self._make_mixin_instance(icon="mdi:water")
        assert obj.icon == "mdi:water"

    def test_entity_category_from_sensor_description(self):
        from homeassistant.helpers.entity import EntityCategory
        obj = self._make_mixin_instance()
        obj.sensor_description.entity_category = EntityCategory.DIAGNOSTIC
        assert obj.entity_category == EntityCategory.DIAGNOSTIC

    def test_device_info_delegates_to_helper(self):
        """device_info is identical to pump_device_info(coordinator)."""
        data = {DEVICE_PUMP_SERIAL: "SN-MIX", TANDEM_SENSOR_KEY_SOFTWARE_VERSION: "7.9"}
        coordinator = _make_coordinator(data)
        obj = self._make_mixin_instance()
        obj.coordinator = coordinator
        info = obj.device_info
        assert info == pump_device_info(coordinator)


# ── Sensor entity ──────────────────────────────────────────────────────────


class TestSensorDeviceInfoStableIdentifier:
    """Sensor device_info must always use entry_id as the stable identifier."""

    def test_identifier_uses_entry_id_not_serial(self):
        """Identifier is (DOMAIN, entry_id) — NOT (DOMAIN, serial_number)."""
        sensor = _make_sensor(
            {
                DEVICE_PUMP_SERIAL: "SN-12345",
                DEVICE_PUMP_NAME: "My Pump",
                DEVICE_PUMP_MODEL: "t:slim X2",
                DEVICE_PUMP_MANUFACTURER: "Tandem Diabetes Care",
            }
        )
        info = sensor.device_info
        assert (DOMAIN, _TEST_ENTRY_ID) in info["identifiers"]
        assert (DOMAIN, "SN-12345") not in info["identifiers"]

    def test_identifier_stable_when_serial_unknown(self):
        """Identifier is still entry_id even when serial is missing — no phantom device."""
        sensor = _make_sensor({})
        info = sensor.device_info
        assert (DOMAIN, _TEST_ENTRY_ID) in info["identifiers"]
        assert (DOMAIN, "unknown") not in info["identifiers"]

    def test_serial_number_returned_as_attribute(self):
        """Serial is returned as serial_number attribute for device panel display."""
        sensor = _make_sensor({DEVICE_PUMP_SERIAL: "SN-99999"})
        info = sensor.device_info
        assert info.get("serial_number") == "SN-99999"

    def test_serial_number_none_when_missing(self):
        sensor = _make_sensor({})
        info = sensor.device_info
        assert info.get("serial_number") is None

    def test_sw_version_populated_for_tandem(self):
        sensor = _make_sensor({TANDEM_SENSOR_KEY_SOFTWARE_VERSION: "7.6.1"})
        info = sensor.device_info
        assert info.get("sw_version") == "7.6.1"

    def test_sw_version_none_when_missing(self):
        sensor = _make_sensor({})
        info = sensor.device_info
        assert info.get("sw_version") is None

    def test_configuration_url_tandem(self):
        sensor = _make_sensor({}, configuration_url=_TANDEM_URL)
        info = sensor.device_info
        assert info.get("configuration_url") == _TANDEM_URL

    def test_configuration_url_carelink(self):
        sensor = _make_sensor({}, configuration_url=_CARELINK_URL)
        info = sensor.device_info
        assert info.get("configuration_url") == _CARELINK_URL

    def test_name_and_manufacturer_from_data(self):
        sensor = _make_sensor(
            {
                DEVICE_PUMP_NAME: "My t:slim X2",
                DEVICE_PUMP_MANUFACTURER: "Tandem Diabetes Care",
                DEVICE_PUMP_MODEL: "t:slim X2",
            }
        )
        info = sensor.device_info
        assert info["name"] == "My t:slim X2"
        assert info["manufacturer"] == "Tandem Diabetes Care"
        assert info["model"] == "t:slim X2"

    def test_name_fallback_when_missing(self):
        sensor = _make_sensor({})
        info = sensor.device_info
        assert info["name"] == "Pump"


# ── Binary sensor entity ───────────────────────────────────────────────────


class TestBinarySensorDeviceInfoStableIdentifier:
    """Binary sensor device_info must always use entry_id as the stable identifier."""

    def test_identifier_uses_entry_id_not_serial(self):
        bs = _make_binary_sensor(
            {
                DEVICE_PUMP_SERIAL: "SN-99999",
                DEVICE_PUMP_NAME: "My Pump",
                DEVICE_PUMP_MODEL: "t:slim X2",
                DEVICE_PUMP_MANUFACTURER: "Tandem Diabetes Care",
            }
        )
        info = bs.device_info
        assert (DOMAIN, _TEST_ENTRY_ID) in info["identifiers"]
        assert (DOMAIN, "SN-99999") not in info["identifiers"]

    def test_identifier_stable_when_serial_unknown(self):
        bs = _make_binary_sensor({})
        info = bs.device_info
        assert (DOMAIN, _TEST_ENTRY_ID) in info["identifiers"]

    def test_serial_number_and_sw_version_attributes(self):
        bs = _make_binary_sensor(
            {
                DEVICE_PUMP_SERIAL: "SN-BSTEST",
                TANDEM_SENSOR_KEY_SOFTWARE_VERSION: "7.6.2",
            }
        )
        info = bs.device_info
        assert info.get("serial_number") == "SN-BSTEST"
        assert info.get("sw_version") == "7.6.2"

    def test_configuration_url_from_coordinator(self):
        bs = _make_binary_sensor({}, configuration_url=_CARELINK_URL)
        info = bs.device_info
        assert info.get("configuration_url") == _CARELINK_URL

    def test_name_fallback(self):
        bs = _make_binary_sensor({})
        info = bs.device_info
        assert info["name"] == "Pump"


# ── Number entity ──────────────────────────────────────────────────────────


class TestNumberDeviceInfoStableIdentifier:
    """CartridgeFillVolumeNumber device_info must use entry_id as stable identifier."""

    def test_identifier_uses_entry_id_not_serial(self):
        entity = _make_number({DEVICE_PUMP_SERIAL: "SN-NUM-123"})
        info = entity.device_info
        assert (DOMAIN, _TEST_ENTRY_ID) in info["identifiers"]
        assert (DOMAIN, "SN-NUM-123") not in info["identifiers"]

    def test_identifier_stable_when_serial_missing(self):
        entity = _make_number({})
        info = entity.device_info
        assert (DOMAIN, _TEST_ENTRY_ID) in info["identifiers"]

    def test_serial_number_attribute(self):
        entity = _make_number({DEVICE_PUMP_SERIAL: "SN-NUM-456"})
        info = entity.device_info
        assert info.get("serial_number") == "SN-NUM-456"

    def test_sw_version_attribute(self):
        entity = _make_number({TANDEM_SENSOR_KEY_SOFTWARE_VERSION: "7.6.0"})
        info = entity.device_info
        assert info.get("sw_version") == "7.6.0"

    def test_configuration_url_is_tandem(self):
        entity = _make_number({})
        info = entity.device_info
        assert info.get("configuration_url") == _TANDEM_URL

    def test_default_name_when_data_empty(self):
        """Name defaults to 'Pump' when coordinator data has no pump name."""
        entity = _make_number({})
        info = entity.device_info
        assert info["name"] == "Pump"
        assert info["manufacturer"] == "Tandem Diabetes Care"

    def test_model_from_data(self):
        """Model comes from coordinator data, not a hardcoded default."""
        entity = _make_number({DEVICE_PUMP_MODEL: "t:slim X2"})
        info = entity.device_info
        assert info["model"] == "t:slim X2"


# ── Cross-entity consistency ───────────────────────────────────────────────


class TestAllEntityTypesProduceConsistentDeviceInfo:
    """All three entity types must produce identical DeviceInfo for the same coordinator.

    This is the guarantee that PumpEntityMixin + pump_device_info() provide:
    one device in HA regardless of which entity type registers first.
    """

    def _get_device_info_from_all_types(self, data: dict, entry_id: str = _TEST_ENTRY_ID):
        sensor_info = _make_sensor(data, entry_id=entry_id).device_info
        bs_info = _make_binary_sensor(data, entry_id=entry_id).device_info
        num_info = _make_number(data, entry_id=entry_id).device_info
        return sensor_info, bs_info, num_info

    def test_identifiers_identical_across_entity_types(self):
        s, b, n = self._get_device_info_from_all_types({DEVICE_PUMP_SERIAL: "SN-X"})
        assert s["identifiers"] == b["identifiers"] == n["identifiers"]

    def test_serial_number_identical_across_entity_types(self):
        s, b, n = self._get_device_info_from_all_types({DEVICE_PUMP_SERIAL: "SN-Y"})
        assert s.get("serial_number") == b.get("serial_number") == n.get("serial_number") == "SN-Y"

    def test_sw_version_identical_across_entity_types(self):
        s, b, n = self._get_device_info_from_all_types(
            {TANDEM_SENSOR_KEY_SOFTWARE_VERSION: "7.9.0"}
        )
        assert s.get("sw_version") == b.get("sw_version") == n.get("sw_version") == "7.9.0"

    def test_configuration_url_identical_across_entity_types(self):
        s, b, n = self._get_device_info_from_all_types({})
        assert (
            s.get("configuration_url")
            == b.get("configuration_url")
            == n.get("configuration_url")
            == _TANDEM_URL
        )

    def test_all_three_use_entry_id_not_serial(self):
        data = {DEVICE_PUMP_SERIAL: "REAL-SN"}
        s, b, n = self._get_device_info_from_all_types(data)
        for info in (s, b, n):
            assert (DOMAIN, _TEST_ENTRY_ID) in info["identifiers"]
            assert (DOMAIN, "REAL-SN") not in info["identifiers"]
