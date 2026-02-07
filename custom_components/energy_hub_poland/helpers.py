# custom_components/energy_hub_poland/helpers.py
import logging
from datetime import datetime
from typing import Any

import holidays

_LOGGER = logging.getLogger(__package__)
_POLISH_HOLIDAYS = holidays.PL()


def parse_hour_ranges(hour_ranges_str: str) -> list[tuple[int, int]]:
    """Parse a string of hour ranges into a list of tuples."""
    ranges: list[tuple[int, int]] = []
    if not hour_ranges_str:
        return ranges
    try:
        parts = hour_ranges_str.split(",")
        for part in parts:
            start_str, end_str = part.strip().split("-")
            ranges.append((int(start_str), int(end_str)))
    except ValueError as e:
        _LOGGER.error(
            "Nieprawidłowy format zakresu godzin: '%s'. Błąd: %s", hour_ranges_str, e
        )
        return []
    return ranges


def is_peak_time(dt: datetime, peak_hours: list[tuple[int, int]]) -> bool:
    """Check if a given time is within the peak hours."""
    for start, end in peak_hours:
        if start <= dt.hour < end:
            return True
    return False


def get_current_g12_price(dt: datetime, settings: dict[str, Any]) -> float | None:
    """Calculate the current G12 price."""
    peak_hours = parse_hour_ranges(settings.get("hours_peak", ""))

    if is_peak_time(dt, peak_hours):
        return settings.get("price_peak")
    return settings.get("price_offpeak")


def get_current_g12w_price(dt: datetime, settings: dict[str, Any]) -> float | None:
    """Calculate the current G12w price."""
    if dt.weekday() >= 5 or dt.date() in _POLISH_HOLIDAYS:
        return settings.get("price_offpeak")

    peak_hours = parse_hour_ranges(settings.get("hours_peak", ""))
    if is_peak_time(dt, peak_hours):
        return settings.get("price_peak")
    return settings.get("price_offpeak")
