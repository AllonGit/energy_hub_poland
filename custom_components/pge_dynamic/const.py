from datetime import timedelta

DOMAIN = "pge_dynamic"
CONF_TARIFF = "tariff"
UPDATE_INTERVAL = timedelta(minutes=60)

# To musi tu być, bo __init__.py tego szuka:
API_URL = "https://api.datahub.pge.pl/pge/api/v1/dynamic-prices"

TARIFF_OPTIONS = [
    "G1x (Taryfy gospodarstw domowych)",
    "C1x (Taryfy komercyjne / małe firmy)"
]