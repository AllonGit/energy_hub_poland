# custom_components/energy_hub_poland/sensor.py
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from homeassistant.components.sensor import (
    SensorEntity, SensorDeviceClass, SensorStateClass, RestoreSensor
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN, CONF_OPERATION_MODE, CONF_ENERGY_SENSOR, CONF_SENSOR_TYPE,
    CONF_G12_SETTINGS, CONF_G12W_SETTINGS,
    MODE_DYNAMIC, MODE_G12, MODE_G12W, MODE_COMPARISON,
    SENSOR_TYPE_TOTAL_INCREASING, SENSOR_TYPE_DAILY
)
from .coordinator import PGEDataCoordinator
from .helpers import get_current_g12_price, get_current_g12w_price

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):

    coordinator: PGEDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    mode = entry.data.get(CONF_OPERATION_MODE)
    sensors = []

    if mode == MODE_DYNAMIC:
        sensors.extend(setup_dynamic_sensors(coordinator))
    elif mode == MODE_G12:
        sensors.extend(setup_g12_sensors(coordinator, entry, is_g12w=False))
    elif mode == MODE_G12W:
        sensors.extend(setup_g12_sensors(coordinator, entry, is_g12w=True))
    elif mode == MODE_COMPARISON:
        sensors.extend(setup_comparison_sensors(coordinator, entry))

    async_add_entities(sensors, update_before_add=True)


def setup_dynamic_sensors(coordinator: PGEDataCoordinator):

    return [
        CurrentPriceSensor(coordinator, "dynamic"),
        MinMaxPriceSensor(coordinator, "today", "min"),
        MinMaxPriceSensor(coordinator, "today", "max"),
        MinMaxPriceSensor(coordinator, "tomorrow", "min"),
        MinMaxPriceSensor(coordinator, "tomorrow", "max"),
    ]

def setup_g12_sensors(coordinator: PGEDataCoordinator, entry: ConfigEntry, is_g12w: bool):

    tariff_name = "g12w" if is_g12w else "g12"
    return [CurrentPriceSensor(coordinator, tariff_name, entry.data)]

def setup_comparison_sensors(coordinator: PGEDataCoordinator, entry: ConfigEntry):

    sensors = [
        CurrentPriceSensor(coordinator, "dynamic"),
        CurrentPriceSensor(coordinator, "g12", entry.data),
        CurrentPriceSensor(coordinator, "g12w", entry.data),
    ]
    if entry.data.get(CONF_ENERGY_SENSOR):
        sensors.append(RecommendationSensor(coordinator, entry))
        sensors.extend([
            SavingsSensor(coordinator, entry, "dynamic", "g12", "daily"),
            SavingsSensor(coordinator, entry, "dynamic", "g12", "monthly"),
            SavingsSensor(coordinator, entry, "dynamic", "g12w", "daily"),
            SavingsSensor(coordinator, entry, "dynamic", "g12w", "monthly"),
            SavingsSensor(coordinator, entry, "g12", "g12w", "daily"),
            SavingsSensor(coordinator, entry, "g12", "g12w", "monthly"),
        ])
    return sensors

class EnergyHubEntity(CoordinatorEntity, SensorEntity):

    _attr_has_entity_name = True

    def __init__(self, coordinator: PGEDataCoordinator):
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "energy_hub_poland")},
            "name": "Energy Hub Poland",
            "manufacturer": "PGE",
        }


