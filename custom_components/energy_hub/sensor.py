# custom_components/energy_hub/sensor.py
"""Definicje sensorów dla integracji Energy Hub."""
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
    """Konfiguruje sensory na podstawie wpisu konfiguracyjnego."""
    coordinator: PGEDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    mode = entry.data.get(CONF_OPERATION_MODE)
    sensors = []

    if mode == MODE_DYNAMIC:
        sensors.extend(setup_dynamic_sensors(coordinator, entry))
    elif mode == MODE_G12:
        sensors.extend(setup_g12_sensors(coordinator, entry, is_g12w=False))
    elif mode == MODE_G12W:
        sensors.extend(setup_g12_sensors(coordinator, entry, is_g12w=True))
    elif mode == MODE_COMPARISON:
        sensors.extend(setup_comparison_sensors(coordinator, entry))

    async_add_entities(sensors, update_before_add=True)

def setup_dynamic_sensors(coordinator: PGEDataCoordinator, entry: ConfigEntry):
    """Tworzy sensory dla trybu taryfy dynamicznej."""
    sensors = [
        CurrentPriceSensor(coordinator, "dynamic"),
        MinMaxPriceSensor(coordinator, "today", "min"),
        MinMaxPriceSensor(coordinator, "today", "max"),
        MinMaxPriceSensor(coordinator, "tomorrow", "min"),
        MinMaxPriceSensor(coordinator, "tomorrow", "max"),
    ]
    
    if entry.data.get(CONF_ENERGY_SENSOR):
        sensors.extend([
            CostSensor(coordinator, entry, "dynamic", "daily"),
            CostSensor(coordinator, entry, "dynamic", "monthly")
        ])
        
    return sensors

def setup_g12_sensors(coordinator: PGEDataCoordinator, entry: ConfigEntry, is_g12w: bool):
    """Tworzy sensory dla trybów G12 i G12w."""
    tariff_name = "g12w" if is_g12w else "g12"
    sensors = [CurrentPriceSensor(coordinator, tariff_name, entry.data)]
    
    if entry.data.get(CONF_ENERGY_SENSOR):
        sensors.extend([
            CostSensor(coordinator, entry, tariff_name, "daily"),
            CostSensor(coordinator, entry, tariff_name, "monthly")
        ])
    return sensors

def setup_comparison_sensors(coordinator: PGEDataCoordinator, entry: ConfigEntry):
    """Tworzy sensory dla trybu porównawczego."""
    sensors = [
        CurrentPriceSensor(coordinator, "dynamic"),
        CurrentPriceSensor(coordinator, "g12", entry.data),
        CurrentPriceSensor(coordinator, "g12w", entry.data),
    ]
    if entry.data.get(CONF_ENERGY_SENSOR):
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
    """Bazowa encja dla sensorów."""
    _attr_has_entity_name = True

    def __init__(self, coordinator: PGEDataCoordinator):
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "energy_hub")},
            "name": "Energy Hub",
            "manufacturer": "PGE",
        }

class CurrentPriceSensor(EnergyHubEntity):
    """Sensor bieżącej ceny dla danej taryfy."""
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "PLN/kWh"

    def __init__(self, coordinator: PGEDataCoordinator, tariff: str, config: Optional[Dict] = None):
        super().__init__(coordinator)
        self._tariff = tariff
        self._config = config
        self._attr_name = f"Energy Hub Cena {tariff.upper()}"
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

class MinMaxPriceSensor(EnergyHubEntity):
    """Sensor ceny minimalnej/maksymalnej dla dnia dzisiejszego i jutrzejszego."""
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "PLN/kWh"

    def __init__(self, coordinator: PGEDataCoordinator, day: str, mode: str):
        super().__init__(coordinator)
        self._day = day
        self._mode = mode
        day_name = "Jutro" if day == "tomorrow" else "Dziś"
        mode_name = "Minimalna" if mode == "min" else "Maksymalna"
        self._attr_name = f"Energy Hub Cena {mode_name} {day_name}"
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
    """Sensor obliczający koszt dzienny i miesięczny."""
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
        
        self._attr_name = f"Energy Hub Koszt {tariff.upper()} {'Dziś' if period == 'daily' else 'Miesiąc'}"
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
        """Resetuje stan sensora o północy (dla dziennego) lub pierwszego dnia miesiąca."""
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
    """Sensor obliczający oszczędności (bilans) między dwiema taryfami."""
    
    def __init__(self, coordinator: PGEDataCoordinator, entry: ConfigEntry, base_tariff: str, compare_tariff: str, period: str):
        super().__init__(coordinator, entry, base_tariff, period) 
        self._base_tariff = base_tariff
        self._compare_tariff = compare_tariff
        
        self._attr_name = f"Energy Hub Bilans {base_tariff.upper()} vs {compare_tariff.upper()} {'Dziś' if period == 'daily' else 'Miesiąc'}"
        self._attr_unique_id = f"{DOMAIN}_savings_{base_tariff}_vs_{compare_tariff}_{period}"

    def _get_current_price(self):
        """Nadpisana metoda - oblicza różnicę cen."""
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
