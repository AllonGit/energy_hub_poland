"""Sensor platform for Energy Hub Poland."""

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ENABLED_TARIFFS,
    CONF_ENERGY_SENSOR,
    CONF_G11_SETTINGS,
    CONF_G12_SETTINGS,
    CONF_G12N_SETTINGS,
    CONF_G12W_SETTINGS,
    CONF_G13_SETTINGS,
    CONF_NETWORK_VARIABLE_FEE,
    CONF_NETWORK_VARIABLE_FEE_DYNAMIC,
    CONF_NETWORK_VARIABLE_FEE_G12_OFFPEAK,
    CONF_NETWORK_VARIABLE_FEE_G12_PEAK,
    CONF_NETWORK_VARIABLE_FEE_G12N_OFFPEAK,
    CONF_NETWORK_VARIABLE_FEE_G12N_PEAK,
    CONF_NETWORK_VARIABLE_FEE_G12W_OFFPEAK,
    CONF_NETWORK_VARIABLE_FEE_G12W_PEAK,
    CONF_NETWORK_VARIABLE_FEE_G13_OFFPEAK,
    CONF_NETWORK_VARIABLE_FEE_G13_PEAK1,
    CONF_NETWORK_VARIABLE_FEE_G13_PEAK2,
    CONF_OPERATION_MODE,
    CONF_PRICE_UNIT,
    CONF_SENSOR_TYPE,
    CONF_VAT_RATE,
    DOMAIN,
    ICONS,
    MODE_COMPARISON,
    MODE_DYNAMIC,
    MODE_G12,
    MODE_G12N,
    MODE_G12W,
    SENSOR_TYPE_DAILY,
    SENSOR_TYPE_TOTAL_INCREASING,
    UNIT_MWH,
)
from .coordinator import EnergyHubDataCoordinator
from .entity import EnergyHubEntity as EnergyHubBaseEntity
from .tariffs import (
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
        sensors.extend(setup_pse_sensors(coordinator, entry))
        sensors.append(PriceStatusSensor(coordinator, entry))
        sensors.append(BestUsageHourSensor(coordinator, entry))
        sensors.append(SavingsPotentialSensor(coordinator, entry))
    elif mode == MODE_G12:
        sensors.append(CurrentPriceSensor(coordinator, entry, "g12", config))
    elif mode == MODE_G12W:
        sensors.append(CurrentPriceSensor(coordinator, entry, "g12w", config))
    elif mode == MODE_G12N:
        sensors.append(CurrentPriceSensor(coordinator, entry, "g12n", config))
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
        HighestPriceHourSensor(coordinator, entry, "today"),
        MinMaxPriceSensor(coordinator, entry, "tomorrow", "min"),
        MinMaxPriceSensor(coordinator, entry, "tomorrow", "max"),
        AveragePriceSensor(coordinator, entry, "tomorrow"),
        LowestPriceHourSensor(coordinator, entry, "tomorrow"),
        HighestPriceHourSensor(coordinator, entry, "tomorrow"),
    ]


def setup_pse_sensors(
    coordinator: EnergyHubDataCoordinator, entry: ConfigEntry
) -> list[SensorEntity]:
    """Set up additional PSE-specific sensors."""
    return [
        KSELoadSensor(coordinator, entry),
        KSEGenerationSensor(coordinator, entry),
    ]


def setup_comparison_sensors(
    coordinator: EnergyHubDataCoordinator, entry: ConfigEntry, config: dict[str, Any]
) -> list[SensorEntity]:
    """Set up comparison mode sensors (enabled tariffs only)."""
    enabled_tariffs = config.get(
        CONF_ENABLED_TARIFFS, ["dynamic", "g11", "g12", "g12w", "g12n", "g13"]
    )
    sensors: list[SensorEntity] = []

    tariff_configs = {
        "dynamic": None,
        "g11": config,
        "g12": config,
        "g12w": config,
        "g12n": config,
        "g13": config,
    }

    for tariff in enabled_tariffs:
        if tariff in tariff_configs:
            sensors.append(
                CurrentPriceSensor(coordinator, entry, tariff, tariff_configs[tariff])
            )

    sensors.extend(
        [
            MinMaxPriceSensor(coordinator, entry, "today", "min"),
            MinMaxPriceSensor(coordinator, entry, "today", "max"),
            AveragePriceSensor(coordinator, entry, "today"),
            LowestPriceHourSensor(coordinator, entry, "today"),
            MinMaxPriceSensor(coordinator, entry, "tomorrow", "min"),
            MinMaxPriceSensor(coordinator, entry, "tomorrow", "max"),
            AveragePriceSensor(coordinator, entry, "tomorrow"),
            LowestPriceHourSensor(coordinator, entry, "tomorrow"),
        ]
    )
    if config.get(CONF_ENERGY_SENSOR):
        sensors.append(RecommendationSensor(coordinator, entry))
        for tariff in enabled_tariffs:
            sensors.append(TariffCostSensor(coordinator, entry, tariff))

    return sensors


