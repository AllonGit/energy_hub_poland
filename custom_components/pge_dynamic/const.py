"""Stałe dla integracji PGE Dynamic Energy."""
from datetime import timedelta

DOMAIN = "pge_dynamic"
NAME = "PGE Dynamic Energy"
CONF_TARIFF = "tariff"

UPDATE_INTERVAL = timedelta(minutes=15)
API_URL = "https://datahub.gkpge.pl/api/tge/quote"