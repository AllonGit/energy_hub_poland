"""Data coordinator for Energy Hub Poland."""

import logging
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EnergyHubApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__package__)

STORAGE_KEY = f"{DOMAIN}_cache"
STORAGE_VERSION = 1


class EnergyHubDataCoordinator(DataUpdateCoordinator):
    """
    Class to manage fetching Energy Hub data from PSE/TGE API.
    Handles data caching, day transitions, and basic statistics calculation.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )
        self.api_client = EnergyHubApiClient(async_get_clientsession(hass))
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._cache_loaded = False

        self._internal_data: dict[str, Any] = {
            "today": None,
            "today_date": None,
            "tomorrow": None,
            "tomorrow_date": None,
        }
        self.last_update_time: datetime | None = None
        self.api_connected: bool = True

    async def _fetch_data(self, fetch_date: date) -> dict[int, float] | None:
        """Fetch and parse price data for a specific date."""
        # Fix_1 prices for 'fetch_date' are published on the previous day.
        api_query_date = fetch_date - timedelta(days=1)
        _LOGGER.debug(
            "Fetching prices for %s (API query date: %s)", fetch_date, api_query_date
        )

        raw_data = await self.api_client.async_get_prices(api_query_date)
        parsed_prices = self._parse_prices(raw_data)

        if parsed_prices:
            self.last_update_time = dt_util.utcnow()
            return parsed_prices

        return None

    async def _async_update_data(self) -> dict[str, Any]:
        """Core update method called periodically by Home Assistant."""
        if not self._cache_loaded:
            await self._load_cache()
            self._cache_loaded = True

        now = dt_util.now()
        today_date = now.date()
        tomorrow_date = today_date + timedelta(days=1)

        data_updated = False

        # Handle day transition (midnight)
        if (
            self._internal_data["today_date"]
            and self._internal_data["today_date"] < today_date
        ):
            _LOGGER.debug("Day transition: moving tomorrow data to today")
            self._internal_data["today"] = self._internal_data["tomorrow"]
            self._internal_data["today_date"] = self._internal_data["tomorrow_date"]
            self._internal_data["tomorrow"] = None
            self._internal_data["tomorrow_date"] = None
            data_updated = True

        # Fetch today's data if missing or date mismatch
        if (
            not self._internal_data["today"]
            or self._internal_data["today_date"] != today_date
        ):
            today_prices = await self._fetch_data(today_date)
            if today_prices:
                self._internal_data["today"] = today_prices
                self._internal_data["today_date"] = today_date
                self.api_connected = True
                data_updated = True
            else:
                _LOGGER.warning("Failed to fetch today's prices (%s)", today_date)
                # Mark as disconnected only if we have no valid data to show
                if not self._internal_data["today"]:
                    self.api_connected = False

        # Fetch tomorrow's data if missing or date mismatch
        if (
            not self._internal_data["tomorrow"]
            or self._internal_data["tomorrow_date"] != tomorrow_date
        ):
            tomorrow_prices = await self._fetch_data(tomorrow_date)
            if tomorrow_prices:
                self._internal_data["tomorrow"] = tomorrow_prices
                self._internal_data["tomorrow_date"] = tomorrow_date
                data_updated = True
            else:
                _LOGGER.debug("Tomorrow's prices (%s) not yet available", tomorrow_date)

        if data_updated:
            await self._save_cache()

        # Raise error only if we have no data at all for today
        if not self._internal_data["today"]:
            raise UpdateFailed("No energy price data available for today")

        data = {
            "today": self._internal_data["today"],
            "tomorrow": self._internal_data["tomorrow"],
        }

        # Calculate daily statistics (Averages and Mins)
        for day in ["today", "tomorrow"]:
            prices = data.get(day)
            if prices:
                # Average Price Calculation
                avg = sum(prices.values()) / len(prices)
                data[f"{day}_avg"] = round(avg, 4)

                # Identify the hour with the lowest price
                min_price = min(prices.values())
                min_hours = [h for h, p in prices.items() if p == min_price]
                data[f"{day}_min_hour"] = min_hours[0] if min_hours else None

        return data

    async def _load_cache(self) -> None:
        """Load previously saved prices from the persistent store."""
        try:
            cached = await self.store.async_load()
            if cached:
                _LOGGER.debug("Loaded prices from persistent cache")
                self._internal_data = {
                    "today": (
                        {int(k): v for k, v in cached.get("today", {}).items()}
                        if cached.get("today")
                        else None
                    ),
                    "today_date": (
                        date.fromisoformat(cached["today_date"])
                        if cached.get("today_date")
                        else None
                    ),
                    "tomorrow": (
                        {int(k): v for k, v in cached.get("tomorrow", {}).items()}
                        if cached.get("tomorrow")
                        else None
                    ),
                    "tomorrow_date": (
                        date.fromisoformat(cached["tomorrow_date"])
                        if cached.get("tomorrow_date")
                        else None
                    ),
                }
                if last_update := cached.get("last_update_time"):
                    self.last_update_time = dt_util.parse_datetime(last_update)
                self.api_connected = cached.get("api_connected", True)
                # Populate self.data immediately for faster integration startup
                self.data = {
                    "today": self._internal_data["today"],
                    "tomorrow": self._internal_data["tomorrow"],
                }
        except Exception as e:
            _LOGGER.error("Error loading cache: %s", e)

    async def _save_cache(self) -> None:
        """Save current data to the persistent store."""
        try:
            today_date: date | None = self._internal_data["today_date"]
            tomorrow_date: date | None = self._internal_data["tomorrow_date"]
            data_to_save = {
                "today": self._internal_data["today"],
                "today_date": today_date.isoformat() if today_date else None,
                "tomorrow": self._internal_data["tomorrow"],
                "tomorrow_date": tomorrow_date.isoformat() if tomorrow_date else None,
                "last_update_time": (
                    self.last_update_time.isoformat() if self.last_update_time else None
                ),
                "api_connected": self.api_connected,
            }
            await self.store.async_save(data_to_save)
        except Exception as e:
            _LOGGER.error("Error saving cache: %s", e)

    def _parse_prices(
        self, raw_data: list[dict[str, Any]] | None
    ) -> dict[int, float] | None:
        """Parse raw JSON response from PGE DataHub API into hour -> price mapping."""
        if not raw_data or not isinstance(raw_data, list):
            return None

        prices: dict[int, float] = {}
        poland_tz = ZoneInfo("Europe/Warsaw")
        item = {}
        try:
            for item in raw_data:
                # API returns timestamps in UTC. We convert them to Polish local time
                # to correctly map prices to Polish hour intervals (0-23).
                dt = dt_util.parse_datetime(item["date_time"])
                if dt is None:
                    continue

                # Assume UTC if no timezone info is present
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=dt_util.UTC)

                # Convert to Polish time
                poland_dt = dt.astimezone(poland_tz)
                hour = poland_dt.hour

                price_val = 0.0
                for attr in item.get("attributes", []):
                    if attr["name"] == "price":
                        price_val = float(attr["value"])
                        break

                prices[hour] = round(price_val / 1000, 4)  # Convert PLN/MWh to PLN/kWh
        except (ValueError, KeyError, TypeError) as e:
            _LOGGER.warning("Error processing price record: %s. Record: %s", e, item)
            return None

        if len(prices) != 24:
            _LOGGER.warning(
                "Received incomplete price data. Expected 24 records, got %d.",
                len(prices),
            )
            return prices if prices else None

        return prices