class EnergyHubSensorEntity(EnergyHubBaseEntity, SensorEntity):
    """Base sensor entity for Energy Hub Poland."""

    def __init__(self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry):
        """Initialize the sensor entity."""
        super().__init__(coordinator, entry)
        self._price_unit = self._config.get(CONF_PRICE_UNIT) or self._config.get(
            "unit_type", "kwh"
        )

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
        price_unit = getattr(self, "_price_unit", "kwh")
        if price_unit == UNIT_MWH:
            return round(value * 1000, 2)
        return round(value, 4)

    def _get_price_series(self, day: str) -> dict[int, float] | None:
        """Return the price series for the selected day from coordinator data."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.get(day)

    def _get_relevant_price_series(self) -> tuple[dict[int, float], str]:
        """Return price data for the current or next relevant period."""
        if not self.coordinator.data:
            return {}, "none"

        now = dt_util.now()
        poland_tz = ZoneInfo("Europe/Warsaw")
        poland_now = now.astimezone(poland_tz)

        today_prices = self.coordinator.data.get("today", {}) or {}
        tomorrow_prices = self.coordinator.data.get("tomorrow", {}) or {}

        future_today = {
            hour: price
            for hour, price in today_prices.items()
            if hour >= poland_now.hour
        }
        if future_today:
            return future_today, "today"
        if tomorrow_prices:
            return tomorrow_prices, "tomorrow"
        if today_prices:
            return today_prices, "today"
        return {}, "none"

    def _calculate_total_price(
        self, energy_price: float | None, tariff: str
    ) -> dict[str, float] | None:
        """Apply network fees and VAT to the energy price and return split components."""
        if energy_price is None:
            return None

        variable_fee = None
        if tariff == "dynamic":
            variable_fee = self._config.get(CONF_NETWORK_VARIABLE_FEE_DYNAMIC)
        elif tariff == "g12":
            tariff_settings = self._config.get(f"{tariff}_settings", {})
            if energy_price == tariff_settings.get("price_peak"):
                variable_fee = tariff_settings.get(CONF_NETWORK_VARIABLE_FEE_G12_PEAK)
            else:
                variable_fee = tariff_settings.get(
                    CONF_NETWORK_VARIABLE_FEE_G12_OFFPEAK
                )
            if variable_fee is None:
                variable_fee = tariff_settings.get(CONF_NETWORK_VARIABLE_FEE)
        elif tariff == "g12w":
            tariff_settings = self._config.get(f"{tariff}_settings", {})
            if energy_price == tariff_settings.get("price_peak"):
                variable_fee = tariff_settings.get(CONF_NETWORK_VARIABLE_FEE_G12W_PEAK)
            else:
                variable_fee = tariff_settings.get(
                    CONF_NETWORK_VARIABLE_FEE_G12W_OFFPEAK
                )
            if variable_fee is None:
                variable_fee = tariff_settings.get(CONF_NETWORK_VARIABLE_FEE)
        elif tariff == "g12n":
            tariff_settings = self._config.get(f"{tariff}_settings", {})
            if energy_price == tariff_settings.get("price_peak"):
                variable_fee = tariff_settings.get(CONF_NETWORK_VARIABLE_FEE_G12N_PEAK)
            else:
                variable_fee = tariff_settings.get(
                    CONF_NETWORK_VARIABLE_FEE_G12N_OFFPEAK
                )
            if variable_fee is None:
                variable_fee = tariff_settings.get(CONF_NETWORK_VARIABLE_FEE)
        elif tariff == "g13":
            tariff_settings = self._config.get(f"{tariff}_settings", {})
            if energy_price == tariff_settings.get("price_peak_1"):
                variable_fee = tariff_settings.get(CONF_NETWORK_VARIABLE_FEE_G13_PEAK1)
            elif energy_price == tariff_settings.get("price_peak_2"):
                variable_fee = tariff_settings.get(CONF_NETWORK_VARIABLE_FEE_G13_PEAK2)
            else:
                variable_fee = tariff_settings.get(
                    CONF_NETWORK_VARIABLE_FEE_G13_OFFPEAK
                )
            if variable_fee is None:
                variable_fee = tariff_settings.get(CONF_NETWORK_VARIABLE_FEE)
        else:
            tariff_settings = self._config.get(f"{tariff}_settings", {})
            variable_fee = tariff_settings.get(CONF_NETWORK_VARIABLE_FEE)
            if variable_fee is None:
                legacy_key = f"network_variable_fee_{tariff}"
                variable_fee = tariff_settings.get(legacy_key)

        if variable_fee is None or float(variable_fee) == 0.0:
            variable_fee = self._config.get(CONF_NETWORK_VARIABLE_FEE, 0.0)

        variable_fee = float(variable_fee)
        total_net = energy_price + variable_fee

        vat_rate_str = self._config.get(CONF_VAT_RATE, "0")
        try:
            vat_rate = float(vat_rate_str) / 100
        except (ValueError, TypeError):
            vat_rate = 0.0

        vat_amount = total_net * vat_rate
        total = total_net * (1 + vat_rate)
        return {
            "energy": float(energy_price),
            "variable_fee": float(variable_fee),
            "vat": float(vat_amount),
            "total": float(total),
        }


class EnergyConsumerEntity(EnergyHubSensorEntity, RestoreEntity):
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

    def _get_tariff_prices(self) -> dict[str, dict[str, float] | None]:
        """Get the current price breakdown for all supported tariffs."""
        now = dt_util.now()
        poland_tz = ZoneInfo("Europe/Warsaw")
        poland_now = now.astimezone(poland_tz)

        if not self.coordinator.data:
            return {}

        today_prices = self.coordinator.data.get("today", {})

        prices = {
            "dynamic": today_prices.get(poland_now.hour),
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

        return {
            tariff: self._calculate_total_price(price, tariff)
            for tariff, price in prices.items()
        }


class TariffCostSensor(EnergyHubSensorEntity, RestoreEntity):
    """Sensor representing the accumulated cost for a specific tariff."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
        tariff: str,
    ) -> None:
        """Initialize the tariff cost sensor."""
        super().__init__(coordinator, entry)
        self._tariff = tariff
        self._attr_translation_key = f"cost_{tariff}"
        self._attr_unique_id = f"cost_{tariff}_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        """Return the accumulated cost from the recommendation sensor."""
        costs = self.coordinator.data.get("costs", {})
        return round(costs.get(self._tariff, 0.0), 2)

    @property
    def last_reset(self) -> datetime | None:
        """Return the timestamp when accumulated costs were last reset."""
        return self.coordinator.data.get("last_reset")

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to HA."""
        await super().async_added_to_hass()

        costs = self.coordinator.costs
        if costs.get(self._tariff, 0.0) == 0.0:
            if (last_state := await self.async_get_last_state()) is not None:
                try:
                    val = float(last_state.state)
                    if val > 0:
                        _LOGGER.info(
                            "Migrating restored value %s for %s to coordinator",
                            val,
                            self._tariff,
                        )
                        self.coordinator.costs[self._tariff] = val
                        self.coordinator.async_set_updated_data(self.coordinator.data)
                except (ValueError, TypeError):
                    pass


