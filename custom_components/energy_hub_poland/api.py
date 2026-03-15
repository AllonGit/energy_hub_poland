"""API client for Energy Hub Poland."""

import logging
from datetime import date
from typing import Any

import async_timeout

from .const import API_URL

_LOGGER = logging.getLogger(__package__)


class EnergyHubApiClient:
    """API client for fetching energy prices from PSE/TGE (via PGE DataHub)."""

    def __init__(self, session: Any) -> None:
        """Initialize the API client with an aiohttp session."""
        self._session = session

    async def async_get_prices(self, for_date: date) -> list[dict[str, Any]] | None:
        """
        Fetch energy prices for a specific date.

        Note: The API usually returns prices for 'today' when queried with 'yesterday' date
        due to how TGE Fixings are published.
        """
        date_str = for_date.strftime("%Y-%m-%d")
        url = (
            f"{API_URL}?source=TGE&contract=Fix_1"
            f"&date_from={date_str} 00:00:00"
            f"&date_to={date_str} 23:59:59&limit=100"
        )

        try:
            async with async_timeout.timeout(20):
                response = await self._session.get(
                    url,
                    headers={
                        "User-Agent": "HomeAssistant/EnergyHubPoland/1.2.2 (https://github.com/AllonGit/energy_hub_poland)"
                    },
                )
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            _LOGGER.error("Error communicating with API for date %s: %s", date_str, e)
            return None
