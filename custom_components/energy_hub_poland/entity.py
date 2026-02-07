"""Base entity for Energy Hub Poland."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EnergyHubDataCoordinator


class EnergyHubEntity(CoordinatorEntity):
    """Base entity for Energy Hub Poland."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Energy Hub",
            manufacturer="AllonGit",
            model="Energy Hub",
            sw_version="v1.2.0",
        )