class RecommendationSensor(EnergyHubEntity, RestoreSensor):
    _attr_icon = "mdi:lightbulb-auto"

    def __init__(self, coordinator: PGEDataCoordinator, entry: ConfigEntry):
        super().__init__(coordinator)
        self._config = entry.data
        self._energy_sensor_id = self._config.get(CONF_ENERGY_SENSOR)
        self._sensor_type = self._config.get(CONF_SENSOR_TYPE)

        self._attr_name = "Energy Hub Poland Rekomendacja"
        self._attr_unique_id = f"{DOMAIN}_recommendation"

        self._last_energy_reading: Optional[float] = None
        self._costs = {"dynamic": 0.0, "g12": 0.0, "g12w": 0.0}

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            if "costs" in last_state.attributes:
                saved_costs = last_state.attributes["costs"]
                self._costs = {k: float(v) for k, v in saved_costs.items()}

        if self._energy_sensor_id:
            self.async_on_remove(
                async_track_state_change_event(self.hass, [self._energy_sensor_id], self._handle_energy_change)
            )
            self.async_on_remove(
                async_track_time_change(self.hass, self._reset_state, day=1, hour=0, minute=0, second=5)
            )

    @callback
    def _reset_state(self, now: datetime):
        self._costs = {"dynamic": 0.0, "g12": 0.0, "g12w": 0.0}
        self.async_write_ha_state()

    @callback
    def _handle_energy_change(self, event):
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        try:
            current_energy = float(new_state.state)
        except ValueError:
            return

        energy_delta = 0.0
        if self._last_energy_reading is None:
            self._last_energy_reading = current_energy
            return

        if self._sensor_type == SENSOR_TYPE_TOTAL_INCREASING:
            if current_energy >= self._last_energy_reading:
                energy_delta = current_energy - self._last_energy_reading
        elif self._sensor_type == SENSOR_TYPE_DAILY:
            if current_energy >= self._last_energy_reading:
                energy_delta = current_energy - self._last_energy_reading
            else:
                energy_delta = current_energy

        self._last_energy_reading = current_energy

        if energy_delta > 0:
            now = dt_util.now()
            prices = {
                "dynamic": self.coordinator.data.get("today", {}).get(now.hour),
                "g12": get_current_g12_price(now, self._config.get(CONF_G12_SETTINGS, {})),
                "g12w": get_current_g12w_price(now, self._config.get(CONF_G12W_SETTINGS, {}))
            }

            for tariff, price in prices.items():
                if price is not None:
                    self._costs[tariff] += energy_delta * price
            
            self.async_write_ha_state()

    @property
    def native_value(self):
        if not self._energy_sensor_id:
            return "Skonfiguruj sensor energii"
        
        if all(v == 0.0 for v in self._costs.values()):
            return "Zbieranie danych..."
            
        best_tariff = min(self._costs, key=self._costs.get)
        return f"Najtańsza taryfa: {best_tariff.upper()}"

    @property
    def extra_state_attributes(self):
        dyn_cost = self._costs.get("dynamic", 0.0)
        return {
            "costs": {k: round(v, 2) for k, v in self._costs.items()},
            "oszczędność_g12": round(dyn_cost - self._costs.get("g12", 0.0), 2),
            "oszczędność_g12w": round(dyn_cost - self._costs.get("g12w", 0.0), 2),
            "oszczędność_dynamiczna": 0.0
        }

class CurrentPriceSensor(EnergyHubEntity):

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "PLN/kWh"

    def __init__(self, coordinator: PGEDataCoordinator, tariff: str, config: Optional[Dict] = None):
        super().__init__(coordinator)
        self._tariff = tariff
        self._config = config
        self._attr_name = f"Energy Hub Poland Cena {tariff.upper()}"
        self._attr_unique_id = f"{DOMAIN}_price_{tariff}"

    @property
    def native_value(self):
        now = dt_util.now()
        if self._tariff == "dynamic":
            prices = self.coordinator.data.get("today", {})
            return prices.get(now.hour) if prices else None
        elif self._tariff == "g12" and self._config:
            return get_current_g12_price(now, self._config.get(CONF_G12_SETTINGS, {}))
        elif self._tariff == "g12w" and self._config:
            return get_current_g12w_price(now, self._config.get(CONF_G12W_SETTINGS, {}))
        return None

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:

        if self._tariff == "dynamic":
            return {
                "today_prices": self.coordinator.data.get("today", {}),
                "tomorrow_prices": self.coordinator.data.get("tomorrow", {})
            }
        return {}

