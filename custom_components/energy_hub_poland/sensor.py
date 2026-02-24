# custom_components/energy_hub_poland/sensor.py
"""Sensor platform for Energy Hub Poland."""

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENERGY_SENSOR,
    CONF_G11_SETTINGS,
    CONF_G12_SETTINGS,
    CONF_G12N_SETTINGS,
    CONF_G12W_SETTINGS,
    CONF_G13_SETTINGS,
    CONF_OPERATION_MODE,
    CONF_PRICE_UNIT,
    CONF_SENSOR_TYPE,
    DOMAIN,
    MODE_COMPARISON,
    MODE_DYNAMIC,
    MODE_G12,
    MODE_G12W,
    SENSOR_TYPE_DAILY,
    SENSOR_TYPE_TOTAL_INCREASING,
    UNIT_MWH,
)
from .coordinator import EnergyHubDataCoordinator
from .entity import EnergyHubEntity as EnergyHubBaseEntity
from .helpers import (
    get_current_g11_price,
    get_current_g12_price,
    get_current_g12n_price,
    get_current_g12w_price,
    get_current_g13_price,
)

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Any
) -> None:
    """Set up Energy Hub sensors from a config entry."""
    coordinator: EnergyHubDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    config = {**entry.data, **entry.options}
    mode = config.get(CONF_OPERATION_MODE)
    _LOGGER.debug(
        "Setting up sensors for mode: %s (entry_id: %s)", mode, entry.entry_id
    )
    sensors = []

    if mode == MODE_DYNAMIC:
        sensors.extend(setup_dynamic_sensors(coordinator, entry))
    elif mode == MODE_G12:
        sensors.append(CurrentPriceSensor(coordinator, entry, "g12", config))
    elif mode == MODE_G12W:
        sensors.append(CurrentPriceSensor(coordinator, entry, "g12w", config))
    elif mode == MODE_COMPARISON:
        sensors.extend(setup_comparison_sensors(coordinator, entry, config))

    async_add_entities(sensors, update_before_add=True)


def setup_dynamic_sensors(
    coordinator: EnergyHubDataCoordinator, entry: ConfigEntry
) -> list[SensorEntity]:
    """Set up dynamic tariff (RCE) sensors."""
    return [
        CurrentPriceSensor(coordinator, entry, "dynamic"),
        MinMaxPriceSensor(coordinator, entry, "today", "min"),
        MinMaxPriceSensor(coordinator, entry, "today", "max"),
        AveragePriceSensor(coordinator, entry, "today"),
        LowestPriceHourSensor(coordinator, entry, "today"),
        MinMaxPriceSensor(coordinator, entry, "tomorrow", "min"),
        MinMaxPriceSensor(coordinator, entry, "tomorrow", "max"),
        AveragePriceSensor(coordinator, entry, "tomorrow"),
        LowestPriceHourSensor(coordinator, entry, "tomorrow"),
    ]


def setup_comparison_sensors(
    coordinator: EnergyHubDataCoordinator, entry: ConfigEntry, config: dict[str, Any]
) -> list[SensorEntity]:
    """Set up comparison mode sensors (all tariffs included)."""
    sensors: list[SensorEntity] = [
        CurrentPriceSensor(coordinator, entry, "dynamic"),
        CurrentPriceSensor(coordinator, entry, "g11", config),
        CurrentPriceSensor(coordinator, entry, "g12", config),
        CurrentPriceSensor(coordinator, entry, "g12w", config),
        CurrentPriceSensor(coordinator, entry, "g12n", config),
        CurrentPriceSensor(coordinator, entry, "g13", config),
        # Analytical RCE sensors are also useful in Comparison mode
        MinMaxPriceSensor(coordinator, entry, "today", "min"),
        MinMaxPriceSensor(coordinator, entry, "today", "max"),
        AveragePriceSensor(coordinator, entry, "today"),
        LowestPriceHourSensor(coordinator, entry, "today"),
        MinMaxPriceSensor(coordinator, entry, "tomorrow", "min"),
        MinMaxPriceSensor(coordinator, entry, "tomorrow", "max"),
        AveragePriceSensor(coordinator, entry, "tomorrow"),
        LowestPriceHourSensor(coordinator, entry, "tomorrow"),
    ]
    # Recommendation sensor requires an energy sensor to calculate historical costs
    if config.get(CONF_ENERGY_SENSOR):
        sensors.append(RecommendationSensor(coordinator, entry))
    return sensors


