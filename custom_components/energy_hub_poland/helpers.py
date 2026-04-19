"""Helper functions for Energy Hub Poland."""

import functools
import logging
from datetime import datetime

import holidays

_LOGGER = logging.getLogger(__package__)
_POLISH_HOLIDAYS = holidays.PL()


@functools.lru_cache(maxsize=32)
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
    Determine if the given date falls within the 'Summer' season for energy tariffs.
    Polish energy providers define summer as April 1st to September 30th (inclusive).
    This matches standard industry practice across major providers (PGE, Tauron, etc.).
    """
    month = dt.month
    return 4 <= month <= 9


# Tariff-specific pricing logic has been moved to tariffs.py.
