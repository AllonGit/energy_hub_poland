import logging
import async_timeout
from datetime import datetime, timedelta
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, API_URL, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry):
    coordinator = PGEDataCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True

class PGEDataCoordinator(DataUpdateCoordinator):
    def __init__(self, hass):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=UPDATE_INTERVAL)

    async def _async_update_data(self):
        # Generowanie URL
        now = datetime.now()
        yesterday_str = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        url = f"{API_URL}?source=TGE&contract=Fix_1&date_from={yesterday_str} 00:00:00&date_to={yesterday_str} 23:59:59&limit=100"
        
        try:
            session = async_get_clientsession(self.hass)
            async with async_timeout.timeout(20):
                response = await session.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                data = await response.json()

            prices = {}
            for item in data:
                # Parsowanie godziny
                dt = datetime.strptime(item['date_time'], "%Y-%m-%d %H:%M:%S")
                
                # Wyciąganie ceny z atrybutów
                price_val = 0
                for attr in item.get('attributes', []):
                    if attr['name'] == 'price':
                        price_val = float(attr['value'])
                        break
                
                # Konwersja MWh -> kWh
                prices[dt.hour] = price_val / 1000
            
            if not prices:
                raise UpdateFailed(f"Brak danych dla URL: {url}")

            return {"hourly": prices}
        except Exception as e:
            _LOGGER.error("Blad pobierania danych z PGE: %s", e)
            raise UpdateFailed(f"Blad API: {e}")
