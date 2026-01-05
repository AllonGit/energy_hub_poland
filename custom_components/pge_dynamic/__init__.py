import logging
import async_timeout
from datetime import datetime
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import Platform
from .const import DOMAIN, API_URL, UPDATE_INTERVAL, CONF_TARIFF

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Konfiguracja integracji po dodaniu przez interfejs."""
    coordinator = PGEDataCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

class PGEDataCoordinator(DataUpdateCoordinator):
    """Koordynator pobierający dane z PGE DataHub."""

    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)
        self.entry = entry

    async def _async_update_data(self):
        """Pobieranie danych (Logika z Twojego download_data.py przeniesiona do HA)."""
        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        
        # Budowanie URL zgodnie z Twoim url_generator.py
        url = f"{API_URL}?source=TGE&contract=Fix_1&date_from={today_str} 00:00:00&date_to={today_str} 23:59:59&limit=100"
        
        try:
            # Używamy sesji HA, aby uniknąć problemów z certyfikatami SSL
            session = async_get_clientsession(self.hass)
            
            async with async_timeout.timeout(30):
                async with session.get(url) as response:
                    if response.status != 200:
                        raise UpdateFailed(f"Błąd API PGE: {response.status}")
                    data = await response.json()

            # Logika przetwarzania
            processed = {}
            for item in data:
                try:
                    dt_str = item.get('date_time')
                    if not dt_str:
                        continue
                        
                    # Parsowanie daty
                    dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                    hour = dt.hour
                    
                    # Wyciąganie ceny
                    attributes = {attr['name']: attr['value'] for attr in item.get('attributes', [])}
                    price_mwh = float(attributes.get('price', 0))
                    
                    # Przeliczenie na kWh (dzielenie przez 1000)
                    processed[hour] = price_mwh / 1000.0
                    
                except (ValueError, KeyError) as e:
                    _LOGGER.warning("Błąd przetwarzania wpisu: %s", e)
                    continue

            if not processed:
                _LOGGER.warning("Pobrano dane, ale lista cen jest pusta.")
            
            return {"hourly": processed}

        except Exception as err:
            raise UpdateFailed(f"Błąd połączenia: {err}")