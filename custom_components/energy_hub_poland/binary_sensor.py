"""Binary sensor platform for Energy Hub Poland."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from .const import CONF_OPERATION_MODE, DOMAIN, MODE_COMPARISON, MODE_DYNAMIC
from .coordinator import EnergyHubDataCoordinator
from .entity import EnergyHubEntity

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Any,
) -> None:
    """Set up the binary sensor platform."""
    coordinator: EnergyHubDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    config = {**entry.data, **entry.options}
    mode = config.get(CONF_OPERATION_MODE)
    _LOGGER.debug(
        "Setting up binary sensors for mode: %s (entry_id: %s)", mode, entry.entry_id
    )
    if mode in (MODE_DYNAMIC, MODE_COMPARISON):
        async_add_entities(
            [ApiStatusBinarySensor(coordinator, entry)], update_before_add=True
        )


class ApiStatusBinarySensor(EnergyHubEntity, BinarySensorEntity):
    """Binary sensor for API connection status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry)
        self._attr_translation_key = "api_status"
        self._attr_unique_id = f"api_status_{entry.entry_id}"

    @property
    def is_on(self) -> bool:
        """Return true if the API is connected."""
        return self.coordinator.api_connected
