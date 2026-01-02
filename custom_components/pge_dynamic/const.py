"""Stałe dla integracji PGE Dynamic Energy."""
from datetime import timedelta

DOMAIN = "pge_dynamic"
NAME = "PGE Dynamic Energy"

CONF_TARIFF = "tariff"
CONF_MARGIN = "margin"
CONF_FEE = "fee"

# Domyślne wartości
DEFAULT_MARGIN = 0.0
DEFAULT_FEE = 0.0
UPDATE_INTERVAL = timedelta(minutes=15)

# URL do API PGE DataHub (zgodnie z Twoim wymogiem)
API_URL = "https://datahub.gkpge.pl/api/tge/quote"