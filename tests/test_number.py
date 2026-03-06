"""Tests for CartridgeFillVolumeNumber entity (M1 — state restore warning)."""
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.carelink.number import CartridgeFillVolumeNumber


def _make_entity() -> CartridgeFillVolumeNumber:
    coordinator = MagicMock()
    coordinator.data = {}
    coordinator.last_update_success = True
    return CartridgeFillVolumeNumber(coordinator)


class TestCartridgeFillVolumeRestore:
    """Tests for async_added_to_hass state restore logic."""

    async def test_restore_valid_state(self):
        """Valid numeric state is restored to _attr_native_value."""
        entity = _make_entity()
        mock_state = MagicMock()
        mock_state.state = "300.0"

        with patch.object(entity, "async_get_last_state", new_callable=AsyncMock, return_value=mock_state):
            await entity.async_added_to_hass()

        assert entity._attr_native_value == 300.0

    async def test_restore_integer_state(self):
        """Integer string state is correctly cast to float."""
        entity = _make_entity()
        mock_state = MagicMock()
        mock_state.state = "250"

        with patch.object(entity, "async_get_last_state", new_callable=AsyncMock, return_value=mock_state):
            await entity.async_added_to_hass()

        assert entity._attr_native_value == 250.0

    async def test_restore_invalid_state_logs_warning(self, caplog):
        """Invalid non-numeric state logs a WARNING (M1) and leaves value as None."""
        entity = _make_entity()
        mock_state = MagicMock()
        mock_state.state = "not-a-number"

        with patch.object(entity, "async_get_last_state", new_callable=AsyncMock, return_value=mock_state):
            with caplog.at_level(logging.WARNING):
                await entity.async_added_to_hass()

        assert entity._attr_native_value is None
        assert any("not-a-number" in r.message for r in caplog.records)

    async def test_restore_unavailable_state_skipped(self):
        """State 'unavailable' is not restored (no crash, no value set)."""
        entity = _make_entity()
        mock_state = MagicMock()
        mock_state.state = "unavailable"

        with patch.object(entity, "async_get_last_state", new_callable=AsyncMock, return_value=mock_state):
            await entity.async_added_to_hass()

        assert entity._attr_native_value is None

    async def test_restore_unknown_state_skipped(self):
        """State 'unknown' is not restored (no crash, no value set)."""
        entity = _make_entity()
        mock_state = MagicMock()
        mock_state.state = "unknown"

        with patch.object(entity, "async_get_last_state", new_callable=AsyncMock, return_value=mock_state):
            await entity.async_added_to_hass()

        assert entity._attr_native_value is None

    async def test_restore_no_previous_state(self):
        """No previous state (None) is handled gracefully."""
        entity = _make_entity()

        with patch.object(entity, "async_get_last_state", new_callable=AsyncMock, return_value=None):
            await entity.async_added_to_hass()

        assert entity._attr_native_value is None

    async def test_set_native_value(self):
        """async_set_native_value updates _attr_native_value."""
        entity = _make_entity()
        entity.hass = MagicMock()
        entity.async_write_ha_state = MagicMock()

        await entity.async_set_native_value(175.0)

        assert entity._attr_native_value == 175.0
        entity.async_write_ha_state.assert_called_once()