class RecommendationSensor(EnergyConsumerEntity):
    """Sensor that recommends the cheapest tariff based on historical consumption."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_state_class = None
    _attr_icon = ICONS.get("recommendation")
    _attr_options = ["dynamiczna", "g11", "g12", "g12w", "g12n", "g13", "brak_danych"]

    def __init__(
        self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the recommendation sensor."""
        super().__init__(coordinator, entry)
        self._attr_translation_key = "recommendation"
        self._attr_unique_id = f"recommendation_{entry.entry_id}"
        self._enabled_tariffs = self._config.get(
            CONF_ENABLED_TARIFFS, ["dynamic", "g11", "g12", "g12w", "g12n", "g13"]
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity being added to HA - setup tracking."""
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

    def _process_energy_delta(self, delta: float) -> None:
        """Apply energy delta to each tariff's accumulated cost in the coordinator."""
        prices = self._get_tariff_prices()
        filtered_prices = {
            k: v for k, v in prices.items() if k in self._enabled_tariffs
        }
        self.coordinator.async_update_costs(delta, filtered_prices)

    @property
    def native_value(self) -> str:
        """Determine and return the cheapest tariff."""
        try:
            costs = self.coordinator.data.get("costs", {})
            if any(v > 0 for v in costs.values()):
                enabled_costs = {
                    k: v for k, v in costs.items() if k in self._enabled_tariffs
                }
                if enabled_costs:
                    cheapest = min(enabled_costs, key=lambda k: enabled_costs[k])
                    return "dynamiczna" if cheapest == "dynamic" else cheapest

            prices = self._get_tariff_prices()
            filtered = {
                tariff: prices[tariff]["total"]
                for tariff in self._enabled_tariffs
                if tariff in prices and prices[tariff] is not None
            }

            if not filtered:
                return "brak_danych"

            cheapest = min(filtered, key=lambda k: filtered[k])
            return "dynamiczna" if cheapest == "dynamic" else cheapest
        except Exception as err:
            _LOGGER.error("Critical error in RecommendationSensor state: %s", err)
            return "brak_danych"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose calculated costs and savings as attributes."""
        costs = self.coordinator.data.get("costs", {})
        enabled_costs = {
            k: round(v, 2) for k, v in costs.items() if k in self._enabled_tariffs
        }
        dyn_cost = enabled_costs.get("dynamic", 0.0)
        attrs = {
            "costs": enabled_costs,
        }
        for k, v in enabled_costs.items():
            if k != "dynamic":
                attrs[f"savings_{k}_vs_dynamic"] = round(
                    dyn_cost - v,
                    2,
                )
        return attrs


class PriceStatusSensor(EnergyHubSensorEntity):
    """Sensor that classifies the current dynamic price as cheap, normal or expensive."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_state_class = None
    _attr_icon = "mdi:chart-line"
    _attr_options = ["cheap", "normal", "expensive"]

    def __init__(self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry):
        """Initialize the price status sensor."""
        super().__init__(coordinator, entry)
        self._attr_translation_key = "price_status"
        self._attr_unique_id = f"price_status_{entry.entry_id}"

    def _get_current_price(self) -> float | None:
        """Return the current dynamic price from coordinator data."""
        if not self.coordinator.data:
            return None

        now = dt_util.now()
        poland_tz = ZoneInfo("Europe/Warsaw")
        poland_now = now.astimezone(poland_tz)
        today_prices = self.coordinator.data.get("today", {})
        return today_prices.get(poland_now.hour) if today_prices else None

    def _get_average_price(self) -> float | None:
        """Return the average dynamic price for the current day."""
        if not self.coordinator.data:
            return None

        today_prices = self.coordinator.data.get("today", {})
        if not today_prices:
            return None

        today_avg = self.coordinator.data.get("today_avg")
        if today_avg is not None:
            return today_avg
        return sum(today_prices.values()) / len(today_prices)

    @property
    def native_value(self) -> str | None:
        """Return a simple cheap/normal/expensive classification."""
        current_price = self._get_current_price()
        average_price = self._get_average_price()
        if current_price is None or average_price is None:
            return None

        threshold = self._config.get("spike_threshold", 30)
        try:
            threshold_value = float(threshold)
        except (TypeError, ValueError):
            threshold_value = 30.0

        if average_price == 0:
            return (
                "cheap"
                if current_price <= 0
                else "expensive"
                if current_price > 0
                else "normal"
            )

        lower_bound = average_price * (1 - threshold_value / 100)
        upper_bound = average_price * (1 + threshold_value / 100)

        if current_price < lower_bound:
            return "cheap"
        if current_price > upper_bound:
            return "expensive"
        return "normal"


class BestUsageHourSensor(EnergyHubSensorEntity):
    """Sensor suggesting the cheapest hour to run a load today or tomorrow."""

    _attr_device_class = None
    _attr_state_class = None
    _attr_icon = "mdi:clock-start"

    def __init__(self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry):
        """Initialize the best usage hour sensor."""
        super().__init__(coordinator, entry)
        self._attr_translation_key = "best_usage_hour"
        self._attr_unique_id = f"best_usage_hour_{entry.entry_id}"

    def _get_hour_candidates(self) -> tuple[dict[int, float], str]:
        """Return price map and source label for the next relevant period."""
        return self._get_relevant_price_series()

    @property
    def native_value(self) -> str | None:
        """Return the best hour in HH:00 format."""
        prices, _ = self._get_hour_candidates()
        if not prices:
            return None

        min_price = min(prices.values())
        hour = [h for h, p in prices.items() if p == min_price][0]
        return f"{hour:02d}:00"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose the selected price and source for automation use."""
        prices, source = self._get_hour_candidates()
        if not prices:
            return {"price": None, "source": source}

        min_price = min(prices.values())
        total_price = self._calculate_total_price(min_price, "dynamic")
        return {
            "price": self._convert_price(total_price["total"] if total_price else None),
            "source": source,
        }


class SavingsPotentialSensor(EnergyHubSensorEntity):
    """Sensor showing potential savings if the current load is moved to the cheapest hour."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, coordinator: EnergyHubDataCoordinator, entry: ConfigEntry):
        """Initialize the savings potential sensor."""
        super().__init__(coordinator, entry)
        self._attr_translation_key = "savings_potential"
        self._attr_unique_id = f"savings_potential_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        """Return the savings potential for moving current usage to the cheapest hour."""
        if not self.coordinator.data:
            return None

        today_prices = self._get_price_series("today") or {}
        if not today_prices:
            return None

        now = dt_util.now()
        poland_tz = ZoneInfo("Europe/Warsaw")
        poland_now = now.astimezone(poland_tz)
        current_price = today_prices.get(poland_now.hour)
        if current_price is None:
            return None

        min_price = min(today_prices.values())
        if min_price >= current_price:
            return None

        savings = current_price - min_price
        total_price = self._calculate_total_price(savings, "dynamic")
        return self._convert_price(total_price["total"] if total_price else None)


class CurrentPriceSensor(EnergyHubSensorEntity):
    """Sensor providing the current price for a specific tariff."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None

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

        total_price = self._calculate_total_price(val, self._tariff)
        return self._convert_price(total_price["total"] if total_price else None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose price forecast tables and statistics for visualization."""
        attrs = {}

        variable_fee = None
        if self._tariff == "dynamic":
            variable_fee = self._config.get(CONF_NETWORK_VARIABLE_FEE_DYNAMIC)
        else:
            tariff_settings = self._config.get(f"{self._tariff}_settings", {})
            variable_fee = tariff_settings.get(CONF_NETWORK_VARIABLE_FEE)
            if variable_fee is None:
                variable_fee = tariff_settings.get(
                    f"network_variable_fee_{self._tariff}"
                )

        if variable_fee is None or float(variable_fee) == 0.0:
            variable_fee = self._config.get(CONF_NETWORK_VARIABLE_FEE, 0.0)

        attrs["network_variable_fee"] = float(variable_fee)
        attrs["vat_rate"] = f"{self._config.get(CONF_VAT_RATE, '0')}%"

        if self._tariff == "dynamic":
            if not self.coordinator.data:
                attrs.update({"today_prices": {}, "tomorrow_prices": {}})
                return attrs

            today_raw = self.coordinator.data.get("today", {})
            tomorrow_raw = self.coordinator.data.get("tomorrow", {})

            today_total: dict[Any, float | None] = {
                h: (
                    self._calculate_total_price(p, "dynamic")["total"]
                    if self._calculate_total_price(p, "dynamic")
                    else None
                )
                for h, p in today_raw.items()
            }
            tomorrow_total: dict[Any, float | None] = {
                h: (
                    self._calculate_total_price(p, "dynamic")["total"]
                    if self._calculate_total_price(p, "dynamic")
                    else None
                )
                for h, p in tomorrow_raw.items()
            }

            attrs.update(
                {
                    "today_prices": today_total,
                    "tomorrow_prices": tomorrow_total,
                }
            )
            today_avg = self.coordinator.data.get("today_avg")
            if today_avg is not None:
                total_avg: float | None = self._calculate_total_price(
                    today_avg, "dynamic"
                )
                if total_avg is not None:
                    attrs["today_average"] = self._convert_price(total_avg["total"])

        return attrs


class MinMaxPriceSensor(EnergyHubSensorEntity):
    """Sensor for the minimum or maximum energy price of the day (RCE)."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None

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
        total_price = self._calculate_total_price(val, "dynamic")
        return self._convert_price(total_price["total"] if total_price else None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose extra attributes for tests."""
        if not self.coordinator.data:
            return {"prices": {}}
        prices = self.coordinator.data.get(self._day, {})
        if not prices:
            return {"prices": {}}

        val = min(prices.values()) if self._mode == "min" else max(prices.values())
        matching_hours = [h for h, p in prices.items() if p == val]

        attrs: dict[str, Any] = {}
        if len(matching_hours) == 1:
            attrs["hour"] = f"{matching_hours[0]:02d}:00"
        else:
            attrs["hours"] = [f"{h:02d}:00" for h in matching_hours]

        return attrs


class AveragePriceSensor(EnergyHubSensorEntity):
    """Sensor for the average energy price of the day (RCE)."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = None

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

        if val is None:
            prices = self.coordinator.data.get(self._day, {})
            if prices:
                val = sum(prices.values()) / len(prices)

        if val is None:
            return None

        total_price = self._calculate_total_price(val, "dynamic")
        return self._convert_price(total_price["total"] if total_price else None)


class LowestPriceHourSensor(EnergyHubSensorEntity):
    """Sensor for the hour with the lowest energy price (RCE)."""

    _attr_icon = ICONS.get("lowest_price_hour")
    _attr_state_class = None

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

        if hour is None:
            prices = self.coordinator.data.get(self._day, {})
            if prices:
                min_price = min(prices.values())
                hour = [h for h, p in prices.items() if p == min_price][0]

        return f"{hour:02d}:00" if hour is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return price for this hour as an attribute."""
        if not self.coordinator.data:
            return {}
        prices = self.coordinator.data.get(self._day, {})
        if not prices:
            return {}
        min_price = min(prices.values())
        total_price = self._calculate_total_price(min_price, "dynamic")
        return {
            "price": self._convert_price(total_price["total"] if total_price else None)
        }


class HighestPriceHourSensor(EnergyHubSensorEntity):
    """Sensor for the hour with the highest energy price (RCE)."""

    _attr_icon = ICONS.get("highest_price_hour")
    _attr_state_class = None

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
        day: str,
    ) -> None:
        """Initialize the highest price hour sensor."""
        super().__init__(coordinator, entry)
        self._day = day
        self._attr_translation_key = f"highest_price_hour_{day}"
        self._attr_unique_id = f"highest_price_hour_{day}_{entry.entry_id}"

    @property
    def native_value(self) -> str | None:
        """Return the formatted hour string (e.g. '19:00')."""
        if not self.coordinator.data:
            return None
        hour = self.coordinator.data.get(f"{self._day}_max_hour")
        return f"{hour:02d}:00" if hour is not None else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return price for this hour as an attribute."""
        if not self.coordinator.data:
            return {}
        price = self.coordinator.data.get(f"{self._day}_max_price")
        total_price = self._calculate_total_price(price, "dynamic")
        return {
            "price": self._convert_price(total_price["total"] if total_price else None)
        }


class KSELoadSensor(EnergyHubSensorEntity):
    """Sensor for KSE energy load (zapotrzebowanie)."""

    _attr_icon = ICONS.get("kse_load")
    _attr_native_unit_of_measurement = "MW"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the load sensor."""
        super().__init__(coordinator, entry)
        self._attr_translation_key = "kse_load"
        self._attr_unique_id = f"kse_load_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        """Return the actual load."""
        return self.coordinator.data.get("load_actual")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return forecast and imbalance energy as attributes."""
        return {
            "load_forecast": self.coordinator.data.get("load_fcst"),
            "imbalance_energy": self.coordinator.data.get("imb_energy"),
        }


class KSEGenerationSensor(EnergyHubSensorEntity):
    """Sensor for KSE energy generation (OZE)."""

    _attr_icon = ICONS.get("kse_generation")
    _attr_native_unit_of_measurement = "MW"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: EnergyHubDataCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the generation sensor."""
        super().__init__(coordinator, entry)
        self._attr_translation_key = "kse_generation"
        self._attr_unique_id = f"kse_generation_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        """Return the sum of wind and PV generation."""
        wi = self.coordinator.data.get("gen_wi") or 0.0
        fv = self.coordinator.data.get("gen_fv") or 0.0
        return round(wi + fv, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed generation data as attributes."""
        return {
            "wind_generation": self.coordinator.data.get("gen_wi"),
            "pv_generation": self.coordinator.data.get("gen_fv"),
            "power_demand_kse": self.coordinator.data.get("kse_pow_dem"),
        }
