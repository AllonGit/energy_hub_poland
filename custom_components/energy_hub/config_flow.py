# custom_components/energy_hub/config_flow.py
"""Przepływ konfiguracji dla integracji Energy Hub."""
import voluptuous as vol
import re
from typing import Any, Dict, Optional

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector, SelectSelectorConfig, SelectSelectorMode,
    EntitySelector, EntitySelectorConfig
)
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONF_OPERATION_MODE, CONF_ENERGY_SENSOR, CONF_SENSOR_TYPE,
    CONF_G12_SETTINGS, CONF_G12W_SETTINGS,
    CONF_PRICE_PEAK, CONF_PRICE_OFFPEAK, CONF_HOURS_PEAK,
    MODE_DYNAMIC, MODE_G12, MODE_G12W, MODE_COMPARISON,
    SENSOR_TYPE_TOTAL_INCREASING, SENSOR_TYPE_DAILY,
    DEFAULT_G12_PEAK_HOURS, DEFAULT_G12W_PEAK_HOURS
)

def validate_hour_format(user_input: str) -> bool:
    """Sprawdza poprawność formatu godzin (np. '6-13,15-22')."""
    if not user_input:
        return True
    pattern = re.compile(r"^\d{1,2}-\d{1,2}(,\d{1,2}-\d{1,2})*$")
    return pattern.match(user_input) is not None

