# custom_components/energy_hub_poland/helpers.py
import logging
from datetime import datetime
from typing import Any

import holidays

_LOGGER = logging.getLogger(__package__)
_POLISH_HOLIDAYS = holidays.PL()


def is_summer_time(dt: datetime) -> bool:
    """Check if the given datetime is in summer time (DST)."""
    dst = dt.dst()
    return dst is not None and dst.total_seconds() != 0


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


def get_seasonal_peak_hours_str(dt: datetime, settings: dict[str, Any]) -> str:
    """Get the peak hours string based on the season."""
    if is_summer_time(dt):
        val = settings.get("hours_peak_summer") or settings.get("hours_peak", "")
    else:
        val = settings.get("hours_peak_winter") or settings.get("hours_peak", "")
    return str(val)


def calculate_tariff_price(dt: datetime, settings: dict[str, Any]) -> float | None:
    """Calculate the tariff price based on time and settings."""
    peak_hours_str = get_seasonal_peak_hours_str(dt, settings)
    peak_hours = parse_hour_ranges(peak_hours_str)

    if is_peak_time(dt, peak_hours):
        return float(settings.get("price_peak", 0))
    return float(settings.get("price_offpeak", 0))


def get_current_g12_price(dt: datetime, settings: dict[str, Any]) -> float | None:
    """Calculate the current G12 price."""
    return calculate_tariff_price(dt, settings)


def get_current_g12w_price(dt: datetime, settings: dict[str, Any]) -> float | None:
    """Calculate the current G12w price."""
    if dt.weekday() >= 5 or dt.date() in _POLISH_HOLIDAYS:
        return settings.get("price_offpeak")

    return calculate_tariff_price(dt, settings)