class EnergyHubEntity(EnergyHubBaseEntity, SensorEntity):
    """Base sensor entity for Energy Hub Poland."""

    def __init__(self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry):
        """Initialize the sensor entity."""
        super().__init__(coordinator, entry)
        self._config = {**entry.data, **entry.options}
        self._price_unit = self._config.get(CONF_PRICE_UNIT)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement based on user settings."""
        if self.device_class == SensorDeviceClass.MONETARY:
            if self._price_unit == UNIT_MWH:
                return "PLN/MWh"
            return "PLN/kWh"
        return super().native_unit_of_measurement

    def _convert_price(self, value: float | None) -> float | None:
        """Convert price from PLN/kWh to PLN/MWh if necessary."""
        if value is None:
            return None
        if self._price_unit == UNIT_MWH:
            return round(value * 1000, 2)
        return round(value, 4)


class EnergyConsumerEntity(EnergyHubEntity, RestoreEntity):
    """Base class for entities that consume and process energy sensor readings."""

    def __init__(
        self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the consumer entity."""
        super().__init__(coordinator, entry)
        self._energy_sensor_id = self._config.get(CONF_ENERGY_SENSOR)
        self._sensor_type = self._config.get(CONF_SENSOR_TYPE)
        self._last_energy_reading: float | None = None

    @callback
    def _handle_energy_change(self, event: Any) -> None:
        """Handle state change event from the tracked energy sensor."""
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        try:
            current_energy = float(new_state.state)
        except ValueError:
            return

        energy_delta = self._get_energy_delta(current_energy)

        if energy_delta > 0:
            self._process_energy_delta(energy_delta)

    def _process_energy_delta(self, delta: float) -> None:
        """Process energy increment. Must be implemented by subclasses."""

    def _get_energy_delta(self, current_energy: float) -> float:
        """Calculate energy consumption increment since last reading."""
        energy_delta = 0.0
        if self._last_energy_reading is not None:
            if self._sensor_type == SENSOR_TYPE_TOTAL_INCREASING:
                if current_energy >= self._last_energy_reading:
                    energy_delta = current_energy - self._last_energy_reading
            elif self._sensor_type == SENSOR_TYPE_DAILY:
                if current_energy >= self._last_energy_reading:
                    energy_delta = current_energy - self._last_energy_reading
                else:
                    energy_delta = current_energy
        self._last_energy_reading = current_energy
        return energy_delta

    def _get_tariff_prices(self) -> dict[str, float | None]:
        """Get the current price for all supported tariffs."""
        now = dt_util.now()
        poland_tz = ZoneInfo("Europe/Warsaw")
        poland_now = now.astimezone(poland_tz)

        return {
            "dynamic": self.coordinator.data.get("today", {}).get(poland_now.hour),
            "g11": get_current_g11_price(self._config.get(CONF_G11_SETTINGS, {})),
            "g12": get_current_g12_price(
                poland_now, self._config.get(CONF_G12_SETTINGS, {})
            ),
            "g12w": get_current_g12w_price(
                poland_now, self._config.get(CONF_G12W_SETTINGS, {})
            ),
            "g12n": get_current_g12n_price(
                poland_now, self._config.get(CONF_G12N_SETTINGS, {})
            ),
            "g13": get_current_g13_price(
                poland_now, self._config.get(CONF_G13_SETTINGS, {})
            ),
        }


