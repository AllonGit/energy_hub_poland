"""Obsługa sensorów dla PGE Dynamic Energy."""
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from datetime import datetime

from .const import DOMAIN, CONF_MARGIN, CONF_FEE

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    """Konfiguracja sensorów."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    margin = entry.data.get(CONF_MARGIN, 0.0)
    fee = entry.data.get(CONF_FEE, 0.0)

    sensors = []

    # Sensory 00-23
    for hour in range(24):
        sensors.append(PGEHourlySensor(coordinator, hour, margin))

    # Statystyki
    sensors.append(PGEStatSensor(coordinator, "min", "Cena Minimalna", margin))
    sensors.append(PGEStatSensor(coordinator, "max", "Cena Maksymalna", margin))
    
    # Aktualna cena
    sensors.append(PGECurrentSensor(coordinator, "aktualna", "Cena Aktualna", margin))

    async_add_entities(sensors)

class PGESensorBase(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, margin):
        super().__init__(coordinator)
        self.margin = margin
        self._attr_currency = "PLN"
        self._attr_native_unit_of_measurement = "PLN/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:currency-eur"

    def calculate_gross(self, net_price):
        if net_price is None:
            return 0.0
        # (Cena giełdowa + Marża) * VAT 23%
        return round((net_price + self.margin) * 1.23, 4)

class PGEHourlySensor(PGESensorBase):
    def __init__(self, coordinator, hour, margin):
        super().__init__(coordinator, margin)
        self.hour = hour
        self._attr_name = f"PGE Cena {hour:02d}:00"
        self._attr_unique_id = f"{DOMAIN}_price_{hour}"

    @property
    def native_value(self):
        data = self.coordinator.data.get("hourly", {})
        return self.calculate_gross(data.get(self.hour))

class PGEStatSensor(PGESensorBase):
    def __init__(self, coordinator, key, name, margin):
        super().__init__(coordinator, margin)
        self.key = key
        self._attr_name = f"PGE {name}"
        self._attr_unique_id = f"{DOMAIN}_{key}"

    @property
    def native_value(self):
        val = self.coordinator.data.get(self.key)
        return self.calculate_gross(val)

class PGECurrentSensor(PGESensorBase):
    def __init__(self, coordinator, key, name, margin):
        super().__init__(coordinator, margin)
        self.key = key
        self._attr_name = f"PGE {name}"
        self._attr_unique_id = f"{DOMAIN}_{key}"
    
    @property
    def native_value(self):
        current_hour = datetime.now().hour
        data = self.coordinator.data.get("hourly", {})
        return self.calculate_gross(data.get(current_hour))