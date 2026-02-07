# custom_components/energy_hub_poland/config_flow.py
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
    CONF_G12_SETTINGS,
    CONF_G12W_SETTINGS,
    CONF_HOURS_PEAK,
    CONF_OPERATION_MODE,
    CONF_PRICE_OFFPEAK,
    CONF_PRICE_PEAK,
    CONF_SENSOR_TYPE,
    DEFAULT_G12_PEAK_HOURS,
    DEFAULT_G12W_PEAK_HOURS,
    MODE_COMPARISON,
    MODE_DYNAMIC,
    MODE_G12,
    MODE_G12W,
    SENSOR_TYPE_DAILY,
    SENSOR_TYPE_TOTAL_INCREASING,
)

_LOGGER = logging.getLogger(__package__)


def validate_hour_format(user_input: str) -> bool:
    """Validate hour format."""
    if not user_input:
        return True
    pattern = re.compile(r"^\d{1,2}-\d{1,2}(,\d{1,2}-\d{1,2})*$")
    return pattern.match(user_input) is not None


def validate_entity_id(entity_id: str) -> bool:
    """Validate entity ID format."""
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
        """Handle the initial step."""
        if user_input is not None:
            self.config_data.update(user_input)
            mode = user_input[CONF_OPERATION_MODE]

            if mode == MODE_G12:
                return await self.async_step_g12_config()
            if mode == MODE_G12W:
                return await self.async_step_g12w_config()
            if mode == MODE_COMPARISON:
                return await self.async_step_g12_config()

            return self.async_create_entry(
                title="Energy Hub Dynamic", data=self.config_data
            )

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

    async def async_step_g12_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle G12 tariff configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not validate_hour_format(user_input[CONF_HOURS_PEAK]):
                errors["base"] = "invalid_hour_range"
            else:
                self.config_data[CONF_G12_SETTINGS] = user_input
                mode = self.config_data[CONF_OPERATION_MODE]
                if mode == MODE_COMPARISON:
                    return await self.async_step_g12w_config()

                return self.async_create_entry(
                    title="Energy Hub G12", data=self.config_data
                )

        return self.async_show_form(
            step_id="g12_config",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE_PEAK, default=0.80): vol.Coerce(float),
                    vol.Required(CONF_PRICE_OFFPEAK, default=0.50): vol.Coerce(float),
                    vol.Required(CONF_HOURS_PEAK, default=DEFAULT_G12_PEAK_HOURS): str,
                }
            ),
            errors=errors,
        )

    async def async_step_g12w_config(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle G12w tariff configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not validate_hour_format(user_input[CONF_HOURS_PEAK]):
                errors["base"] = "invalid_hour_range"
            else:
                self.config_data[CONF_G12W_SETTINGS] = user_input
                if self.config_data[CONF_OPERATION_MODE] == MODE_COMPARISON:
                    return await self.async_step_energy_sensor()

                return self.async_create_entry(
                    title="Energy Hub G12w", data=self.config_data
                )

        return self.async_show_form(
            step_id="g12w_config",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRICE_PEAK, default=0.85): vol.Coerce(float),
                    vol.Required(CONF_PRICE_OFFPEAK, default=0.55): vol.Coerce(float),
                    vol.Required(CONF_HOURS_PEAK, default=DEFAULT_G12W_PEAK_HOURS): str,
                }
            ),
            errors=errors,
        )

    async def async_step_energy_sensor(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle energy sensor configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_ENERGY_SENSOR) and not validate_entity_id(
                user_input[CONF_ENERGY_SENSOR]
            ):
                errors["base"] = "invalid_entity_id"
            else:
                self.config_data.update(user_input)

                title_map = {
                    MODE_DYNAMIC: "Energy Hub Dynamic",
                    MODE_G12: "Energy Hub G12",
                    MODE_G12W: "Energy Hub G12w",
                    MODE_COMPARISON: "Energy Hub Comparison",
                }
                title = title_map.get(
                    self.config_data[CONF_OPERATION_MODE], "Energy Hub"
                )

                return self.async_create_entry(title=title, data=self.config_data)

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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
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
        try:
            config = {**self._config_entry.data, **self._config_entry.options}
            mode = config.get(CONF_OPERATION_MODE)
            if mode == MODE_DYNAMIC:
                return self.async_create_entry(title="", data={})

            return await self.async_step_reconfigure()
        except Exception as err:
            _LOGGER.error("Options flow init error: %s", err)
            return self.async_abort(reason="unknown")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reconfiguration."""
        errors: dict[str, str] = {}
        try:
            config = {**self._config_entry.data, **self._config_entry.options}
            mode = config.get(CONF_OPERATION_MODE)

            if user_input is not None:
                if mode in [MODE_G12, MODE_COMPARISON]:
                    val = user_input.get(f"{CONF_G12_SETTINGS}_{CONF_HOURS_PEAK}")
                    if not validate_hour_format(str(val) if val is not None else ""):
                        errors["base"] = "invalid_g12_hour_range"

                if mode in [MODE_G12W, MODE_COMPARISON]:
                    val = user_input.get(f"{CONF_G12W_SETTINGS}_{CONF_HOURS_PEAK}")
                    if not validate_hour_format(str(val) if val is not None else ""):
                        errors["base"] = "invalid_g12w_hour_range"

                if mode == MODE_COMPARISON:
                    if user_input.get(CONF_ENERGY_SENSOR) and not validate_entity_id(
                        user_input[CONF_ENERGY_SENSOR]
                    ):
                        errors["base"] = "invalid_entity_id"

                if not errors:
                    try:
                        new_options = {**user_input}
                        if mode in [MODE_G12, MODE_COMPARISON]:
                            new_options[CONF_G12_SETTINGS] = {
                                CONF_PRICE_PEAK: new_options.pop(
                                    f"{CONF_G12_SETTINGS}_{CONF_PRICE_PEAK}", 0.80
                                ),
                                CONF_PRICE_OFFPEAK: new_options.pop(
                                    f"{CONF_G12_SETTINGS}_{CONF_PRICE_OFFPEAK}", 0.50
                                ),
                                CONF_HOURS_PEAK: new_options.pop(
                                    f"{CONF_G12_SETTINGS}_{CONF_HOURS_PEAK}",
                                    DEFAULT_G12_PEAK_HOURS,
                                ),
                            }

                        if mode in [MODE_G12W, MODE_COMPARISON]:
                            new_options[CONF_G12W_SETTINGS] = {
                                CONF_PRICE_PEAK: new_options.pop(
                                    f"{CONF_G12W_SETTINGS}_{CONF_PRICE_PEAK}", 0.85
                                ),
                                CONF_PRICE_OFFPEAK: new_options.pop(
                                    f"{CONF_G12W_SETTINGS}_{CONF_PRICE_OFFPEAK}", 0.55
                                ),
                                CONF_HOURS_PEAK: new_options.pop(
                                    f"{CONF_G12W_SETTINGS}_{CONF_HOURS_PEAK}",
                                    DEFAULT_G12W_PEAK_HOURS,
                                ),
                            }

                        return self.async_create_entry(title="", data=new_options)
                    except Exception as err:
                        _LOGGER.error("Options flow process error: %s", err)
                        errors["base"] = "unknown"

            g12_settings = config.get(CONF_G12_SETTINGS) or {}
            g12w_settings = config.get(CONF_G12W_SETTINGS) or {}

            schema = {}

            if mode == MODE_COMPARISON:
                schema.update(
                    {
                        vol.Optional(
                            CONF_ENERGY_SENSOR,
                            default=config.get(CONF_ENERGY_SENSOR),
                        ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                        vol.Required(
                            CONF_SENSOR_TYPE,
                            default=config.get(
                                CONF_SENSOR_TYPE, SENSOR_TYPE_TOTAL_INCREASING
                            ),
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    SENSOR_TYPE_TOTAL_INCREASING,
                                    SENSOR_TYPE_DAILY,
                                ],
                                mode=SelectSelectorMode.DROPDOWN,
                                translation_key="sensor_type",
                            )
                        ),
                    }
                )

            if mode in [MODE_G12, MODE_COMPARISON]:
                schema.update(
                    {
                        vol.Required(
                            f"{CONF_G12_SETTINGS}_{CONF_PRICE_PEAK}",
                            default=g12_settings.get(CONF_PRICE_PEAK, 0.80),
                        ): vol.Coerce(float),
                        vol.Required(
                            f"{CONF_G12_SETTINGS}_{CONF_PRICE_OFFPEAK}",
                            default=g12_settings.get(CONF_PRICE_OFFPEAK, 0.50),
                        ): vol.Coerce(float),
                        vol.Required(
                            f"{CONF_G12_SETTINGS}_{CONF_HOURS_PEAK}",
                            default=g12_settings.get(
                                CONF_HOURS_PEAK, DEFAULT_G12_PEAK_HOURS
                            ),
                        ): str,
                    }
                )

            if mode in [MODE_G12W, MODE_COMPARISON]:
                schema.update(
                    {
                        vol.Required(
                            f"{CONF_G12W_SETTINGS}_{CONF_PRICE_PEAK}",
                            default=g12w_settings.get(CONF_PRICE_PEAK, 0.85),
                        ): vol.Coerce(float),
                        vol.Required(
                            f"{CONF_G12W_SETTINGS}_{CONF_PRICE_OFFPEAK}",
                            default=g12w_settings.get(CONF_PRICE_OFFPEAK, 0.55),
                        ): vol.Coerce(float),
                        vol.Required(
                            f"{CONF_G12W_SETTINGS}_{CONF_HOURS_PEAK}",
                            default=g12w_settings.get(
                                CONF_HOURS_PEAK, DEFAULT_G12W_PEAK_HOURS
                            ),
                        ): str,
                    }
                )

            return self.async_show_form(
                step_id="reconfigure", data_schema=vol.Schema(schema), errors=errors
            )
        except Exception as err:
            _LOGGER.error("Options flow reconfigure error: %s", err)
            return self.async_abort(reason="unknown")
