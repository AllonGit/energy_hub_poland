from datetime import timedelta

DOMAIN = "pge_dynamic"
CONF_TARIFF = "tariff"
UPDATE_INTERVAL = timedelta(minutes=60)
API_URL = "https://datahub.gkpge.pl/api/tge/quote"
TARIFF_OPTIONS = ["G1x", "C1x"]