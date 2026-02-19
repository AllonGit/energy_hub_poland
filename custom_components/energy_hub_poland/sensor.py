# custom_components/energy_hub_poland/sensor.py
import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
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
    CONF_G12_SETTINGS,
    CONF_G12W_SETTINGS,
    CONF_HOURS_PEAK_SUMMER,
    CONF_HOURS_PEAK_WINTER,
    CONF_OPERATION_MODE,
    CONF_SENSOR_TYPE,
    CONF_UNIT_TYPE,
    DOMAIN,
    MODE_COMPARISON,
    MODE_DYNAMIC,
    MODE_G12,
    MODE_G12W,
    SENSOR_TYPE_DAILY,
    SENSOR_TYPE_TOTAL_INCREASING,
    UNIT_KWH,
    UNIT_MWH,
)
from .coordinator import EnergyHubDataCoordinator
from .entity import EnergyHubEntity as EnergyHubBaseEntity
from .helpers import (
    get_current_g12_price,
    get_current_g12w_price,
    is_peak_time,
    is_summer_time,
    parse_hour_ranges,
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
        sensors.extend(setup_g12_sensors(coordinator, entry, config, is_g12w=False))
    elif mode == MODE_G12W:
        sensors.extend(setup_g12_sensors(coordinator, entry, config, is_g12w=True))
    elif mode == MODE_COMPARISON:
        sensors.extend(setup_comparison_sensors(coordinator, entry, config))

    async_add_entities(sensors, update_before_add=True)


def setup_dynamic_sensors(
    coordinator: EnergyHubDataCoordinator, entry: ConfigEntry
) -> list[SensorEntity]:
    """Set up dynamic tariff sensors."""
    return [
        CurrentPriceSensor(coordinator, entry, "dynamic"),
        MinMaxPriceSensor(coordinator, entry, "today", "min"),
        MinMaxPriceSensor(coordinator, entry, "today", "max"),
        MinMaxPriceSensor(coordinator, entry, "tomorrow", "min"),
        MinMaxPriceSensor(coordinator, entry, "tomorrow", "max"),
        AveragePriceSensor(coordinator, entry, "today"),
        AveragePriceSensor(coordinator, entry, "tomorrow"),
        CheapestHourSensor(coordinator, entry, "today"),
        CheapestHourSensor(coordinator, entry, "tomorrow"),
    ]


def setup_g12_sensors(
    coordinator: EnergyHubDataCoordinator,
    entry: ConfigEntry,
    config: dict[str, Any],
    is_g12w: bool,
) -> list[SensorEntity]:
    """Set up G12/G12w tariff sensors."""
    tariff_name = "g12w" if is_g12w else "g12"
    return [
        CurrentPriceSensor(coordinator, entry, tariff_name, config),
        CurrentTariffSensor(coordinator, entry, tariff_name, config),
    ]


def setup_comparison_sensors(
    coordinator: EnergyHubDataCoordinator, entry: ConfigEntry, config: dict[str, Any]
) -> list[SensorEntity]:
    """Set up comparison mode sensors."""
    sensors: list[SensorEntity] = [
        CurrentPriceSensor(coordinator, entry, "dynamic"),
        CurrentPriceSensor(coordinator, entry, "g12", config),
        CurrentPriceSensor(coordinator, entry, "g12w", config),
        CurrentTariffSensor(coordinator, entry, "g12", config),
        CurrentTariffSensor(coordinator, entry, "g12w", config),
    ]
    if config.get(CONF_ENERGY_SENSOR):
        sensors.append(RecommendationSensor(coordinator, entry))
        sensors.extend(
            [
                SavingsSensor(coordinator, entry, "dynamic", "g12", "daily"),
                SavingsSensor(coordinator, entry, "dynamic", "g12", "monthly"),
                SavingsSensor(coordinator, entry, "dynamic", "g12w", "daily"),
                SavingsSensor(coordinator, entry, "dynamic", "g12w", "monthly"),
                SavingsSensor(coordinator, entry, "g12", "g12w", "daily"),
                SavingsSensor(coordinator, entry, "g12", "g12w", "monthly"),
            ]
        )
    return sensors


class EnergyHubEntity(EnergyHubBaseEntity, SensorEntity):
    """Base sensor entity for Energy Hub Poland."""

    def __init__(self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry):
        """Initialize the sensor entity."""
        super().__init__(coordinator, entry)


class EnergyConsumerEntity(EnergyHubEntity, RestoreEntity):
    """Base class for entities that consume energy sensor data."""

    def __init__(
        self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the consumer entity."""
        super().__init__(coordinator, entry)
        self._config = {**entry.data, **entry.options}
        self._energy_sensor_id = self._config.get(CONF_ENERGY_SENSOR)
        self._sensor_type = self._config.get(CONF_SENSOR_TYPE)
        self._last_energy_reading: float | None = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

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
        """Reset state on period transition."""

    @callback
    def _handle_energy_change(self, event: Any) -> None:
        """Handle energy sensor state changes."""
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
        """Process energy delta. To be overridden by subclasses."""

    def _get_energy_delta(self, current_energy: float) -> float:
        """Calculate energy delta from current reading."""
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
        """Get current prices for all tariffs."""
        now = dt_util.now()
        return {
            "dynamic": self.coordinator.data.get("today", {}).get(now.hour),
            "g12": get_current_g12_price(now, self._config.get(CONF_G12_SETTINGS, {})),
            "g12w": get_current_g12w_price(
                now, self._config.get(CONF_G12W_SETTINGS, {})
            ),
        }


class RecommendationSensor(EnergyConsumerEntity):
    """Sensor for the best tariff recommendation."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_icon = "mdi:lightbulb-auto"
    _attr_options = ["dynamiczna", "g12", "g12w", "brak_danych"]

    def __init__(
        self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_translation_key = "recommendation"
        self._attr_unique_id = f"recommendation_{entry.entry_id}"
        self._costs = {"dynamic": 0.0, "g12": 0.0, "g12w": 0.0}

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # Restore accumulated costs
        if (last_state := await self.async_get_last_state()) is not None:
            if "costs" in last_state.attributes:
                saved_costs = last_state.attributes["costs"]
                self._costs = {k: float(v) for k, v in saved_costs.items()}

    @callback
    def _reset_state(self, now: datetime) -> None:
        """Reset the cost values."""
        if now.day == 1:
            self._costs = {"dynamic": 0.0, "g12": 0.0, "g12w": 0.0}
            self.async_write_ha_state()

    def _process_energy_delta(self, delta: float) -> None:
        """Process energy delta for recommendation."""
        prices = self._get_tariff_prices()
        for tariff, price in prices.items():
            if price is not None:
                self._costs[tariff] += delta * price

        self.async_write_ha_state()

    @property
    def native_value(self) -> str:
        """Return the cheapest available tariff."""
        try:
            prices = self._get_tariff_prices()
            mapping = {
                "dynamiczna": prices.get("dynamic"),
                "g12": prices.get("g12"),
                "g12w": prices.get("g12w"),
            }
            # Filter out None values and ensure they are floats
            filtered = {}
            for k, v in mapping.items():
                if v is not None:
                    try:
                        filtered[k] = float(v)
                    except (ValueError, TypeError):
                        continue

            if not filtered:
                return "brak_danych"

            # native_value must return one of self._attr_options exactly
            cheapest = min(filtered, key=lambda k: filtered[k])
            return str(cheapest)
        except Exception as err:
            _LOGGER.error("Critical error in RecommendationSensor state: %s", err)
            return "brak_danych"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        dyn_cost = self._costs.get("dynamic", 0.0)
        return {
            "costs": {k: round(v, 2) for k, v in self._costs.items()},
            "savings_g12": round(dyn_cost - self._costs.get("g12", 0.0), 2),
            "savings_g12w": round(dyn_cost - self._costs.get("g12w", 0.0), 2),
            "savings_dynamic": 0.0,
        }


class CurrentTariffSensor(EnergyHubEntity):
    """Sensor for the current tariff (peak/off-peak)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["szczyt", "poza_szczytem"]

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
        tariff: str,
        config: dict,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._tariff = tariff
        self._config = config
        self._attr_translation_key = "current_tariff"
        self._attr_unique_id = f"current_tariff_{tariff}_{entry.entry_id}"
        # If comparison mode, we need distinct names
        if self._config.get(CONF_OPERATION_MODE) == MODE_COMPARISON:
            self._attr_translation_key = f"current_tariff_{tariff}"

    @property
    def native_value(self) -> str | None:
        """Return the current tariff."""
        now = dt_util.now()
        settings = self._config.get(
            CONF_G12W_SETTINGS if self._tariff == "g12w" else CONF_G12_SETTINGS, {}
        )

        if self._tariff == "g12w":
            from .helpers import _POLISH_HOLIDAYS

            if now.weekday() >= 5 or now.date() in _POLISH_HOLIDAYS:
                return "poza_szczytem"

        if is_summer_time(now):
            peak_hours_str = settings.get(CONF_HOURS_PEAK_SUMMER) or settings.get(
                "hours_peak", ""
            )
        else:
            peak_hours_str = settings.get(CONF_HOURS_PEAK_WINTER) or settings.get(
                "hours_peak", ""
            )

        peak_hours = parse_hour_ranges(peak_hours_str)
        if is_peak_time(now, peak_hours):
            return "szczyt"
        return "poza_szczytem"


class DynamicPriceEntity(EnergyHubEntity):
    """Base class for dynamic price entities."""

    _attr_device_class = SensorDeviceClass.MONETARY

    def __init__(self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry):
        """Initialize the entity."""
        super().__init__(coordinator, entry)
        self._config = {**entry.data, **entry.options}

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        unit = self._config.get(CONF_UNIT_TYPE, UNIT_KWH)
        return f"PLN/{'kWh' if unit == UNIT_KWH else 'MWh'}"

    def _get_day_prices(self, day: str) -> dict[int, float] | None:
        """Get prices for a given day."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(day)

    def _scale_price(self, val: float | None, precision: int = 4) -> float | None:
        """Scale price based on unit settings."""
        if val is None:
            return None
        if self._config.get(CONF_UNIT_TYPE) == UNIT_MWH:
            return round(val * 1000, 2)
        return round(val, precision)


class CurrentPriceSensor(DynamicPriceEntity):
    """Sensor for the current energy price."""

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
        tariff: str,
        config: dict | None = None,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._tariff = tariff
        self._attr_translation_key = f"current_price_{tariff}"
        self._attr_unique_id = f"current_price_{tariff}_{entry.entry_id}"

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        if self._tariff != "dynamic":
            return "PLN/kWh"
        return super().native_unit_of_measurement

    @property
    def native_value(self) -> float | None:
        now = dt_util.now()
        if self._tariff == "dynamic":
            prices = self._get_day_prices("today")
            val = prices.get(now.hour) if prices else None
            return self._scale_price(val)
        elif self._tariff == "g12" and self._config:
            return get_current_g12_price(now, self._config.get(CONF_G12_SETTINGS, {}))
        elif self._tariff == "g12w" and self._config:
            return get_current_g12w_price(now, self._config.get(CONF_G12W_SETTINGS, {}))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self._tariff == "dynamic":
            if not self.coordinator.data:
                return {"today_prices": {}, "tomorrow_prices": {}}
            return {
                "today_prices": self.coordinator.data.get("today", {}),
                "tomorrow_prices": self.coordinator.data.get("tomorrow", {}),
            }
        return {}


class AveragePriceSensor(DynamicPriceEntity):
    """Sensor for the average energy price of the day."""

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
        day: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._day = day
        self._attr_translation_key = f"average_price_{day}"
        self._attr_unique_id = f"average_price_{day}_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        if (prices := self._get_day_prices(self._day)) is None or not prices:
            return None
        avg = sum(prices.values()) / len(prices)
        return self._scale_price(avg)


class CheapestHourSensor(EnergyHubEntity):
    """Sensor for the hour with the lowest energy price."""

    _attr_icon = "mdi:clock-outline"

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
        day: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._day = day
        self._attr_translation_key = f"cheapest_hour_{day}"
        self._attr_unique_id = f"cheapest_hour_{day}_{entry.entry_id}"

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
        prices = self.coordinator.data.get(self._day, {})
        if not prices:
            return None
        cheapest_hour = min(prices, key=prices.get)
        return f"{cheapest_hour:02d}:00"


class MinMaxPriceSensor(DynamicPriceEntity):
    """Sensor for the minimum or maximum energy price of the day."""

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
        day: str,
        mode: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._day = day
        self._mode = mode
        self._attr_translation_key = f"{mode}_price_{day}"
        self._attr_unique_id = f"{mode}_price_{day}_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        if (prices := self._get_day_prices(self._day)) is None or not prices:
            return None
        val = min(prices.values()) if self._mode == "min" else max(prices.values())
        return self._scale_price(val)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if (prices := self._get_day_prices(self._day)) is None or not prices:
            return {"prices": {}}

        raw_val = min(prices.values()) if self._mode == "min" else max(prices.values())
        hours = [f"{h:02d}:00" for h, p in prices.items() if p == raw_val]
        attributes: dict[str, Any] = {"prices": prices}
        if len(hours) == 1:
            attributes["hour"] = hours[0]
        else:
            attributes["hours"] = hours
        return attributes


class CostSensor(EnergyConsumerEntity):
    """Sensor for the energy cost in a given period."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "PLN"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
        tariff: str,
        period: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._tariff = tariff
        self._period = period

        self._attr_translation_key = f"cost_{tariff}_{period}"
        self._attr_unique_id = f"cost_{tariff}_{period}_{entry.entry_id}"
        self._native_value = 0.0

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()

        # Restore accumulated cost
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._native_value = float(last_state.state)
            except (ValueError, TypeError):
                self._native_value = 0.0

    @callback
    def _reset_state(self, now: datetime) -> None:
        """Reset the cost values."""
        if self._period == "daily" or (self._period == "monthly" and now.day == 1):
            self._native_value = 0.0
            self.async_write_ha_state()

    def _process_energy_delta(self, delta: float) -> None:
        """Process energy delta for cost calculation."""
        price = self._get_current_price()
        if price is not None:
            self._native_value += delta * price
            self.async_write_ha_state()

    def _get_current_price(self) -> float | None:
        """Return the current price for the tariff."""
        now = dt_util.now()
        if self._tariff == "dynamic":
            if not self.coordinator.data:
                return None
            return self.coordinator.data.get("today", {}).get(now.hour)
        elif self._tariff == "g12":
            return get_current_g12_price(now, self._config.get(CONF_G12_SETTINGS, {}))
        elif self._tariff == "g12w":
            return get_current_g12w_price(now, self._config.get(CONF_G12W_SETTINGS, {}))
        return None

    @property
    def native_value(self):
        return round(self._native_value, 2) if self._native_value is not None else None


class SavingsSensor(CostSensor):
    """Sensor for the energy savings/balance between two tariffs."""

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
        base_tariff: str,
        compare_tariff: str,
        period: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, base_tariff, period)
        self._base_tariff = base_tariff
        self._compare_tariff = compare_tariff

        self._attr_translation_key = (
            f"savings_{base_tariff}_vs_{compare_tariff}_{period}"
        )
        self._attr_unique_id = (
            f"savings_{base_tariff}_vs_{compare_tariff}_{period}_{entry.entry_id}"
        )

    def _get_current_price(self) -> float | None:
        """Return the price difference between tariffs."""
        price_map = self._get_tariff_prices()

        base_price = price_map.get(self._base_tariff)
        compare_price = price_map.get(self._compare_tariff)

        if base_price is None or compare_price is None:
            return None

        return compare_price - base_price