class PGEDynamicConfigFlow(config_entries.ConfigFlow, domain=DOMAIN): # type: ignore[call-arg]
    """Obsługuje przepływ konfiguracji dla Energy Hub."""
    VERSION = 1

    def __init__(self):
        """Inicjalizacja przepływu."""
        self.config_data: Dict[str, Any] = {}

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Krok 1: Wybór trybu pracy."""
        if user_input is not None:
            self.config_data.update(user_input)
            mode = user_input[CONF_OPERATION_MODE]

            if mode == MODE_G12:
                return await self.async_step_g12_config()
            if mode == MODE_G12W:
                return await self.async_step_g12w_config()
            if mode == MODE_COMPARISON:
                return await self.async_step_g12_config()
            
            return await self.async_step_energy_sensor()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_OPERATION_MODE, default=MODE_DYNAMIC): SelectSelector(
                    SelectSelectorConfig(
                        options=[MODE_DYNAMIC, MODE_G12, MODE_G12W, MODE_COMPARISON],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="operation_mode"
                    )
                ),
            })
        )

    async def async_step_g12_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Krok konfiguracji taryfy G12."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            if not validate_hour_format(user_input[CONF_HOURS_PEAK]):
                errors["base"] = "invalid_hour_range"
            else:
                self.config_data[CONF_G12_SETTINGS] = user_input
                if self.config_data[CONF_OPERATION_MODE] in [MODE_G12W, MODE_COMPARISON]:
                     return await self.async_step_g12w_config()
                return await self.async_step_energy_sensor()

        return self.async_show_form(
            step_id="g12_config",
            data_schema=vol.Schema({
                vol.Required(CONF_PRICE_PEAK, default=0.80): vol.Coerce(float),
                vol.Required(CONF_PRICE_OFFPEAK, default=0.50): vol.Coerce(float),
                vol.Required(CONF_HOURS_PEAK, default=DEFAULT_G12_PEAK_HOURS): str,
            }),
            errors=errors
        )

    async def async_step_g12w_config(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Krok konfiguracji taryfy G12w."""
        errors: Dict[str, str] = {}
        if user_input is not None:
            if not validate_hour_format(user_input[CONF_HOURS_PEAK]):
                errors["base"] = "invalid_hour_range"
            else:
                self.config_data[CONF_G12W_SETTINGS] = user_input
                return await self.async_step_energy_sensor()
        
        return self.async_show_form(
            step_id="g12w_config",
            data_schema=vol.Schema({
                vol.Required(CONF_PRICE_PEAK, default=0.85): vol.Coerce(float),
                vol.Required(CONF_PRICE_OFFPEAK, default=0.55): vol.Coerce(float),
                vol.Required(CONF_HOURS_PEAK, default=DEFAULT_G12W_PEAK_HOURS): str,
            }),
            errors=errors
        )
        
    async def async_step_energy_sensor(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Krok konfiguracji sensora zużycia energii (opcjonalny)."""
        if user_input is not None:
            self.config_data.update(user_input)
            
            title_map = {
                MODE_DYNAMIC: "Energy Hub Dynamic",
                MODE_G12: "Energy Hub G12",
                MODE_G12W: "Energy Hub G12w",
                MODE_COMPARISON: "Energy Hub Comparison"
            }
            mode = self.config_data.get(CONF_OPERATION_MODE)
            title = title_map.get(mode, "Energy Hub") if mode else "Energy Hub"

            return self.async_create_entry(title=title, data=self.config_data)

        schema = {
            vol.Optional(CONF_ENERGY_SENSOR): EntitySelector(EntitySelectorConfig(domain="sensor")),
            vol.Optional(CONF_SENSOR_TYPE, default=SENSOR_TYPE_TOTAL_INCREASING): SelectSelector(
                SelectSelectorConfig(
                    options=[SENSOR_TYPE_TOTAL_INCREASING, SENSOR_TYPE_DAILY],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="sensor_type"
                )
            ),
        }
        
        # W trybach G12/G12w/Porównawczym, jeśli jest sensor energii, typ jest wymagany
        if self.config_data.get(CONF_OPERATION_MODE) != MODE_DYNAMIC:
             schema[vol.Required(CONF_SENSOR_TYPE, default=SENSOR_TYPE_TOTAL_INCREASING)] = schema.pop(vol.Optional(CONF_SENSOR_TYPE, default=SENSOR_TYPE_TOTAL_INCREASING))


        return self.async_show_form(
            step_id="energy_sensor",
            data_schema=vol.Schema(schema)
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Zwraca przepływ opcji dla tej integracji."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Obsługuje przepływ opcji dla Energy Hub."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Inicjalizacja przepływu opcji."""
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Zarządza opcjami."""
        if self.config_entry.data.get(CONF_OPERATION_MODE) == MODE_DYNAMIC and not self.config_entry.data.get(CONF_ENERGY_SENSOR):
            return self.async_abort(reason="no_options")
            
        return await self.async_step_reconfigure()

    async def async_step_reconfigure(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """Główny krok rekonfiguracji."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            if self.config_entry.data.get(CONF_OPERATION_MODE) in [MODE_G12, MODE_COMPARISON]:
                 if not validate_hour_format(user_input[f"{CONF_G12_SETTINGS}_{CONF_HOURS_PEAK}"]):
                    errors["base"] = "invalid_g12_hour_range"

            if self.config_entry.data.get(CONF_OPERATION_MODE) in [MODE_G12W, MODE_COMPARISON]:
                 if not validate_hour_format(user_input[f"{CONF_G12W_SETTINGS}_{CONF_HOURS_PEAK}"]):
                    errors["base"] = "invalid_g12w_hour_range"
            
            if not errors:
                g12_settings = {}
                g12w_settings = {}
                
                if self.config_entry.data.get(CONF_OPERATION_MODE) in [MODE_G12, MODE_COMPARISON]:
                    g12_settings = {
                        CONF_PRICE_PEAK: user_input.pop(f"{CONF_G12_SETTINGS}_{CONF_PRICE_PEAK}"),
                        CONF_PRICE_OFFPEAK: user_input.pop(f"{CONF_G12_SETTINGS}_{CONF_PRICE_OFFPEAK}"),
                        CONF_HOURS_PEAK: user_input.pop(f"{CONF_G12_SETTINGS}_{CONF_HOURS_PEAK}")
                    }
                
                if self.config_entry.data.get(CONF_OPERATION_MODE) in [MODE_G12W, MODE_COMPARISON]:
                     g12w_settings = {
                        CONF_PRICE_PEAK: user_input.pop(f"{CONF_G12W_SETTINGS}_{CONF_PRICE_PEAK}"),
                        CONF_PRICE_OFFPEAK: user_input.pop(f"{CONF_G12W_SETTINGS}_{CONF_PRICE_OFFPEAK}"),
                        CONF_HOURS_PEAK: user_input.pop(f"{CONF_G12W_SETTINGS}_{CONF_HOURS_PEAK}")
                    }
                
                updated_data = {**self.options, **user_input}
                if g12_settings:
                    updated_data[CONF_G12_SETTINGS] = g12_settings
                if g12w_settings:
                    updated_data[CONF_G12W_SETTINGS] = g12w_settings

                return self.async_create_entry(title="", data=updated_data)

        current_config = {**self.config_entry.data, **self.config_entry.options}
        g12_settings = current_config.get(CONF_G12_SETTINGS, {})
        g12w_settings = current_config.get(CONF_G12W_SETTINGS, {})

        schema = {}

        if current_config.get(CONF_ENERGY_SENSOR):
             schema.update({
                vol.Optional(CONF_ENERGY_SENSOR, default=current_config.get(CONF_ENERGY_SENSOR)): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Required(CONF_SENSOR_TYPE, default=current_config.get(CONF_SENSOR_TYPE)): SelectSelector(
                    SelectSelectorConfig(options=[SENSOR_TYPE_TOTAL_INCREASING, SENSOR_TYPE_DAILY], mode=SelectSelectorMode.DROPDOWN, translation_key="sensor_type")
                ),
             })

        if current_config.get(CONF_OPERATION_MODE) in [MODE_G12, MODE_COMPARISON]:
            schema.update({
                vol.Required(f"{CONF_G12_SETTINGS}_{CONF_PRICE_PEAK}", default=g12_settings.get(CONF_PRICE_PEAK, 0.80)): vol.Coerce(float),
                vol.Required(f"{CONF_G12_SETTINGS}_{CONF_PRICE_OFFPEAK}", default=g12_settings.get(CONF_PRICE_OFFPEAK, 0.50)): vol.Coerce(float),
                vol.Required(f"{CONF_G12_SETTINGS}_{CONF_HOURS_PEAK}", default=g12_settings.get(CONF_HOURS_PEAK, DEFAULT_G12_PEAK_HOURS)): str,
            })
            
        if current_config.get(CONF_OPERATION_MODE) in [MODE_G12W, MODE_COMPARISON]:
             schema.update({
                vol.Required(f"{CONF_G12W_SETTINGS}_{CONF_PRICE_PEAK}", default=g12w_settings.get(CONF_PRICE_PEAK, 0.85)): vol.Coerce(float),
                vol.Required(f"{CONF_G12W_SETTINGS}_{CONF_PRICE_OFFPEAK}", default=g12w_settings.get(CONF_PRICE_OFFPEAK, 0.55)): vol.Coerce(float),
                vol.Required(f"{CONF_G12W_SETTINGS}_{CONF_HOURS_PEAK}", default=g12w_settings.get(CONF_HOURS_PEAK, DEFAULT_G12W_PEAK_HOURS)): str,
            })

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(schema),
            errors=errors
        )
