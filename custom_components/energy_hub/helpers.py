# custom_components/energy_hub/helpers.py
"""Funkcje pomocnicze dla integracji Energy Hub."""
import logging
from datetime import datetime
from typing import List, Tuple
import holidays

_LOGGER = logging.getLogger(__name__)
_POLISH_HOLIDAYS = holidays.PL()

def parse_hour_ranges(hour_ranges_str: str) -> List[Tuple[int, int]]:
    """Przetwarza ciąg znaków z zakresami godzin na listę krotek."""
    ranges: List[Tuple[int, int]] = []
    if not hour_ranges_str:
        return ranges
    try:
        parts = hour_ranges_str.split(',')
        for part in parts:
            start_str, end_str = part.strip().split('-')
            ranges.append((int(start_str), int(end_str)))
    except ValueError as e:
        _LOGGER.error("Nieprawidłowy format zakresu godzin: '%s'. Błąd: %s", hour_ranges_str, e)
        return []
    return ranges

def is_peak_time(dt: datetime, peak_hours: list) -> bool:
    """Sprawdza, czy podany czas (datetime) wpada w godziny szczytowe."""
    for start, end in peak_hours:
        if start <= dt.hour < end:
            return True
    return False

def get_current_g12_price(dt: datetime, settings: dict):
    """Zwraca aktualną cenę dla taryfy G12 na podstawie ustawień i czasu."""
    peak_hours = parse_hour_ranges(settings.get("hours_peak", ""))
    
    if is_peak_time(dt, peak_hours):
        return settings.get("price_peak")
    return settings.get("price_offpeak")

def get_current_g12w_price(dt: datetime, settings: dict):
    """Zwraca aktualną cenę dla taryfy G12w, uwzględniając weekendy i święta."""
    if dt.weekday() >= 5 or dt.date() in _POLISH_HOLIDAYS:
        return settings.get("price_offpeak")

    peak_hours = parse_hour_ranges(settings.get("hours_peak", ""))
    if is_peak_time(dt, peak_hours):
        return settings.get("price_peak")
    return settings.get("price_offpeak")
