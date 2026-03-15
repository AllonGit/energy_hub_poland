"""Constants for the Energy Hub Poland integration."""

DOMAIN = "energy_hub_poland"
API_URL = "https://datahub.gkpge.pl/api/tge/quote"

# Configuration keys
CONF_OPERATION_MODE = "operation_mode"
CONF_ENERGY_SENSOR = "energy_sensor"
CONF_SENSOR_TYPE = "sensor_type"
CONF_G11_SETTINGS = "g11_settings"
CONF_G12_SETTINGS = "g12_settings"
CONF_G12W_SETTINGS = "g12w_settings"
CONF_G12N_SETTINGS = "g12n_settings"
CONF_G13_SETTINGS = "g13_settings"

CONF_PRICE_UNIT = "price_unit"
CONF_PROVIDER = "provider"
CONF_SPIKE_THRESHOLD = "spike_threshold"

CONF_PRICE_PEAK = "price_peak"
CONF_PRICE_OFFPEAK = "price_offpeak"
CONF_HOURS_PEAK = "hours_peak"

# G12 Seasonal Peak Hour Keys
CONF_HOURS_PEAK_SUMMER = "hours_peak_summer"
CONF_HOURS_PEAK_WINTER = "hours_peak_winter"

# G13 Specific Configuration Keys
CONF_PRICE_PEAK_1 = "price_peak_1"
CONF_PRICE_PEAK_2 = "price_peak_2"
CONF_HOURS_PEAK_1_SUMMER = "hours_peak_1_summer"
CONF_HOURS_PEAK_2_SUMMER = "hours_peak_2_summer"
CONF_HOURS_PEAK_1_WINTER = "hours_peak_1_winter"
CONF_HOURS_PEAK_2_WINTER = "hours_peak_2_winter"

# Operation Modes
MODE_DYNAMIC = "dynamic"
MODE_G11 = "g11"
MODE_G12 = "g12"
MODE_G12W = "g12w"
MODE_G12N = "g12n"
MODE_G13 = "g13"
MODE_COMPARISON = "comparison"

# Units
UNIT_KWH = "kwh"
UNIT_MWH = "mwh"

# Compatibility with tests
CONF_UNIT_TYPE = CONF_PRICE_UNIT

# Energy Providers (used for pre-filling standard hours)
PROVIDER_CUSTOM = "custom"
PROVIDER_PGE = "pge"
PROVIDER_TAURON = "tauron"
PROVIDER_ENEA = "enea"
PROVIDER_ENERGA = "energa"
PROVIDER_STOEN = "stoen"

# Sensor Types
SENSOR_TYPE_TOTAL_INCREASING = "total_increasing"
SENSOR_TYPE_DAILY = "daily"
