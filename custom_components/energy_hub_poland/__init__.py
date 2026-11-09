import logging
from typing import Any

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change

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
    _LOGGER.debug("Ładowanie integracji Energy Hub Poland dla wpisu: %s", entry.title)

    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)

    for entity in entities:
        old_uid = entity.unique_id
        new_uid = None

        if old_uid.startswith(f"{DOMAIN}_price_"):
            tariff = old_uid.replace(f"{DOMAIN}_price_", "")
            new_uid = f"current_price_{tariff}_{entry.entry_id}"
        elif old_uid.startswith(f"{DOMAIN}_min_"):
            day = old_uid.replace(f"{DOMAIN}_min_", "")
            new_uid = f"min_price_{day}_{entry.entry_id}"
        elif old_uid.startswith(f"{DOMAIN}_max_"):
            day = old_uid.replace(f"{DOMAIN}_max_", "")
            new_uid = f"max_price_{day}_{entry.entry_id}"
        elif old_uid == f"{DOMAIN}_recommendation":
            new_uid = f"recommendation_{entry.entry_id}"
        elif old_uid.startswith(f"{DOMAIN}_cost_"):
            parts = old_uid.replace(f"{DOMAIN}_cost_", "")
            new_uid = f"cost_{parts}_{entry.entry_id}"
        elif old_uid.startswith(f"{DOMAIN}_savings_"):
            parts = old_uid.replace(f"{DOMAIN}_savings_", "")
            new_uid = f"savings_{parts}_{entry.entry_id}"
        elif old_uid == f"{DOMAIN}_api_status":
            new_uid = f"api_status_{entry.entry_id}"
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
    await coordinator._load_cache()
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    @callback
    def _handle_hourly_update(_now: Any) -> None:
        """Notify entities on the hour to update price status and current prices."""
        _LOGGER.debug("Hourly trigger: refreshing coordinator listeners")
        coordinator.async_update_listeners()

    entry.async_on_unload(
        async_track_time_change(hass, _handle_hourly_update, minute=0, second=0)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(update_listener))

    async def handle_update_prices(call: Any) -> None:
        """Handle the service call to force price update."""
        entry_id = call.data.get("entry_id", entry.entry_id)
        if entry_id == entry.entry_id:
            coordinator = hass.data[DOMAIN][entry.entry_id]
            _LOGGER.debug("Forcing price update via service call")
            await coordinator.async_request_refresh()

    async def handle_export_profile(call: Any) -> None:
        """Handle the service call to export a tariff profile."""
        entry_id = call.data.get("entry_id", entry.entry_id)
        if entry_id != entry.entry_id:
            return

        path = call.data.get("path")
        fmt = call.data.get("format")
        profile = {"data": entry.data, "options": entry.options}

        if not fmt:
            fmt = "json" if not path or path.endswith(".json") else "csv"

        from pathlib import Path

        if not path:
            path = hass.config.path(f"energy_hub_poland_profile.{fmt}")
        else:
            path = path if Path(path).is_absolute() else hass.config.path(path)

        _LOGGER.info("Exporting tariff profile for entry %s to %s", entry_id, path)

        if fmt == "csv":
            import csv

            with open(path, "w", newline="", encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["key", "value"])

                def flatten(prefix: str, value: Any) -> None:
                    if isinstance(value, dict):
                        for key, item in value.items():
                            flatten(f"{prefix}{key}.", item)
                    else:
                        writer.writerow([prefix.rstrip("."), value])

                flatten("data.", profile["data"])
                flatten("options.", profile["options"])
        else:
            import json

            with open(path, "w", encoding="utf-8") as jsonfile:
                json.dump(profile, jsonfile, indent=2, ensure_ascii=False)

    async def handle_import_profile(call: Any) -> None:
        """Handle the service call to import a tariff profile."""
        entry_id = call.data.get("entry_id", entry.entry_id)
        if entry_id != entry.entry_id:
            return

        path = call.data.get("path")
        fmt = call.data.get("format")
        if not path:
            _LOGGER.error("Profile import failed: path must be provided")
            return

        from pathlib import Path

        path = path if Path(path).is_absolute() else hass.config.path(path)
        if not fmt:
            fmt = "json" if path.endswith(".json") else "csv"

        _LOGGER.info("Importing tariff profile for entry %s from %s", entry_id, path)

        if fmt == "csv":
            import csv

            profile: dict[str, Any] = {"data": {}, "options": {}}
            with open(path, encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    key = row.get("key")
                    value = row.get("value")
                    if key is None:
                        continue
                    target = (
                        profile["data"]
                        if key.startswith("data.")
                        else profile["options"]
                    )
                    parts = key.split(".")[1:]
                    current = target
                    for part in parts[:-1]:
                        current = current.setdefault(part, {})
                    current[parts[-1]] = value
        else:
            import json

            with open(path, encoding="utf-8") as jsonfile:
                profile = json.load(jsonfile)

        data = profile.get("data") if isinstance(profile, dict) else None
        options = profile.get("options") if isinstance(profile, dict) else None
        if data is None and options is None and isinstance(profile, dict):
            options = profile

        if data or options:
            updated_data = {**entry.data, **(data or {})}
            updated_options = {**entry.options, **(options or {})}
            await hass.config_entries.async_update_entry(
                entry,
                data=updated_data,
                options=updated_options,
            )
            await hass.config_entries.async_reload(entry.entry_id)

    hass.services.async_register(
        DOMAIN, "update_prices", handle_update_prices, supports_response=False
    )
    hass.services.async_register(
        DOMAIN, "export_tariff_profile", handle_export_profile, supports_response=False
    )
    hass.services.async_register(
        DOMAIN, "import_tariff_profile", handle_import_profile, supports_response=False
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
