"""Inicjalizacja integracji PGE Dynamic Energy (DataHub)."""
import logging
import async_timeout
import aiohttp
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.const import Platform

from .const import DOMAIN, API_URL, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Ustawienie wpisu konfiguracyjnego."""
    coordinator = PGEDataCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Odładowanie wpisu."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

class PGEDataCoordinator(DataUpdateCoordinator):
    """Koordynator pobierający dane z PGE DataHub."""

    def __init__(self, hass, entry):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.entry = entry

    async def _async_update_data(self):
        """Pobierz dane z API PGE DataHub (odpowiednik Twojego kodu JS)."""
        
        # 1. Logika daty (JS: const now = new Date()...)
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d") # Format YYYY-MM-DD
        
        # 2. Budowanie parametrów URL (zgodnie z Twoim wzorem)
        # URL: ...?source=TGE&contract=Fix_1&date_from=...&date_to=...
        params = {
            "source": "TGE",
            "contract": "Fix_1",
            "date_from": f"{today_str} 00:00:00",
            "date_to": f"{today_str} 23:59:59",
            "limit": "100"
        }

        try:
            async with async_timeout.timeout(20):
                async with aiohttp.ClientSession() as session:
                    async with session.get(API_URL, params=params) as response:
                        if response.status != 200:
                            raise UpdateFailed(f"Błąd PGE DataHub: {response.status}")
                        
                        data = await response.json()
                        # PGE DataHub zazwyczaj zwraca listę obiektów w polu 'quotes' lub bezpośrednio listę
                        # Zabezpieczamy się na oba przypadki
                        results = data.get("quotes", data) if isinstance(data, dict) else data

            if not results or not isinstance(results, list):
                _LOGGER.warning("PGE DataHub zwrócił pustą listę lub błędny format.")
                return {}

            # 3. Parsowanie danych (Mapowanie godziny na cenę)
            prices = {}
            prices_list = []

            for item in results:
                # Przykład itemu: {"date": "2024-05-20 00:00:00", "price": 450.50, ...}
                date_str = item.get("date")
                price_val = item.get("price")

                if date_str and price_val is not None:
                    # Wyciągamy godzinę z daty "YYYY-MM-DD HH:MM:SS"
                    try:
                        dt_obj = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                        hour = dt_obj.hour
                        
                        # Przeliczamy na float (dla pewności) i zamieniamy MWh -> kWh
                        # Fix_1 zazwyczaj jest w PLN/MWh
                        price_kwh = float(price_val) / 1000.0
                        
                        prices[hour] = price_kwh
                        prices_list.append(price_kwh)
                    except ValueError:
                        continue

            return {
                "hourly": prices,
                "min": min(prices_list) if prices_list else 0,
                "max": max(prices_list) if prices_list else 0,
                "raw": results
            }

        except Exception as err:
            raise UpdateFailed(f"Błąd połączenia z PGE: {err}")