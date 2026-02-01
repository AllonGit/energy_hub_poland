# custom_components/energy_hub_poland/api.py
import logging
import async_timeout
from datetime import date

from .const import API_URL

_LOGGER = logging.getLogger(__name__)

class PGEApiClient:
    

    def __init__(self, session):

        self._session = session

    async def async_get_prices(self, for_date: date):

        date_str = for_date.strftime("%Y-%m-%d")
        url = f"{API_URL}?source=TGE&contract=Fix_1&date_from={date_str} 00:00:00&date_to={date_str} 23:59:59&limit=100"
        
        try:
            async with async_timeout.timeout(20):
                response = await self._session.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            _LOGGER.error("Błąd podczas komunikacji z API PGE dla daty %s: %s", date_str, e)
            return None
