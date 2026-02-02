# custom_components/energy_hub_poland/coordinator.py
import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PGEApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = f"{DOMAIN}_cache"
STORAGE_VERSION = 1


class PGEDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )
        self.api_client = PGEApiClient(async_get_clientsession(hass))
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._cache_loaded = False

        self._internal_data = {
            "today": None,
            "today_date": None,
            "tomorrow": None,
            "tomorrow_date": None,
        }

    async def _fetch_with_retries(self, fetch_date: date) -> dict[int, float] | None:
        api_query_date = fetch_date - timedelta(days=1)

        for attempt in range(10):
            _LOGGER.debug(
                "Pobieranie danych dla %s (data zapytania API: %s), próba %d",
                fetch_date,
                api_query_date,
                attempt + 1,
            )
            raw_data = await self.api_client.async_get_prices(api_query_date)
            parsed_prices = self._parse_prices(raw_data)

            if parsed_prices:
                _LOGGER.info("Pomyślnie pobrano dane dla %s", fetch_date)
                return parsed_prices

            _LOGGER.warning(
                "Nie udało się pobrać danych dla %s w próbie %d. Ponawiam za 30 sekund.",
                fetch_date,
                attempt + 1,
            )
            await asyncio.sleep(30)

        _LOGGER.error(
            "Nie udało się pobrać danych dla %s po wielu próbach.", fetch_date
        )
        return None

    async def _async_update_data(self) -> dict[str, Any]:
        ""
        if not self._cache_loaded:
            await self._load_cache()
            self._cache_loaded = True

        now = datetime.now()
        today_date = now.date()
        tomorrow_date = today_date + timedelta(days=1)

        data_updated = False

        if (
            self._internal_data["today_date"]
            and self._internal_data["today_date"] < today_date
        ):
            _LOGGER.debug(
                "Wykryto zmianę dnia. Przenoszenie danych dla %s do dnia dzisiejszego.",
                self._internal_data["tomorrow_date"],
            )
            self._internal_data = {
                "today": self._internal_data["tomorrow"],
                "today_date": self._internal_data["tomorrow_date"],
                "tomorrow": None,
                "tomorrow_date": None,
            }
            data_updated = True

        if (
            not self._internal_data["today"]
            or self._internal_data["today_date"] != today_date
        ):
            _LOGGER.info(
                "Brak danych na dziś (%s). Rozpoczynam pobieranie.", today_date
            )
            today_prices = await self._fetch_with_retries(today_date)
            if today_prices:
                self._internal_data["today"] = today_prices
                self._internal_data["today_date"] = today_date
                data_updated = True

        if (
            not self._internal_data["tomorrow"]
            or self._internal_data["tomorrow_date"] != tomorrow_date
        ):
            _LOGGER.info(
                "Brak danych na jutro (%s). Rozpoczynam pobieranie.", tomorrow_date
            )
            tomorrow_prices = await self._fetch_with_retries(tomorrow_date)
            if tomorrow_prices:
                self._internal_data["tomorrow"] = tomorrow_prices
                self._internal_data["tomorrow_date"] = tomorrow_date
                data_updated = True

        if data_updated:
            await self._save_cache()

        if not self._internal_data["today"]:
            raise UpdateFailed("Nie można było pobrać cen energii na dziś.")

        return {
            "today": self._internal_data["today"],
            "tomorrow": self._internal_data["tomorrow"],
        }

    async def _load_cache(self):
        try:
            cached = await self.store.async_load()
            if cached:
                _LOGGER.debug("Wczytano ceny z pamięci trwałej")
                self._internal_data = {
                    "today": {int(k): v for k, v in cached.get("today", {}).items()}
                    if cached.get("today")
                    else None,
                    "today_date": date.fromisoformat(cached["today_date"])
                    if cached.get("today_date")
                    else None,
                    "tomorrow": {
                        int(k): v for k, v in cached.get("tomorrow", {}).items()
                    }
                    if cached.get("tomorrow")
                    else None,
                    "tomorrow_date": date.fromisoformat(cached["tomorrow_date"])
                    if cached.get("tomorrow_date")
                    else None,
                }
        except Exception as e:
            _LOGGER.error("Błąd podczas wczytywania cache: %s", e)

    async def _save_cache(self):
        try:
            data_to_save = {
                "today": self._internal_data["today"],
                "today_date": self._internal_data["today_date"].isoformat()
                if self._internal_data["today_date"]
                else None,
                "tomorrow": self._internal_data["tomorrow"],
                "tomorrow_date": self._internal_data["tomorrow_date"].isoformat()
                if self._internal_data["tomorrow_date"]
                else None,
            }
            await self.store.async_save(data_to_save)
        except Exception as e:
            _LOGGER.error("Błąd podczas zapisywania cache: %s", e)

    def _parse_prices(self, raw_data: dict[str, Any] | None) -> dict[int, float] | None:
        if not raw_data or not isinstance(raw_data, list):
            return None

        prices: dict[int, float] = {}
        item = {}
        try:
            for item in raw_data:
                dt = datetime.strptime(item["date_time"], "%Y-%m-%d %H:%M:%S")
                price_val = 0.0
                for attr in item.get("attributes", []):
                    if attr["name"] == "price":
                        price_val = float(attr["value"])
                        break
                prices[dt.hour] = round(price_val / 1000, 4)
        except (ValueError, KeyError, TypeError) as e:
            _LOGGER.warning(
                "Błąd podczas przetwarzania rekordu ceny: %s. Rekord: %s", e, item
            )
            return None

        if len(prices) != 24:
            _LOGGER.warning(
                "Otrzymano niekompletne dane cenowe. Oczekiwano 24 rekordów, otrzymano %d.",
                len(prices),
            )
            return prices if prices else None

        return prices
