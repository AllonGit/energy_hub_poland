# custom_components/energy_hub/coordinator.py
"""Koordynator danych dla integracji Energy Hub."""
import asyncio
import logging
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PGEApiClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class PGEDataCoordinator(DataUpdateCoordinator):
    """Zarządza pobieraniem i przetwarzaniem danych z API PGE."""

    def __init__(self, hass):
        """Inicjalizacja koordynatora."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
        )
        self.api_client = PGEApiClient(async_get_clientsession(hass))
        self._first_refresh_done = False

    async def _fetch_with_retries(self, fetch_date: date, quick_try: bool = False) -> Optional[Dict[int, float]]:
        """Pobiera dane dla określonej daty z mechanizmem ponowień."""
        api_query_date = fetch_date - timedelta(days=1)
        max_attempts = 1 if quick_try else 10
        
        for attempt in range(max_attempts):
            _LOGGER.debug(
                "Pobieranie danych dla %s (API: %s), próba %d/%d",
                fetch_date, api_query_date, attempt + 1, max_attempts
            )
            raw_data = await self.api_client.async_get_prices(api_query_date)
            parsed_prices = self._parse_prices(raw_data)
            
            if parsed_prices:
                _LOGGER.info("Pomyślnie pobrano dane dla %s", fetch_date)
                return parsed_prices
            
            if not quick_try:
                _LOGGER.debug("Nie udało się pobrać danych dla %s. Ponawiam za 30s.", fetch_date)
                await asyncio.sleep(30)
        
        if not quick_try:
            _LOGGER.error("Nie udało się pobrać danych dla %s po %d próbach.", fetch_date, max_attempts)
        return None

    async def _async_update_data(self) -> Dict[str, Any]:
        """Główna metoda pobierania i przetwarzania danych zgodnie z harmonogramem."""
        is_first_refresh = not self._first_refresh_done
        now = datetime.now()
        today_date = now.date()
        tomorrow_date = today_date + timedelta(days=1)

        current_data = self.data if self.data else {}
        
        if current_data.get("today_date") and current_data["today_date"] < today_date:
            current_data = {
                "today": current_data.get("tomorrow"),
                "today_date": current_data.get("tomorrow_date"),
                "tomorrow": None, "tomorrow_date": None
            }

        if not current_data.get("today") or current_data.get("today_date") != today_date:
            today_prices = await self._fetch_with_retries(today_date, quick_try=is_first_refresh)
            if today_prices:
                current_data["today"] = today_prices
                current_data["today_date"] = today_date
        
        if not current_data.get("tomorrow") or current_data.get("tomorrow_date") != tomorrow_date:
            tomorrow_prices = await self._fetch_with_retries(tomorrow_date, quick_try=is_first_refresh)
            if tomorrow_prices:
                current_data["tomorrow"] = tomorrow_prices
                current_data["tomorrow_date"] = tomorrow_date

        if not current_data.get("today"):
            raise UpdateFailed("Nie udało się pobrać cen energii na dziś. Spróbuj ponownie za chwilę.")
        
        self._first_refresh_done = True
        return {
            "today": current_data.get("today"),
            "tomorrow": current_data.get("tomorrow")
        }

    def _parse_prices(self, raw_data: Optional[Dict[str, Any]]) -> Optional[Dict[int, float]]:
        """Przetwarza surowe dane z API na słownik cen godzinowych."""
        if not raw_data or not isinstance(raw_data, list):
            return None
            
        prices: Dict[int, float] = {}
        item = {}
        try:
            for item in raw_data:
                dt = datetime.strptime(item['date_time'], "%Y-%m-%d %H:%M:%S")
                price_val = 0.0
                for attr in item.get('attributes', []):
                    if attr['name'] == 'price':
                        price_val = float(attr['value'])
                        break
                prices[dt.hour] = round(price_val / 1000, 4)
        except (ValueError, KeyError, TypeError) as e:
            _LOGGER.warning("Błąd podczas przetwarzania rekordu ceny: %s. Rekord: %s", e, item)
            return None

        if len(prices) != 24:
            _LOGGER.warning(
                "Otrzymano niekompletne dane cenowe. Oczekiwano 24 rekordów, otrzymano %d.",
                len(prices)
            )
            return prices if prices else None
            
        return prices
