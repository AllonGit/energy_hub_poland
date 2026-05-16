"""API client for Energy Hub Poland."""

import asyncio
import logging
from datetime import date
from typing import Any

import async_timeout

from .const import API_URL, PSE_API_URL

_LOGGER = logging.getLogger(__package__)


class PSEApiClient:
    """API client from PSE."""

    def __init__(self, session: Any) -> None:
        """Initialize the API client."""
        self._session = session
        self._headers = {
            "Accept": "application/json",
            "User-Agent": "HomeAssistant-EnergyHub-Client",
        }
        self._last_response_schema: str | None = None

    async def _async_get_data(
        self, endpoint: str, select_fields: str, for_date: date
    ) -> list[dict[str, Any]] | None:
        """Fetch generic data from PSE API with retry logic."""
        date_str = for_date.strftime("%Y-%m-%d")
        url = f"{PSE_API_URL}/{endpoint}"
        params = {
            "$select": select_fields,
            "$filter": f"business_date ge '{date_str}'",
        }

        for attempt in range(3):  # Retry up to 3 times
            try:
                async with async_timeout.timeout(15):
                    response = await self._session.get(
                        url, params=params, headers=self._headers
                    )
                    response.raise_for_status()
                    data = await response.json()
                    result = data.get("value", [])

                    # API behavior monitoring
                    if result:
                        current_schema = self._get_schema(result[0])
                        if self._last_response_schema != current_schema:
                            _LOGGER.info(
                                "API schema changed for %s: %s",
                                endpoint,
                                current_schema,
                            )
                            self._last_response_schema = current_schema

                    return result
            except Exception as e:
                if attempt < 2:  # Don't log on last attempt
                    _LOGGER.warning(
                        "Attempt %d failed for %s on %s: %s. Retrying...",
                        attempt + 1,
                        endpoint,
                        date_str,
                        e,
                    )
                    await asyncio.sleep(1)  # Wait 1 second before retry
                else:
                    _LOGGER.error(
                        "Error fetching %s from PSE for %s after 3 attempts: %s",
                        endpoint,
                        date_str,
                        e,
                    )
                    return None

    def _get_schema(self, record: dict[str, Any]) -> str:
        """Get a string representation of the record schema."""
        return ",".join(sorted(record.keys()))

    async def get_rce_prices(self, for_date: date) -> list[dict[str, Any]] | None:
        """Fetch RCE prices."""
        return await self._async_get_data(
            "rce-pln", "business_date,dtime,rce_pln", for_date
        )

    async def get_rce_forecast(self, for_date: date) -> list[dict[str, Any]] | None:
        """Fetch RCE price forecast."""
        return await self._async_get_data(
            "price-fcst", "business_date,dtime,cen_fcst,imb_energy", for_date
        )

    async def get_peak_hours(self, for_date: date) -> list[dict[str, Any]] | None:
        """Fetch peak hours."""
        return await self._async_get_data(
            "pdgsz", "business_date,dtime,usage_fcst,is_active", for_date
        )

    async def get_load_data(self, for_date: date) -> list[dict[str, Any]] | None:
        """Fetch KSE load data."""
        return await self._async_get_data(
            "kse-load", "business_date,dtime,load_actual,load_fcst", for_date
        )

    async def get_generation_plans(self, for_date: date) -> list[dict[str, Any]] | None:
        """Fetch PV and Wind generation plans."""
        return await self._async_get_data(
            "pdgobpkd", "business_date,dtime,gen_wi,gen_fv,kse_pow_dem", for_date
        )


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
            f"{API_URL}?source=TGE&contract=Fix_2"
            f"&date_from={date_str} 00:00:00"
            f"&date_to={date_str} 23:59:59&limit=100"
        )

        try:
            async with async_timeout.timeout(20):
                response = await self._session.get(
                    url,
                    headers={"User-Agent": "HomeAssistant/EnergyHubPoland"},
                )
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            _LOGGER.error("Error communicating with API for date %s: %s", date_str, e)
            return None
