"""Tariff pricing helpers for Energy Hub Poland."""

from datetime import datetime
from typing import Any

from .helpers import _POLISH_HOLIDAYS, is_peak_time, is_summer, parse_hour_ranges


def get_current_g11_price(settings: dict[str, Any]) -> float | None:
    return settings.get("price_peak")


def get_current_g12_price(dt: datetime, settings: dict[str, Any]) -> float | None:
    if is_summer(dt):
        hours_str = settings.get("hours_peak_summer") or settings.get("hours_peak", "")
    else:
        hours_str = settings.get("hours_peak_winter") or settings.get("hours_peak", "")

    peak_hours = parse_hour_ranges(hours_str)
    if is_peak_time(dt, peak_hours):
        return settings.get("price_peak")
    return settings.get("price_offpeak")


def get_current_g12w_price(dt: datetime, settings: dict[str, Any]) -> float | None:
    if dt.weekday() >= 5 or dt.date() in _POLISH_HOLIDAYS:
        return settings.get("price_offpeak")
    return get_current_g12_price(dt, settings)


def get_current_g12n_price(dt: datetime, settings: dict[str, Any]) -> float | None:
    if dt.weekday() == 6 or dt.date() in _POLISH_HOLIDAYS:
        return settings.get("price_offpeak")
    if (1 <= dt.hour < 5) or (13 <= dt.hour < 15):
        return settings.get("price_offpeak")
    return settings.get("price_peak")


def get_current_g13_price(dt: datetime, settings: dict[str, Any]) -> float | None:
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
