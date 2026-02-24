"""Binary sensor platform for Energy Hub Poland."""

from __future__ import annotations

import logging
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt as dt_util

from .const import (
    CONF_OPERATION_MODE,
    CONF_SPIKE_THRESHOLD,
    DOMAIN,
    MODE_DYNAMIC,
)
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

    # API Status is a diagnostic sensor available in all modes
    entities = [ApiStatusBinarySensor(coordinator, entry)]

    # Price Spike binary sensor is only available in RCE (Dynamic) mode
    if mode == MODE_DYNAMIC:
        entities.append(PriceSpikeBinarySensor(coordinator, entry))

    async_add_entities(entities, update_before_add=True)


class ApiStatusBinarySensor(EnergyHubEntity, BinarySensorEntity):
    """Binary sensor for monitoring API connection status."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the API status binary sensor."""
        super().__init__(coordinator, entry)
        self._attr_translation_key = "api_status"
        self._attr_unique_id = f"api_status_{entry.entry_id}"

    @property
    def is_on(self) -> bool:
        """Return true if the API is currently reported as connected."""
        return self.coordinator.api_connected


class PriceSpikeBinarySensor(EnergyHubEntity, BinarySensorEntity):
    """Binary sensor that turns ON when current price is significantly above average."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the price spike binary sensor."""
        super().__init__(coordinator, entry)
        self._attr_translation_key = "price_spike"
        self._attr_unique_id = f"price_spike_{entry.entry_id}"
        self._config = {**entry.data, **entry.options}

    @property
    def is_on(self) -> bool:
        """Determine if current price exceeds average by configured threshold."""
        if not self.coordinator.data:
            return False

        today_avg = self.coordinator.data.get("today_avg")
        now = dt_util.now()
        poland_tz = ZoneInfo("Europe/Warsaw")
        poland_now = now.astimezone(poland_tz)

        current_price = self.coordinator.data.get("today", {}).get(poland_now.hour)

        # Guard against missing data or zero average
        if today_avg is None or current_price is None or today_avg == 0:
            return False

        # Default threshold is 30% above average
        threshold = self._config.get(CONF_SPIKE_THRESHOLD, 30)
        return current_price > today_avg * (1 + threshold / 100)
