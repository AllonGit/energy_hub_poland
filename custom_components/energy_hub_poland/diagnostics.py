"""Diagnostics support for Energy Hub Poland."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import EnergyHubDataCoordinator

TO_REDACT = {
    "api_key",
    "latitude",
    "longitude",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: EnergyHubDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "coordinator_data": {
            "api_connected": coordinator.api_connected,
            "last_update": (
                coordinator.last_update_time.isoformat()
                if coordinator.last_update_time
                else None
            ),
            "today_date": (
                coordinator._internal_data["today_date"].isoformat()
                if coordinator._internal_data.get("today_date")
                else None
            ),
            "tomorrow_date": (
                coordinator._internal_data["tomorrow_date"].isoformat()
                if coordinator._internal_data.get("tomorrow_date")
                else None
            ),
            "today_prices_count": (
                len(coordinator._internal_data["today"])
                if coordinator._internal_data.get("today")
                else 0
            ),
            "tomorrow_prices_count": (
                len(coordinator._internal_data["tomorrow"])
                if coordinator._internal_data.get("tomorrow")
                else 0
            ),
            "costs": coordinator.costs,
            "last_reset": coordinator.last_reset.isoformat(),
        },
    }
