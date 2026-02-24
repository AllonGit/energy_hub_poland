# custom_components/energy_hub_poland/__init__.py
import logging
from typing import Any

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import EnergyHubDataCoordinator

_LOGGER = logging.getLogger(__package__)
PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Energy Hub component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Energy Hub from a config entry."""
    _LOGGER.info("Ładowanie integracji Energy Hub Poland dla wpisu: %s", entry.title)

    # Migrate unique IDs if necessary
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)

    for entity in entities:
        old_uid = entity.unique_id
        new_uid = None

        # Price sensors: energy_hub_poland_price_dynamic -> current_price_dynamic_{entry_id}
        if old_uid.startswith(f"{DOMAIN}_price_"):
            tariff = old_uid.replace(f"{DOMAIN}_price_", "")
            new_uid = f"current_price_{tariff}_{entry.entry_id}"

        # MinMax sensors: energy_hub_poland_min_today -> min_price_today_{entry_id}
        elif old_uid.startswith(f"{DOMAIN}_min_"):
            day = old_uid.replace(f"{DOMAIN}_min_", "")
            new_uid = f"min_price_{day}_{entry.entry_id}"
        elif old_uid.startswith(f"{DOMAIN}_max_"):
            day = old_uid.replace(f"{DOMAIN}_max_", "")
            new_uid = f"max_price_{day}_{entry.entry_id}"

        # Recommendation: energy_hub_poland_recommendation -> recommendation_{entry_id}
        elif old_uid == f"{DOMAIN}_recommendation":
            new_uid = f"recommendation_{entry.entry_id}"

        # Cost: energy_hub_poland_cost_dynamic_daily -> cost_dynamic_daily_{entry_id}
        elif old_uid.startswith(f"{DOMAIN}_cost_"):
            parts = old_uid.replace(f"{DOMAIN}_cost_", "")
            new_uid = f"cost_{parts}_{entry.entry_id}"

        # Savings: energy_hub_poland_savings_... -> savings_..._{entry_id}
        elif old_uid.startswith(f"{DOMAIN}_savings_"):
            parts = old_uid.replace(f"{DOMAIN}_savings_", "")
            new_uid = f"savings_{parts}_{entry.entry_id}"

        # API Status: energy_hub_poland_api_status -> api_status_{entry_id}
        elif old_uid == f"{DOMAIN}_api_status":
            new_uid = f"api_status_{entry.entry_id}"

        # Last Update: energy_hub_poland_last_update -> last_update_{entry_id}
        elif old_uid == f"{DOMAIN}_last_update":
            new_uid = f"last_update_{entry.entry_id}"

        if new_uid and new_uid != old_uid:
            if registry.async_get_entity_id(entity.domain, DOMAIN, new_uid):
                _LOGGER.info(
                    "New unique ID %s already exists, removing old entity %s",
                    new_uid,
                    entity.entity_id,
                )
                registry.async_remove(entity.entity_id)
            else:
                _LOGGER.info("Migrating unique ID from %s to %s", old_uid, new_uid)
                registry.async_update_entity(entity.entity_id, new_unique_id=new_uid)

    coordinator = EnergyHubDataCoordinator(hass)
    # Load cache immediately to avoid setup timeouts and provide data to sensors fast
    await coordinator._load_cache()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
