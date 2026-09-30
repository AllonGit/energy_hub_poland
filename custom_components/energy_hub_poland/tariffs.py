"""Tariff pricing helpers for Energy Hub Poland."""

from datetime import datetime
from typing import Any, NamedTuple

from .const import ZONE_OFFPEAK, ZONE_PEAK
from .time_helpers import _POLISH_HOLIDAYS, is_peak_time, is_summer, parse_hour_ranges


class TariffPrice(NamedTuple):
    """Tariff price and active zone."""

    price: float | None
    zone: str | None = None


def _is_weekend_or_holiday(dt: datetime) -> bool:
    return dt.weekday() >= 5 or dt.date() in _POLISH_HOLIDAYS


def _get_peak_hours(
    dt: datetime,
    settings: dict[str, Any],
    *,
    summer_key: str,
    winter_key: str,
    default: str = "",
) -> list[tuple[int, int]]:
    hour_key = summer_key if is_summer(dt) else winter_key
    return parse_hour_ranges(settings.get(hour_key, default))


def get_current_g11_price(settings: dict[str, Any]) -> float | None:
    return settings.get("price_peak")


def get_current_g12_price(dt: datetime, settings: dict[str, Any]) -> TariffPrice:
    peak_hours = _get_peak_hours(
        dt,
        settings,
        summer_key="hours_peak_summer",
        winter_key="hours_peak_winter",
        default=settings.get("hours_peak", ""),
    )
    if is_peak_time(dt, peak_hours):
        return TariffPrice(settings.get("price_peak"), ZONE_PEAK)
    return TariffPrice(settings.get("price_offpeak"), ZONE_OFFPEAK)


def get_current_g12w_price(dt: datetime, settings: dict[str, Any]) -> TariffPrice:
    if _is_weekend_or_holiday(dt):
        return TariffPrice(settings.get("price_offpeak"), ZONE_OFFPEAK)
    return get_current_g12_price(dt, settings)


def get_current_g12n_price(dt: datetime, settings: dict[str, Any]) -> TariffPrice:
    if _is_weekend_or_holiday(dt):
        return TariffPrice(settings.get("price_offpeak"), ZONE_OFFPEAK)
    if (1 <= dt.hour < 5) or (13 <= dt.hour < 15):
        return TariffPrice(settings.get("price_offpeak"), ZONE_OFFPEAK)
    return TariffPrice(settings.get("price_peak"), ZONE_PEAK)


def get_current_g13_price(dt: datetime, settings: dict[str, Any]) -> TariffPrice:
    if _is_weekend_or_holiday(dt):
        return TariffPrice(settings.get("price_offpeak"), ZONE_OFFPEAK)

    p1_hours = _get_peak_hours(
        dt,
        settings,
        summer_key="hours_peak_1_summer",
        winter_key="hours_peak_1_winter",
        default="7-13",
    )
    p2_hours = _get_peak_hours(
        dt,
        settings,
        summer_key="hours_peak_2_summer",
        winter_key="hours_peak_2_winter",
        default="16-21",
    )

    if is_peak_time(dt, p1_hours):
        return TariffPrice(settings.get("price_peak_1"), ZONE_PEAK)
    if is_peak_time(dt, p2_hours):
        return TariffPrice(settings.get("price_peak_2"), ZONE_PEAK)
    return TariffPrice(settings.get("price_offpeak"), ZONE_OFFPEAK)
