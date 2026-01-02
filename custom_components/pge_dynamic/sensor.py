"""Sensory PGE Dynamic Energy."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from datetime import datetime
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = []
    for hour in range(24):
        sensors.append(PGEPriceSensor(coordinator, hour))
    sensors.append(PGECurrentPriceSensor(coordinator))
    async_add_entities(sensors)

class PGEPriceSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, hour):
        super().__init__(coordinator)
        self.hour = hour
        self._attr_name = f"PGE Cena {hour:02d}:00"
        self._attr_unique_id = f"{DOMAIN}_h_{hour}"
        self._attr_native_unit_of_measurement = "PLN/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        prices = self.coordinator.data.get("hourly", {})
        price = prices.get(self.hour)
        return round(price, 4) if price is not None else None

class PGECurrentPriceSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "PGE Cena Aktualna"
        self._attr_unique_id = f"{DOMAIN}_current"
        self._attr_native_unit_of_measurement = "PLN/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        hour = datetime.now().hour
        prices = self.coordinator.data.get("hourly", {})
        price = prices.get(hour)
        return round(price, 4) if price is not None else None