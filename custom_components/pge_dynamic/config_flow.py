"""Konfiguracja dla PGE Dynamic Energy."""
import voluptuous as vol
from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv
from .const import DOMAIN, CONF_TARIFF, CONF_MARGIN, CONF_FEE

TARIFFS = {
    "G1x (G11, G12) - 36.90 zł": 36.90,
    "C1x (C11, C12) - 49.20 zł": 49.20,
    "Inna": 0.0
}

class PGEDynamicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # Automat opłaty handlowej
            selected = user_input.get(CONF_TARIFF)
            fee = user_input.get(CONF_FEE)
            if (fee is None or fee == 0) and selected in TARIFFS:
                user_input[CONF_FEE] = TARIFFS[selected]
            
            return self.async_create_entry(title="PGE Dynamic", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_TARIFF, default="G1x (G11, G12) - 36.90 zł"): vol.In(list(TARIFFS.keys())),
                vol.Optional(CONF_MARGIN, default=0.0): cv.small_float,
                vol.Optional(CONF_FEE, default=0.0): cv.small_float,
            })
        )