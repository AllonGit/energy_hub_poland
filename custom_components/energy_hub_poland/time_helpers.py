"""Time and tariff helper utilities for Energy Hub Poland."""

import functools
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import holidays

_LOGGER = logging.getLogger(__package__)
_POLISH_HOLIDAYS = holidays.PL()


def _parse_single_hour_range(part: str) -> tuple[int, int] | None:
    """Parse a single hour range string into a start/end tuple."""
    normalized_part = part.strip()
    if not normalized_part or "-" not in normalized_part:
        return None

    try:
        start_str, end_str = normalized_part.split("-", maxsplit=1)
        return int(start_str), int(end_str)
    except ValueError as exc:
        _LOGGER.error("Invalid hour range format: '%s'. Error: %s", part, exc)
        return None


@functools.lru_cache(maxsize=32)
def parse_hour_ranges(hour_ranges_str: str) -> list[tuple[int, int]]:
    """Parse a comma-separated list of hour ranges into tuples."""
    if not hour_ranges_str:
        return []

    return [
        parsed_range
        for part in hour_ranges_str.split(",")
        if (parsed_range := _parse_single_hour_range(part)) is not None
    ]


def is_peak_time(dt: datetime, peak_hours: list[tuple[int, int]]) -> bool:
    """Check whether a datetime falls within any of the provided hour ranges."""
    for start, end in peak_hours:
        if start < end:
            if start <= dt.hour < end:
                return True
            continue

        if dt.hour >= start or dt.hour < end:
            return True

    return False


def is_summer(dt: datetime) -> bool:
    """Return True when the date falls in the summer tariff season."""

    try:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        poland_dt = dt.astimezone(ZoneInfo("Europe/Warsaw"))
        return 4 <= poland_dt.month <= 9
    except Exception:
        # Fallback to naive month check if conversion fails for any reason
        return 4 <= dt.month <= 9
