# custom_components/energy_hub_poland/config_flow.py
"""Config flow for Energy Hub Poland integration."""

import logging
import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_ENERGY_SENSOR,
    CONF_G11_SETTINGS,
    CONF_G12_SETTINGS,
    CONF_G12N_SETTINGS,
    CONF_G12W_SETTINGS,
    CONF_G13_SETTINGS,
    CONF_HOURS_PEAK,
    CONF_HOURS_PEAK_1_SUMMER,
    CONF_HOURS_PEAK_1_WINTER,
    CONF_HOURS_PEAK_2_SUMMER,
    CONF_HOURS_PEAK_2_WINTER,
    CONF_HOURS_PEAK_SUMMER,
    CONF_HOURS_PEAK_WINTER,
    CONF_OPERATION_MODE,
    CONF_PRICE_OFFPEAK,
    CONF_PRICE_PEAK,
    CONF_PRICE_PEAK_1,
    CONF_PRICE_PEAK_2,
    CONF_PRICE_UNIT,
    CONF_PROVIDER,
    CONF_SENSOR_TYPE,
    CONF_SPIKE_THRESHOLD,
    MODE_COMPARISON,
    MODE_DYNAMIC,
    MODE_G11,
    MODE_G12,
    MODE_G12N,
    MODE_G12W,
    MODE_G13,
    PROVIDER_CUSTOM,
    PROVIDER_ENEA,
    PROVIDER_ENERGA,
    PROVIDER_PGE,
    PROVIDER_STOEN,
    PROVIDER_TAURON,
    SENSOR_TYPE_DAILY,
    SENSOR_TYPE_TOTAL_INCREASING,
    UNIT_KWH,
    UNIT_MWH,
)

_LOGGER = logging.getLogger(__package__)

DEFAULT_G12_PEAK_HOURS = "6-13,15-22"

# Default hour configurations for different Polish energy providers
PROVIDER_DEFAULTS = {
    PROVIDER_PGE: {
        CONF_HOURS_PEAK: "6-13,15-22",
        "g12n_hours": "5-13,15-1",
    },
    PROVIDER_TAURON: {
        CONF_HOURS_PEAK: "6-13,15-22",
        "g13": {
            "p1_s": "7-13",
            "p2_s": "19-22",
            "p1_w": "7-13",
            "p2_w": "16-21",
        },
    },
    PROVIDER_ENERGA: {
        CONF_HOURS_PEAK: "6-13,15-22",
    },
    PROVIDER_ENEA: {
        CONF_HOURS_PEAK: "6-13,15-22",
    },
    PROVIDER_STOEN: {
        CONF_HOURS_PEAK: "6-13,15-22",
    },
}


def validate_hour_format(user_input: str) -> bool:
    """Validate hour range format (e.g., '6-13,15-22')."""
    if not user_input:
        return True
    pattern = re.compile(r"^\d{1,2}-\d{1,2}(,\d{1,2}-\d{1,2})*$")
    return pattern.match(user_input) is not None


def validate_entity_id(entity_id: str) -> bool:
    """Validate sensor entity ID format."""
    if not entity_id:
        return True
    return re.match(r"^sensor\..+$", entity_id) is not None