class RecommendationSensor(EnergyConsumerEntity):
    """Sensor that recommends the cheapest tariff based on historical consumption."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_icon = "mdi:lightbulb-auto"
    _attr_options = ["dynamiczna", "g11", "g12", "g12w", "g12n", "g13", "brak_danych"]

    def __init__(
        self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the recommendation sensor."""
        super().__init__(coordinator, entry)
        self._attr_translation_key = "recommendation"
        self._attr_unique_id = f"recommendation_{entry.entry_id}"
        # Store accumulated costs for each tariff
        self._costs = {k: 0.0 for k in ["dynamic", "g11", "g12", "g12w", "g12n", "g13"]}

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to HA - restore state and setup tracking."""
        await super().async_added_to_hass()

        # Restore accumulated costs from previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if "costs" in last_state.attributes:
                saved_costs = last_state.attributes["costs"]
                self._costs.update(
                    {k: float(v) for k, v in saved_costs.items() if k in self._costs}
                )

        # Initialize last reading from the energy sensor's current state
        if self._energy_sensor_id:
            if (state := self.hass.states.get(self._energy_sensor_id)) is not None:
                try:
                    self._last_energy_reading = float(state.state)
                except (ValueError, TypeError):
                    pass

            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._energy_sensor_id], self._handle_energy_change
                )
            )
            self.async_on_remove(
                async_track_time_change(
                    self.hass, self._reset_state, hour=0, minute=0, second=5
                )
            )

    @callback
    def _reset_state(self, now: datetime) -> None:
        """Reset accumulated costs on the 1st of each month."""
        if now.day == 1:
            self._costs = {k: 0.0 for k in self._costs}
            self.async_write_ha_state()

    def _process_energy_delta(self, delta: float) -> None:
        """Apply energy delta to each tariff's accumulated cost."""
        prices = self._get_tariff_prices()
        for tariff, price in prices.items():
            if price is not None:
                self._costs[tariff] += delta * price

        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        """Determine and return the cheapest tariff."""
        try:
            # Prefer using accumulated costs for recommendation
            if any(v > 0 for v in self._costs.values()):
                cheapest = min(self._costs, key=lambda k: self._costs[k])
                return "dynamiczna" if cheapest == "dynamic" else cheapest

            # Fallback to current instantaneous prices
            prices = self._get_tariff_prices()
            mapping = {
                "dynamiczna": prices.get("dynamic"),
                "g11": prices.get("g11"),
                "g12": prices.get("g12"),
                "g12w": prices.get("g12w"),
                "g12n": prices.get("g12n"),
                "g13": prices.get("g13"),
            }
            filtered = {k: float(v) for k, v in mapping.items() if v is not None}

            if not filtered:
                return "brak_danych"

            cheapest = min(filtered, key=lambda k: filtered[k])
            return cheapest
        except Exception as err:
            _LOGGER.error("Critical error in RecommendationSensor state: %s", err)
            return "brak_danych"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose calculated costs and savings as attributes."""
        dyn_cost = self._costs.get("dynamic", 0.0)
        attrs = {
            "costs": {k: round(v, 2) for k, v in self._costs.items()},
        }
        for k, v in self._costs.items():
            if k != "dynamic":
                attrs[f"savings_{k}_vs_dynamic"] = round(dyn_cost - v, 2)
        return attrs


class CurrentPriceSensor(EnergyHubEntity):
    """Sensor providing the current price for a specific tariff."""

    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
        tariff: str,
        config: dict | None = None,
    ) -> None:
        """Initialize the price sensor."""
        super().__init__(coordinator, entry)
        self._tariff = tariff
        self._attr_translation_key = f"current_price_{tariff}"
        self._attr_unique_id = f"current_price_{tariff}_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        """Fetch and convert the current tariff price."""
        now = dt_util.now()
        poland_tz = ZoneInfo("Europe/Warsaw")
        poland_now = now.astimezone(poland_tz)

        val = None
        if self._tariff == "dynamic":
            if self.coordinator.data:
                prices = self.coordinator.data.get("today", {})
                val = prices.get(poland_now.hour) if prices else None
        elif self._tariff == "g11":
            val = get_current_g11_price(self._config.get(CONF_G11_SETTINGS, {}))
        elif self._tariff == "g12":
            val = get_current_g12_price(
                poland_now, self._config.get(CONF_G12_SETTINGS, {})
            )
        elif self._tariff == "g12w":
            val = get_current_g12w_price(
                poland_now, self._config.get(CONF_G12W_SETTINGS, {})
            )
        elif self._tariff == "g12n":
            val = get_current_g12n_price(
                poland_now, self._config.get(CONF_G12N_SETTINGS, {})
            )
        elif self._tariff == "g13":
            val = get_current_g13_price(
                poland_now, self._config.get(CONF_G13_SETTINGS, {})
            )

        return self._convert_price(val)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose full day price tables for dynamic mode."""
        if self._tariff == "dynamic":
            if not self.coordinator.data:
                return {"today_prices": {}, "tomorrow_prices": {}}
            return {
                "today_prices": self.coordinator.data.get("today", {}),
                "tomorrow_prices": self.coordinator.data.get("tomorrow", {}),
            }
        return {}


class MinMaxPriceSensor(EnergyHubEntity):
    """Sensor for the minimum or maximum energy price of the day (RCE)."""

    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
        day: str,
        mode: str,
    ) -> None:
        """Initialize the min/max price sensor."""
        super().__init__(coordinator, entry)
        self._day = day
        self._mode = mode
        self._attr_translation_key = f"{mode}_price_{day}"
        self._attr_unique_id = f"{mode}_price_{day}_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        """Return the min or max price for the specified day."""
        if not self.coordinator.data:
            return None
        prices = self.coordinator.data.get(self._day, {})
        if not prices:
            return None
        val = min(prices.values()) if self._mode == "min" else max(prices.values())
        return self._convert_price(val)


class AveragePriceSensor(EnergyHubEntity):
    """Sensor for the average energy price of the day (RCE)."""

    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
        day: str,
    ) -> None:
        """Initialize the average price sensor."""
        super().__init__(coordinator, entry)
        self._day = day
        self._attr_translation_key = f"avg_price_{day}"
        self._attr_unique_id = f"avg_price_{day}_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        """Return the average price for the specified day."""
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.get(f"{self._day}_avg")
        return self._convert_price(val)


class LowestPriceHourSensor(EnergyHubEntity):
    """Sensor for the hour with the lowest energy price (RCE)."""

    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
        day: str,
    ) -> None:
        """Initialize the lowest price hour sensor."""
        super().__init__(coordinator, entry)
        self._day = day
        self._attr_translation_key = f"lowest_price_hour_{day}"
        self._attr_unique_id = f"lowest_price_hour_{day}_{entry.entry_id}"

    @property
    def native_value(self) -> str | None:
        """Return the formatted hour string (e.g. '14:00')."""
        if not self.coordinator.data:
            return None
        hour = self.coordinator.data.get(f"{self._day}_min_hour")
        return f"{hour:02d}:00" if hour is not None else None