class MinMaxPriceSensor(EnergyHubEntity):

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "PLN/kWh"

    def __init__(self, coordinator: PGEDataCoordinator, day: str, mode: str):
        super().__init__(coordinator)
        self._day = day
        self._mode = mode
        day_name = "Jutro" if day == "tomorrow" else "Dziś"
        mode_name = "Minimalna" if mode == "min" else "Maksymalna"
        self._attr_name = f"Energy Hub Poland Cena {mode_name} {day_name}"
        self._attr_unique_id = f"{DOMAIN}_{mode}_{day}"

    @property
    def native_value(self):
        prices = self.coordinator.data.get(self._day, {})
        if not prices:
            return None
        return min(prices.values()) if self._mode == "min" else max(prices.values())

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        prices = self.coordinator.data.get(self._day, {})
        value = self.native_value
        if not prices or value is None:
            return {"prices": {}}

        hours = [f"{h:02d}:00" for h, p in prices.items() if p == value]
        attributes = {"prices": prices}
        if len(hours) == 1:
            attributes["hour"] = hours[0]
        else:
            attributes["hours"] = hours
        return attributes


class CostSensor(EnergyHubEntity, RestoreSensor):

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "PLN"
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(self, coordinator: PGEDataCoordinator, entry: ConfigEntry, tariff: str, period: str):
        super().__init__(coordinator)
        self._config = entry.data
        self._tariff = tariff
        self._period = period
        self._energy_sensor_id = self._config[CONF_ENERGY_SENSOR]
        self._sensor_type = self._config[CONF_SENSOR_TYPE]

        self._attr_name = f"Energy Hub Poland Koszt {tariff.upper()} {'Dziś' if period == 'daily' else 'Miesiąc'}"
        self._attr_unique_id = f"{DOMAIN}_cost_{tariff}_{period}"

        self._last_energy_reading: Optional[float] = None
        self._native_value = 0.0

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._native_value = float(last_state.state)

        self.async_on_remove(
            async_track_state_change_event(self.hass, [self._energy_sensor_id], self._handle_energy_change)
        )
        self.async_on_remove(
            async_track_time_change(self.hass, self._reset_state, hour=0, minute=0, second=5)
        )

    @callback
    def _reset_state(self, now: datetime):

        if self._period == "daily" or (self._period == "monthly" and now.day == 1):
            self._native_value = 0.0
            self.async_write_ha_state()

    @callback
    def _handle_energy_change(self, event):
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in ("unknown", "unavailable"):
            return

        current_energy = float(new_state.state)
        energy_delta = 0.0

        if self._last_energy_reading is None:
            self._last_energy_reading = current_energy
            return

        if self._sensor_type == SENSOR_TYPE_TOTAL_INCREASING:
            if current_energy >= self._last_energy_reading:
                energy_delta = current_energy - self._last_energy_reading

        elif self._sensor_type == SENSOR_TYPE_DAILY:
            if current_energy >= self._last_energy_reading:
                energy_delta = current_energy - self._last_energy_reading
            else:
                energy_delta = current_energy

        self._last_energy_reading = current_energy

        if energy_delta > 0:
            price = self._get_current_price()
            if price is not None:
                self._native_value += energy_delta * price
                self.async_write_ha_state()

    def _get_current_price(self):
        now = dt_util.now()
        if self._tariff == "dynamic":
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

    def __init__(self, coordinator: PGEDataCoordinator, entry: ConfigEntry, base_tariff: str, compare_tariff: str, period: str):
        super().__init__(coordinator, entry, base_tariff, period)
        self._base_tariff = base_tariff
        self._compare_tariff = compare_tariff

        self._attr_name = f"Energy Hub Poland Bilans {base_tariff.upper()} vs {compare_tariff.upper()} {'Dziś' if period == 'daily' else 'Miesiąc'}"
        self._attr_unique_id = f"{DOMAIN}_savings_{base_tariff}_vs_{compare_tariff}_{period}"

    def _get_current_price(self):

        now = dt_util.now()

        price_map = {
            "dynamic": self.coordinator.data.get("today", {}).get(now.hour),
            "g12": get_current_g12_price(now, self._config.get(CONF_G12_SETTINGS, {})),
            "g12w": get_current_g12w_price(now, self._config.get(CONF_G12W_SETTINGS, {}))
        }

        base_price = price_map.get(self._base_tariff)
        compare_price = price_map.get(self._compare_tariff)

        if base_price is None or compare_price is None:
            return None

        return compare_price - base_price
