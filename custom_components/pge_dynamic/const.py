"""Stałe dla integracji PGE Dynamic Energy."""
from datetime import timedelta

DOMAIN = "pge_dynamic"
CONF_TARIFF = "tariff"
UPDATE_INTERVAL = timedelta(minutes=60)

# URL wzięty bezpośrednio z Twojego url_generator.py
API_URL = "https://datahub.gkpge.pl/api/tge/quote"

TARIFF_OPTIONS = [
    "G1x (Taryfy gospodarstw domowych)",
    "C1x (Taryfy komercyjne / małe firmy)"
]