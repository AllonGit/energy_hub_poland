"""Constants for the Energy Hub Poland integration."""

DOMAIN = "energy_hub_poland"
API_URL = "https://datahub.gkpge.pl/api/tge/quote"


CONF_OPERATION_MODE = "operation_mode"
CONF_ENERGY_SENSOR = "energy_sensor"
CONF_SENSOR_TYPE = "sensor_type"
CONF_G12_SETTINGS = "g12_settings"
CONF_G12W_SETTINGS = "g12w_settings"


CONF_PRICE_PEAK = "price_peak"
CONF_PRICE_OFFPEAK = "price_offpeak"
CONF_HOURS_PEAK = "hours_peak"


MODE_DYNAMIC = "dynamic"
MODE_G12 = "g12"
MODE_G12W = "g12w"
MODE_COMPARISON = "comparison"


SENSOR_TYPE_TOTAL_INCREASING = "total_increasing"
SENSOR_TYPE_DAILY = "daily"


DEFAULT_G12_PEAK_HOURS = "6-13,15-22"
DEFAULT_G12W_PEAK_HOURS = "6-13,15-22"
