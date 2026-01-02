"""Konfiguracja PGE - tylko wybór taryfy."""
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_TARIFF

# Definiujemy dostępne taryfy
TARIFFS = ["G1x", "C1x", "Inna"]

class PGEDynamicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Obsługa konfiguracji."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=f"PGE ({user_input[CONF_TARIFF]})", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_TARIFF, default="G1x"): vol.In(TARIFFS),
            })
        )