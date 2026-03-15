"""Tests for custom_components/energy_hub_poland/helpers.py."""

from datetime import datetime
from zoneinfo import ZoneInfo

import holidays

from custom_components.energy_hub_poland.helpers import (
    get_current_g12_price,
    get_current_g12w_price,
    is_peak_time,
    is_summer,
    parse_hour_ranges,
)

# Use real Europe/Warsaw timezone so DST detection works properly
WARSAW = ZoneInfo("Europe/Warsaw")


# ============================================================
# is_summer_time
# ============================================================


class TestIsSummer:
    def test_summer_months(self):
        # July in Warsaw
        dt = datetime(2025, 7, 15, 12, 0, 0, tzinfo=WARSAW)
        assert is_summer(dt) is True

    def test_winter_months(self):
        # January in Warsaw
        dt = datetime(2025, 1, 15, 12, 0, 0, tzinfo=WARSAW)
        assert is_summer(dt) is False


# ============================================================
# parse_hour_ranges
# ============================================================


class TestParseHourRanges:
    def test_single_range(self):
        assert parse_hour_ranges("6-13") == [(6, 13)]

    def test_multiple_ranges(self):
        assert parse_hour_ranges("6-13,15-22") == [(6, 13), (15, 22)]

    def test_empty_string(self):
        assert parse_hour_ranges("") == []

    def test_ranges_with_spaces(self):
        assert parse_hour_ranges("6-13, 15-22") == [(6, 13), (15, 22)]

    def test_invalid_format_letters(self):
        assert parse_hour_ranges("abc") == []

    def test_invalid_no_dash(self):
        assert parse_hour_ranges("613") == []

    def test_single_number(self):
        assert parse_hour_ranges("6") == []

    def test_three_numbers_with_dashes(self):
        # "6-13-20" → split("-") gives 3 parts → ValueError on unpack
        assert parse_hour_ranges("6-13-20") == []


# ============================================================
# is_peak_time
# ============================================================


class TestIsPeakTime:
    def test_hour_in_range(self):
        dt = datetime(2025, 1, 15, 10, 0, 0)
        assert is_peak_time(dt, [(8, 14)]) is True

    def test_hour_outside_range(self):
        dt = datetime(2025, 1, 15, 7, 0, 0)
        assert is_peak_time(dt, [(8, 14)]) is False

    def test_hour_equals_start_inclusive(self):
        dt = datetime(2025, 1, 15, 8, 0, 0)
        assert is_peak_time(dt, [(8, 14)]) is True

    def test_hour_equals_end_exclusive(self):
        dt = datetime(2025, 1, 15, 14, 0, 0)
        assert is_peak_time(dt, [(8, 14)]) is False

    def test_empty_ranges(self):
        dt = datetime(2025, 1, 15, 10, 0, 0)
        assert is_peak_time(dt, []) is False

    def test_multiple_ranges_second_match(self):
        dt = datetime(2025, 1, 15, 16, 0, 0)
        assert is_peak_time(dt, [(8, 11), (15, 22)]) is True

    def test_multiple_ranges_no_match(self):
        dt = datetime(2025, 1, 15, 12, 0, 0)
        assert is_peak_time(dt, [(8, 11), (15, 22)]) is False


# ============================================================
# get_seasonal_peak_hours_str
# ============================================================




# ============================================================
# get_current_g12_price
# ============================================================


class TestGetCurrentG12Price:
    def test_peak_hour_returns_peak_price(self):
        dt = datetime(2025, 1, 15, 10, 0, 0, tzinfo=WARSAW)
        settings = {
            "hours_peak_winter": "8-14",
            "price_peak": 0.80,
            "price_offpeak": 0.50,
        }
        assert get_current_g12_price(dt, settings) == 0.80

    def test_offpeak_hour_returns_offpeak_price(self):
        dt = datetime(2025, 1, 15, 22, 0, 0, tzinfo=WARSAW)
        settings = {
            "hours_peak_winter": "8-14",
            "price_peak": 0.80,
            "price_offpeak": 0.50,
        }
        assert get_current_g12_price(dt, settings) == 0.50


# ============================================================
# get_current_g12w_price
# ============================================================


class TestGetCurrentG12wPrice:
    def test_weekend_returns_offpeak(self):
        # Saturday Jan 18, 2025
        dt = datetime(2025, 1, 18, 10, 0, 0, tzinfo=WARSAW)
        settings = {
            "hours_peak_winter": "8-14",
            "price_peak": 0.80,
            "price_offpeak": 0.50,
        }
        assert get_current_g12w_price(dt, settings) == 0.50

    def test_sunday_returns_offpeak(self):
        dt = datetime(2025, 1, 19, 10, 0, 0, tzinfo=WARSAW)
        settings = {
            "hours_peak_winter": "8-14",
            "price_peak": 0.80,
            "price_offpeak": 0.50,
        }
        assert get_current_g12w_price(dt, settings) == 0.50

    def test_polish_holiday_returns_offpeak(self):
        # Nov 11 is Polish Independence Day (Tuesday in 2025)
        dt = datetime(2025, 11, 11, 10, 0, 0, tzinfo=WARSAW)
        pl_holidays = holidays.PL(years=2025)
        assert dt.date() in pl_holidays  # sanity check
        settings = {
            "hours_peak_winter": "8-14",
            "price_peak": 0.80,
            "price_offpeak": 0.50,
        }
        assert get_current_g12w_price(dt, settings) == 0.50

    def test_weekday_peak_returns_peak_price(self):
        # Wednesday Jan 15, 2025
        dt = datetime(2025, 1, 15, 10, 0, 0, tzinfo=WARSAW)
        settings = {
            "hours_peak_winter": "8-14",
            "price_peak": 0.80,
            "price_offpeak": 0.50,
        }
        assert get_current_g12w_price(dt, settings) == 0.80

    def test_weekday_offpeak_returns_offpeak_price(self):
        # Wednesday 22:00
        dt = datetime(2025, 1, 15, 22, 0, 0, tzinfo=WARSAW)
        settings = {
            "hours_peak_winter": "8-14",
            "price_peak": 0.80,
            "price_offpeak": 0.50,
        }
        assert get_current_g12w_price(dt, settings) == 0.50