class EnergyHubPolandConfigFlow(config_entries.ConfigFlow, domain="energy_hub_poland"):  # type: ignore[call-arg]
    """Handle a config flow for Energy Hub Poland."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.config_data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - selection of operation mode."""
        if user_input is not None:
            self.config_data.update(user_input)
            return await self.async_step_advanced_config()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_OPERATION_MODE, default=MODE_DYNAMIC
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                MODE_DYNAMIC,
                                MODE_G12,
                                MODE_G12W,
                                MODE_COMPARISON,
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="operation_mode",
                        )
                    ),
                }
            ),
        )

    async def async_step_advanced_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle advanced configuration (units, provider, thresholds)."""
        mode = self.config_data[CONF_OPERATION_MODE]
        if user_input is not None:
            self.config_data.update(user_input)

            if mode == MODE_DYNAMIC:
                # Dynamic mode only needs advanced settings then it's done (no extra energy sensor step)
                return await self.async_finish_config()
            if mode == MODE_G12:
                return await self.async_step_g12_config()
            if mode == MODE_G12W:
                return await self.async_step_g12w_config()
            if mode == MODE_COMPARISON:
                return await self.async_step_g11_config()

        schema = {
            vol.Required(CONF_PRICE_UNIT, default=UNIT_KWH): SelectSelector(
                SelectSelectorConfig(
                    options=[UNIT_KWH, UNIT_MWH],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="price_unit",
                )
            ),
            vol.Required(CONF_PROVIDER, default=PROVIDER_CUSTOM): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        PROVIDER_CUSTOM,
                        PROVIDER_PGE,
                        PROVIDER_TAURON,
                        PROVIDER_ENEA,
                        PROVIDER_ENERGA,
                        PROVIDER_STOEN,
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="provider",
                )
            ),
        }

        # Price spike threshold is only relevant for Dynamic mode
        if mode == MODE_DYNAMIC:
            schema[vol.Required(CONF_SPIKE_THRESHOLD, default=30)] = vol.All(
                vol.Coerce(int), vol.Range(min=1, max=500)
            )

        return self.async_show_form(
            step_id="advanced_config", data_schema=vol.Schema(schema)
        )

    async def async_step_g11_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle G11 tariff configuration (flat rate)."""
        if user_input is not None:
            self.config_data[CONF_G11_SETTINGS] = user_input
            return await self.async_step_g12_config()

        return self.async_show_form(
            step_id="g11_config",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE_PEAK, default=0.80): vol.Coerce(float),
                }
            ),
        )

    def _get_default_hours(self) -> str:
        """Get default peak hours based on selected provider."""
        provider = self.config_data.get(CONF_PROVIDER, PROVIDER_CUSTOM)
        return PROVIDER_DEFAULTS.get(provider, {}).get(
            CONF_HOURS_PEAK, DEFAULT_G12_PEAK_HOURS
        )

    async def async_step_g12_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle G12 tariff configuration (2-zone seasonal)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not validate_hour_format(
                user_input[CONF_HOURS_PEAK_SUMMER]
            ) or not validate_hour_format(user_input[CONF_HOURS_PEAK_WINTER]):
                errors["base"] = "invalid_hour_range"
            else:
                self.config_data[CONF_G12_SETTINGS] = user_input
                mode = self.config_data[CONF_OPERATION_MODE]
                if mode == MODE_COMPARISON:
                    return await self.async_step_g12w_config()
                return await self.async_finish_config()

        default_hours = self._get_default_hours()
        return self.async_show_form(
            step_id="g12_config",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE_PEAK, default=0.80): vol.Coerce(float),
                    vol.Required(CONF_PRICE_OFFPEAK, default=0.50): vol.Coerce(float),
                    vol.Required(CONF_HOURS_PEAK_SUMMER, default=default_hours): str,
                    vol.Required(CONF_HOURS_PEAK_WINTER, default=default_hours): str,
                }
            ),
            errors=errors,
        )

    async def async_step_g12w_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle G12w tariff configuration (2-zone weekend/seasonal)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not validate_hour_format(
                user_input[CONF_HOURS_PEAK_SUMMER]
            ) or not validate_hour_format(user_input[CONF_HOURS_PEAK_WINTER]):
                errors["base"] = "invalid_hour_range"
            else:
                self.config_data[CONF_G12W_SETTINGS] = user_input
                mode = self.config_data[CONF_OPERATION_MODE]
                if mode == MODE_COMPARISON:
                    return await self.async_step_g12n_config()
                return await self.async_finish_config()

        default_hours = self._get_default_hours()
        return self.async_show_form(
            step_id="g12w_config",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE_PEAK, default=0.85): vol.Coerce(float),
                    vol.Required(CONF_PRICE_OFFPEAK, default=0.55): vol.Coerce(float),
                    vol.Required(CONF_HOURS_PEAK_SUMMER, default=default_hours): str,
                    vol.Required(CONF_HOURS_PEAK_WINTER, default=default_hours): str,
                }
            ),
            errors=errors,
        )

    async def async_step_g12n_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle G12n tariff configuration (PGE rules)."""
        if user_input is not None:
            self.config_data[CONF_G12N_SETTINGS] = user_input
            return await self.async_step_g13_config()

        return self.async_show_form(
            step_id="g12n_config",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE_PEAK, default=0.80): vol.Coerce(float),
                    vol.Required(CONF_PRICE_OFFPEAK, default=0.45): vol.Coerce(float),
                }
            ),
        )

    async def async_step_g13_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle G13 tariff configuration (Tauron 3-zone seasonal)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            hour_fields = [
                CONF_HOURS_PEAK_1_SUMMER,
                CONF_HOURS_PEAK_2_SUMMER,
                CONF_HOURS_PEAK_1_WINTER,
                CONF_HOURS_PEAK_2_WINTER,
            ]
            if any(not validate_hour_format(user_input[f]) for f in hour_fields):
                errors["base"] = "invalid_hour_range"
            else:
                self.config_data[CONF_G13_SETTINGS] = user_input
                return await self.async_step_energy_sensor()

        provider = self.config_data.get(CONF_PROVIDER)
        defaults = PROVIDER_DEFAULTS.get(
            PROVIDER_TAURON if provider == PROVIDER_TAURON else None, {}
        ).get("g13", {"p1_s": "7-13", "p2_s": "19-22", "p1_w": "7-13", "p2_w": "16-21"})

        return self.async_show_form(
            step_id="g13_config",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE_PEAK_1, default=1.00): vol.Coerce(float),
                    vol.Required(CONF_PRICE_PEAK_2, default=0.80): vol.Coerce(float),
                    vol.Required(CONF_PRICE_OFFPEAK, default=0.50): vol.Coerce(float),
                    vol.Required(
                        CONF_HOURS_PEAK_1_SUMMER, default=defaults["p1_s"]
                    ): str,
                    vol.Required(
                        CONF_HOURS_PEAK_2_SUMMER, default=defaults["p2_s"]
                    ): str,
                    vol.Required(
                        CONF_HOURS_PEAK_1_WINTER, default=defaults["p1_w"]
                    ): str,
                    vol.Required(
                        CONF_HOURS_PEAK_2_WINTER, default=defaults["p2_w"]
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_energy_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle energy sensor configuration (Only in Comparison mode)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_ENERGY_SENSOR) and not validate_entity_id(
                user_input[CONF_ENERGY_SENSOR]
            ):
                errors["base"] = "invalid_entity_id"
            else:
                self.config_data.update(user_input)
                return await self.async_finish_config()

        return self.async_show_form(
            step_id="energy_sensor",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_ENERGY_SENSOR): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Required(
                        CONF_SENSOR_TYPE, default=SENSOR_TYPE_TOTAL_INCREASING
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=[SENSOR_TYPE_TOTAL_INCREASING, SENSOR_TYPE_DAILY],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="sensor_type",
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_finish_config(self) -> FlowResult:
        """Finish the configuration flow and create entry."""
        title_map = {
            MODE_DYNAMIC: "Energy Hub Dynamic",
            MODE_G12: "Energy Hub G12",
            MODE_G12W: "Energy Hub G12w",
            MODE_COMPARISON: "Energy Hub Comparison",
        }
        title = title_map.get(self.config_data[CONF_OPERATION_MODE], "Energy Hub")
        return self.async_create_entry(title=title, data=self.config_data)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow handler."""
        return EnergyHubPolandOptionsFlowHandler(config_entry)


class EnergyHubPolandOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Energy Hub Poland."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize the options flow."""
        return await self.async_step_reconfigure()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration of integration options."""
        errors: dict[str, str] = {}
        config = {**self._config_entry.data, **self._config_entry.options}
        mode = config.get(CONF_OPERATION_MODE)

        if user_input is not None:
            # Validate all fields containing 'hours'
            for key, val in user_input.items():
                if "hours" in key and not validate_hour_format(str(val)):
                    errors["base"] = "invalid_hour_range"
                    break

            if not errors:
                new_options = {}
                # Map prefixed fields back to their respective settings dictionaries
                tariff_prefixes = {
                    "g11_settings": CONF_G11_SETTINGS,
                    "g12_settings": CONF_G12_SETTINGS,
                    "g12w_settings": CONF_G12W_SETTINGS,
                    "g12n_settings": CONF_G12N_SETTINGS,
                    "g13_settings": CONF_G13_SETTINGS,
                }

                temp_input = {**user_input}
                for prefix, settings_key in tariff_prefixes.items():
                    prefix_with_underscore = f"{prefix}_"
                    settings = {}
                    keys_to_remove = []
                    for k, v in temp_input.items():
                        if k.startswith(prefix_with_underscore):
                            settings[k.replace(prefix_with_underscore, "")] = v
                            keys_to_remove.append(k)
                    if settings:
                        new_options[settings_key] = settings
                        for k in keys_to_remove:
                            temp_input.pop(k)

                new_options.update(temp_input)
                return self.async_create_entry(title="", data=new_options)

        schema = {}

        # Unit selection is always available
        schema[
            vol.Required(CONF_PRICE_UNIT, default=config.get(CONF_PRICE_UNIT, UNIT_KWH))
        ] = SelectSelector(
            SelectSelectorConfig(
                options=[UNIT_KWH, UNIT_MWH],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="price_unit",
            )
        )

        # Spike threshold only for Dynamic/RCE mode
        if mode == MODE_DYNAMIC:
            schema[
                vol.Required(
                    CONF_SPIKE_THRESHOLD, default=config.get(CONF_SPIKE_THRESHOLD, 30)
                )
            ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=500))

        # Energy sensor settings only for Comparison mode
        if mode == MODE_COMPARISON:
            schema[
                vol.Optional(CONF_ENERGY_SENSOR, default=config.get(CONF_ENERGY_SENSOR))
            ] = EntitySelector(EntitySelectorConfig(domain="sensor"))
            schema[
                vol.Required(
                    CONF_SENSOR_TYPE,
                    default=config.get(CONF_SENSOR_TYPE, SENSOR_TYPE_TOTAL_INCREASING),
                )
            ] = SelectSelector(
                SelectSelectorConfig(
                    options=[SENSOR_TYPE_TOTAL_INCREASING, SENSOR_TYPE_DAILY],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="sensor_type",
                )
            )

        # Populate schema with fields relevant to the current mode
        tariffs_to_show = []
        if mode == MODE_COMPARISON:
            tariffs_to_show = [MODE_G11, MODE_G12, MODE_G12W, MODE_G12N, MODE_G13]
        else:
            tariffs_to_show = [mode]

        for t in tariffs_to_show:
            if t == MODE_G11:
                s = config.get(CONF_G11_SETTINGS, {})
                schema[
                    vol.Required(
                        "g11_settings_price_peak", default=s.get(CONF_PRICE_PEAK, 0.80)
                    )
                ] = vol.Coerce(float)
            elif t == MODE_G12:
                s = config.get(CONF_G12_SETTINGS, {})
                schema[
                    vol.Required(
                        "g12_settings_price_peak", default=s.get(CONF_PRICE_PEAK, 0.80)
                    )
                ] = vol.Coerce(float)
                schema[
                    vol.Required(
                        "g12_settings_price_offpeak",
                        default=s.get(CONF_PRICE_OFFPEAK, 0.50),
                    )
                ] = vol.Coerce(float)
                schema[
                    vol.Required(
                        "g12_settings_hours_peak_summer",
                        default=s.get(CONF_HOURS_PEAK_SUMMER, DEFAULT_G12_PEAK_HOURS),
                    )
                ] = str
                schema[
                    vol.Required(
                        "g12_settings_hours_peak_winter",
                        default=s.get(CONF_HOURS_PEAK_WINTER, DEFAULT_G12_PEAK_HOURS),
                    )
                ] = str
            elif t == MODE_G12W:
                s = config.get(CONF_G12W_SETTINGS, {})
                schema[
                    vol.Required(
                        "g12w_settings_price_peak", default=s.get(CONF_PRICE_PEAK, 0.85)
                    )
                ] = vol.Coerce(float)
                schema[
                    vol.Required(
                        "g12w_settings_price_offpeak",
                        default=s.get(CONF_PRICE_OFFPEAK, 0.55),
                    )
                ] = vol.Coerce(float)
                schema[
                    vol.Required(
                        "g12w_settings_hours_peak_summer",
                        default=s.get(CONF_HOURS_PEAK_SUMMER, DEFAULT_G12_PEAK_HOURS),
                    )
                ] = str
                schema[
                    vol.Required(
                        "g12w_settings_hours_peak_winter",
                        default=s.get(CONF_HOURS_PEAK_WINTER, DEFAULT_G12_PEAK_HOURS),
                    )
                ] = str
            elif t == MODE_G12N:
                s = config.get(CONF_G12N_SETTINGS, {})
                schema[
                    vol.Required(
                        "g12n_settings_price_peak", default=s.get(CONF_PRICE_PEAK, 0.80)
                    )
                ] = vol.Coerce(float)
                schema[
                    vol.Required(
                        "g12n_settings_price_offpeak",
                        default=s.get(CONF_PRICE_OFFPEAK, 0.45),
                    )
                ] = vol.Coerce(float)
            elif t == MODE_G13:
                s = config.get(CONF_G13_SETTINGS, {})
                schema[
                    vol.Required(
                        "g13_settings_price_peak_1",
                        default=s.get(CONF_PRICE_PEAK_1, 1.00),
                    )
                ] = vol.Coerce(float)
                schema[
                    vol.Required(
                        "g13_settings_price_peak_2",
                        default=s.get(CONF_PRICE_PEAK_2, 0.80),
                    )
                ] = vol.Coerce(float)
                schema[
                    vol.Required(
                        "g13_settings_price_offpeak",
                        default=s.get(CONF_PRICE_OFFPEAK, 0.50),
                    )
                ] = vol.Coerce(float)

        return self.async_show_form(
            step_id="reconfigure", data_schema=vol.Schema(schema), errors=errors
        )
