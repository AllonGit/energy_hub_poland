from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from datetime import datetime
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = [PGEPriceSensor(coordinator, hour) for hour in range(24)]
    sensors.append(PGECurrentPriceSensor(coordinator))
    async_add_entities(sensors)

class PGEPriceSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, hour):
        super().__init__(coordinator)
        self.hour = hour
        self._attr_name = f"PGE Cena {hour:02d}:00"
        self._attr_unique_id = f"{DOMAIN}_h_{hour}"
        self._attr_native_unit_of_measurement = "PLN/kWh"
        self._attr_device_class = SensorDeviceClass.MONETARY

    @property
    def native_value(self):
        return round(self.coordinator.data["hourly"].get(self.hour, 0), 4)

class PGECurrentPriceSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_name = "PGE Cena Aktualna"
        self._attr_unique_id = f"{DOMAIN}_current"
        self._attr_native_unit_of_measurement = "PLN/kWh"
        self._attr_device_class = SensorDeviceClass.MONETARY

    @property
    def native_value(self):
        hour = datetime.now().hour
        return round(self.coordinator.data["hourly"].get(hour, 0), 4)