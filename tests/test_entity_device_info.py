"""Tests for device_info .get() fallback in sensor and binary_sensor (C4)."""
from unittest.mock import MagicMock

from custom_components.carelink.const import (
    DEVICE_PUMP_MODEL,
    DEVICE_PUMP_NAME,
    DEVICE_PUMP_SERIAL,
    DEVICE_PUMP_MANUFACTURER,
    DOMAIN,
)
from custom_components.carelink.sensor import CarelinkSensorEntity
from custom_components.carelink.binary_sensor import CarelinkConnectivityEntity


def _make_coordinator(data: dict) -> MagicMock:
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.last_update_success = True
    return coordinator


def _make_sensor(data: dict) -> CarelinkSensorEntity:
    coordinator = _make_coordinator(data)
    desc = MagicMock()
    desc.key = "test_key"
    desc.name = "Test Sensor"
    desc.icon = None
    desc.device_class = None
    desc.native_unit_of_measurement = None
    desc.state_class = None
    desc.entity_category = None
    return CarelinkSensorEntity(coordinator, desc, "test sensor")


def _make_binary_sensor(data: dict) -> CarelinkConnectivityEntity:
    coordinator = _make_coordinator(data)
    desc = MagicMock()
    desc.key = "test_key"
    desc.name = "Test Binary Sensor"
    desc.icon = None
    desc.device_class = None
    desc.entity_category = None
    return CarelinkConnectivityEntity(coordinator, desc)


class TestSensorDeviceInfoFallback:
    """device_info must not raise KeyError when pump identity keys are absent (C4)."""

    def test_device_info_full_data(self):
        """device_info returns full data when all keys present."""
        sensor = _make_sensor({
            DEVICE_PUMP_SERIAL: "SN-12345",
            DEVICE_PUMP_NAME: "My Pump",
            DEVICE_PUMP_MODEL: "t:slim X2",
            DEVICE_PUMP_MANUFACTURER: "Tandem Diabetes Care",
        })
        info = sensor.device_info
        assert (DOMAIN, "SN-12345") in info["identifiers"]
        assert info["name"] == "My Pump"
        assert info["model"] == "t:slim X2"
        assert info["manufacturer"] == "Tandem Diabetes Care"

    def test_device_info_missing_serial_uses_unknown(self):
        """Missing DEVICE_PUMP_SERIAL falls back to 'unknown' — no KeyError."""
        sensor = _make_sensor({
            DEVICE_PUMP_NAME: "My Pump",
            DEVICE_PUMP_MODEL: "t:slim X2",
        })
        info = sensor.device_info
        assert (DOMAIN, "unknown") in info["identifiers"]

    def test_device_info_missing_name_uses_pump(self):
        """Missing DEVICE_PUMP_NAME falls back to 'Pump' — no KeyError."""
        sensor = _make_sensor({
            DEVICE_PUMP_SERIAL: "SN-12345",
            DEVICE_PUMP_MODEL: "t:slim X2",
        })
        info = sensor.device_info
        assert info["name"] == "Pump"

    def test_device_info_missing_model_is_none(self):
        """Missing DEVICE_PUMP_MODEL returns None — no KeyError."""
        sensor = _make_sensor({
            DEVICE_PUMP_SERIAL: "SN-12345",
            DEVICE_PUMP_NAME: "My Pump",
        })
        info = sensor.device_info
        assert info.get("model") is None

    def test_device_info_empty_data(self):
        """device_info on an empty data dict uses all fallbacks without raising."""
        sensor = _make_sensor({})
        info = sensor.device_info
        assert (DOMAIN, "unknown") in info["identifiers"]
        assert info["name"] == "Pump"


class TestBinarySensorDeviceInfoFallback:
    """Same coverage for CarelinkConnectivityEntity (C4)."""

    def test_device_info_full_data(self):
        """device_info returns full data when all keys present."""
        bs = _make_binary_sensor({
            DEVICE_PUMP_SERIAL: "SN-99999",
            DEVICE_PUMP_NAME: "Carelink Pump",
            DEVICE_PUMP_MODEL: "MMT-1780",
            DEVICE_PUMP_MANUFACTURER: "Medtronic",
        })
        info = bs.device_info
        assert (DOMAIN, "SN-99999") in info["identifiers"]
        assert info["name"] == "Carelink Pump"

    def test_device_info_missing_serial_uses_unknown(self):
        """Missing serial falls back to 'unknown' — no KeyError."""
        bs = _make_binary_sensor({})
        info = bs.device_info
        assert (DOMAIN, "unknown") in info["identifiers"]

    def test_device_info_missing_name_uses_pump(self):
        """Missing name falls back to 'Pump' — no KeyError."""
        bs = _make_binary_sensor({DEVICE_PUMP_SERIAL: "SN-1"})
        info = bs.device_info
        assert info["name"] == "Pump"
