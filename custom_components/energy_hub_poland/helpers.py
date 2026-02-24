"""Helper functions for Energy Hub Poland."""

import logging
from datetime import datetime
from typing import Any

import holidays

_LOGGER = logging.getLogger(__package__)
_POLISH_HOLIDAYS = holidays.PL()


def parse_hour_ranges(hour_ranges_str: str) -> list[tuple[int, int]]:
    """
    Parse a string of comma-separated hour ranges into a list of (start, end) tuples.
    Format: '6-13,15-22' -> [(6, 13), (15, 22)]
    """
    ranges: list[tuple[int, int]] = []
    if not hour_ranges_str:
        return ranges
    try:
        parts = hour_ranges_str.split(",")
        for part in parts:
            if "-" not in part:
                continue
            start_str, end_str = part.strip().split("-")
            ranges.append((int(start_str), int(end_str)))
    except ValueError as e:
        _LOGGER.error("Invalid hour range format: '%s'. Error: %s", hour_ranges_str, e)
        return []
    return ranges


def is_peak_time(dt: datetime, peak_hours: list[tuple[int, int]]) -> bool:
    """
    Check if the hour of the given datetime falls within any of the peak hour ranges.
    Supports ranges that cross midnight (e.g., 22-6).
    """
    for start, end in peak_hours:
        if start < end:
            # Normal range (e.g., 6-13)
            if start <= dt.hour < end:
                return True
        else:
            # Range crossing midnight (e.g., 22-6)
            if dt.hour >= start or dt.hour < end:
                return True
    return False


def is_summer(dt: datetime) -> bool:
    """
    Determine if the given date falls within the 'Summer' season.
    Polish energy providers typically define summer as April 1st to September 30th.
    """
    month = dt.month
    return 4 <= month <= 9


def get_current_g11_price(settings: dict[str, Any]) -> float | None:
    """Get price for G11 tariff (always peak/flat price)."""
    return settings.get("price_peak")


def get_current_g12_price(dt: datetime, settings: dict[str, Any]) -> float | None:
    """
    Calculate current price for G12 tariff.
    Supports seasonal (Summer/Winter) peak hours if configured.
    """
    summer_hours = settings.get("hours_peak_summer")
    winter_hours = settings.get("hours_peak_winter")

    if summer_hours and winter_hours:
        hours_str = summer_hours if is_summer(dt) else winter_hours
    else:
        # Fallback to standard peak hours if seasonal ones are missing
        hours_str = settings.get("hours_peak", "")

    peak_hours = parse_hour_ranges(hours_str)

    if is_peak_time(dt, peak_hours):
        return settings.get("price_peak")
    return settings.get("price_offpeak")


def get_current_g12w_price(dt: datetime, settings: dict[str, Any]) -> float | None:
    """
    Calculate current price for G12w (Weekend) tariff.
    Weekends and Polish holidays are automatically considered off-peak.
    """
    if dt.weekday() >= 5 or dt.date() in _POLISH_HOLIDAYS:
        return settings.get("price_offpeak")

    return get_current_g12_price(dt, settings)


def get_current_g12n_price(dt: datetime, settings: dict[str, Any]) -> float | None:
    """
    Calculate current price for G12n tariff (PGE-specific logic).
    Off-peak: Night (01-05), Window (13-15), Sundays, and Holidays.
    """
    # Sundays and Holidays are always off-peak
    if dt.weekday() == 6 or dt.date() in _POLISH_HOLIDAYS:
        return settings.get("price_offpeak")

    # Mon-Sat: Off-peak windows
    if (1 <= dt.hour < 5) or (13 <= dt.hour < 15):
        return settings.get("price_offpeak")

    return settings.get("price_peak")


def get_current_g13_price(dt: datetime, settings: dict[str, Any]) -> float | None:
    """
    Calculate current price for G13 tariff (Tauron 3-zone).
    Off-peak: Saturdays, Sundays, Holidays, and specific weekday windows.
    Peak hours (1 and 2) shift between Summer and Winter seasons.
    """
    # Weekend and Holidays are always 'Other' (off-peak)
    if dt.weekday() >= 5 or dt.date() in _POLISH_HOLIDAYS:
        return settings.get("price_offpeak")

    summer = is_summer(dt)

    if summer:
        p1_hours = parse_hour_ranges(settings.get("hours_peak_1_summer", "7-13"))
        p2_hours = parse_hour_ranges(settings.get("hours_peak_2_summer", "19-22"))
    else:
        p1_hours = parse_hour_ranges(settings.get("hours_peak_1_winter", "7-13"))
        p2_hours = parse_hour_ranges(settings.get("hours_peak_2_winter", "16-21"))

    if is_peak_time(dt, p1_hours):
        return settings.get("price_peak_1")
    if is_peak_time(dt, p2_hours):
        return settings.get("price_peak_2")

    return settings.get("price_offpeak")
