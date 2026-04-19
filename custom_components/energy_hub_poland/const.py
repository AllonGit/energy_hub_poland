"""Constants for the Energy Hub Poland integration."""

DOMAIN = "energy_hub_poland"
API_URL = "https://datahub.gkpge.pl/api/tge/quote"
PSE_API_URL = "https://api.raporty.pse.pl/api"

ICONS = {
    "recommendation": "mdi:lightbulb-auto",
    "kse_load": "mdi:transmission-tower",
    "kse_generation": "mdi:solar-power-variant",
    "price_spike": "mdi:chart-line-variant",
    "negative_price": "mdi:currency-pln-circle",
    "api_status": "mdi:cloud-check",
    "lowest_price_hour": "mdi:clock-outline",
    "highest_price_hour": "mdi:clock-alert-outline",
}

# Configuration keys
CONF_OPERATION_MODE = "operation_mode"
CONF_VAT_RATE = "vat_rate"
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

# Enabled tariffs
CONF_ENABLED_TARIFFS = "enabled_tariffs"

# Network fees
CONF_NETWORK_FIXED_FEE = "network_fixed_fee"
CONF_NETWORK_VARIABLE_FEE = "network_variable_fee"  # Global fallback

# Per-tariff network variable fees (for accurate comparisons)
CONF_NETWORK_VARIABLE_FEE_DYNAMIC = "network_variable_fee_dynamic"
CONF_NETWORK_VARIABLE_FEE_G11 = "network_variable_fee_g11"
CONF_NETWORK_VARIABLE_FEE_G12 = "network_variable_fee_g12"
CONF_NETWORK_VARIABLE_FEE_G12W = "network_variable_fee_g12w"
CONF_NETWORK_VARIABLE_FEE_G12N = "network_variable_fee_g12n"
CONF_NETWORK_VARIABLE_FEE_G13 = "network_variable_fee_g13"

# Units
UNIT_KWH = "kwh"
UNIT_MWH = "mwh"

# Update interval tuning
DEFAULT_UPDATE_INTERVAL_MINUTES = 5
ERROR_BACKOFF_THRESHOLD = 3
ERROR_BACKOFF_INTERVAL_MINUTES = 15

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

# PSE Sensor Constants
ATTR_LOAD_ACTUAL = "load_actual"
ATTR_LOAD_FCST = "load_fcst"
ATTR_GEN_WI = "gen_wi"
ATTR_GEN_FV = "gen_fv"
ATTR_KSE_POW_DEM = "kse_pow_dem"
ATTR_CEN_FCST = "cen_fcst"
ATTR_IMB_ENERGY = "imb_energy"
ATTR_IS_ACTIVE = "is_active"
