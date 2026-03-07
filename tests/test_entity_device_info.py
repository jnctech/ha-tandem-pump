"""Tests for stable DeviceInfo using entry_id as the device identifier."""

from unittest.mock import MagicMock

from custom_components.carelink.const import (
    DEVICE_PUMP_MODEL,
    DEVICE_PUMP_NAME,
    DEVICE_PUMP_SERIAL,
    DEVICE_PUMP_MANUFACTURER,
    DOMAIN,
    TANDEM_SENSOR_KEY_SOFTWARE_VERSION,
)
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
        """serial_number is None when DEVICE_PUMP_SERIAL not in data."""
        sensor = _make_sensor({})
        info = sensor.device_info
        assert info.get("serial_number") is None

    def test_sw_version_populated_for_tandem(self):
        """sw_version is populated from TANDEM_SENSOR_KEY_SOFTWARE_VERSION."""
        sensor = _make_sensor({TANDEM_SENSOR_KEY_SOFTWARE_VERSION: "7.6.1"})
        info = sensor.device_info
        assert info.get("sw_version") == "7.6.1"

    def test_sw_version_none_when_missing(self):
        """sw_version is None when software version not in data (e.g. Carelink)."""
        sensor = _make_sensor({})
        info = sensor.device_info
        assert info.get("sw_version") is None

    def test_configuration_url_tandem(self):
        """configuration_url points to Tandem Source for Tandem coordinator."""
        sensor = _make_sensor({}, configuration_url=_TANDEM_URL)
        info = sensor.device_info
        assert info.get("configuration_url") == _TANDEM_URL

    def test_configuration_url_carelink(self):
        """configuration_url points to Carelink for Medtronic coordinator."""
        sensor = _make_sensor({}, configuration_url=_CARELINK_URL)
        info = sensor.device_info
        assert info.get("configuration_url") == _CARELINK_URL

    def test_name_and_manufacturer_from_data(self):
        """Name and manufacturer come from coordinator data when present."""
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
        """Name falls back to 'Pump' when DEVICE_PUMP_NAME not in data."""
        sensor = _make_sensor({})
        info = sensor.device_info
        assert info["name"] == "Pump"


class TestBinarySensorDeviceInfoStableIdentifier:
    """Binary sensor device_info must always use entry_id as the stable identifier."""

    def test_identifier_uses_entry_id_not_serial(self):
        """Identifier is (DOMAIN, entry_id) — NOT (DOMAIN, serial_number)."""
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
        """Identifier is entry_id even when data dict is empty."""
        bs = _make_binary_sensor({})
        info = bs.device_info
        assert (DOMAIN, _TEST_ENTRY_ID) in info["identifiers"]

    def test_serial_number_and_sw_version_attributes(self):
        """serial_number and sw_version are present in device_info."""
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
        """configuration_url is taken from coordinator.configuration_url."""
        bs = _make_binary_sensor({}, configuration_url=_CARELINK_URL)
        info = bs.device_info
        assert info.get("configuration_url") == _CARELINK_URL

    def test_name_fallback(self):
        """Name falls back to 'Pump' when missing."""
        bs = _make_binary_sensor({})
        info = bs.device_info
        assert info["name"] == "Pump"


class TestNumberDeviceInfoStableIdentifier:
    """CartridgeFillVolumeNumber device_info must use entry_id as stable identifier."""

    def test_identifier_uses_entry_id_not_serial(self):
        """Identifier is (DOMAIN, entry_id) — NOT (DOMAIN, serial_number)."""
        entity = _make_number({DEVICE_PUMP_SERIAL: "SN-NUM-123"})
        info = entity.device_info
        assert (DOMAIN, _TEST_ENTRY_ID) in info["identifiers"]
        assert (DOMAIN, "SN-NUM-123") not in info["identifiers"]

    def test_identifier_stable_when_serial_missing(self):
        """Identifier is entry_id even when serial not loaded yet."""
        entity = _make_number({})
        info = entity.device_info
        assert (DOMAIN, _TEST_ENTRY_ID) in info["identifiers"]

    def test_serial_number_attribute(self):
        """serial_number is exposed for device panel display."""
        entity = _make_number({DEVICE_PUMP_SERIAL: "SN-NUM-456"})
        info = entity.device_info
        assert info.get("serial_number") == "SN-NUM-456"

    def test_sw_version_attribute(self):
        """sw_version is populated from coordinator data."""
        entity = _make_number({TANDEM_SENSOR_KEY_SOFTWARE_VERSION: "7.6.0"})
        info = entity.device_info
        assert info.get("sw_version") == "7.6.0"

    def test_configuration_url_is_tandem(self):
        """number.py is Tandem-only; configuration_url is always Tandem Source."""
        entity = _make_number({})
        info = entity.device_info
        assert info.get("configuration_url") == _TANDEM_URL

    def test_tandem_defaults_when_data_empty(self):
        """Tandem-specific fallbacks used when data dict is empty."""
        entity = _make_number({})
        info = entity.device_info
        assert info["name"] == "Tandem Pump"
        assert info["manufacturer"] == "Tandem Diabetes Care"
        assert info["model"] == "t:slim X2"
