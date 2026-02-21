"""Tests for config_flow validation functions."""

from custom_components.energy_hub_poland.config_flow import (
    validate_entity_id,
    validate_hour_format,
)


# ============================================================
# validate_hour_format
# ============================================================


class TestValidateHourFormat:
    def test_single_range(self):
        assert validate_hour_format("6-13") is True

    def test_multiple_ranges(self):
        assert validate_hour_format("6-13,15-22") is True

    def test_three_ranges(self):
        assert validate_hour_format("6-8,10-14,16-22") is True

    def test_empty_string_is_valid(self):
        assert validate_hour_format("") is True

    def test_letters_invalid(self):
        assert validate_hour_format("abc") is False

    def test_missing_end(self):
        assert validate_hour_format("6-") is False

    def test_missing_start(self):
        assert validate_hour_format("-13") is False

    def test_double_comma(self):
        assert validate_hour_format("6-13,,15-22") is False

    def test_trailing_comma(self):
        assert validate_hour_format("6-13,") is False

    def test_two_digit_hours(self):
        assert validate_hour_format("08-11,15-22") is True

    def test_single_digit_hours(self):
        assert validate_hour_format("8-9") is True

    def test_spaces_not_allowed(self):
        # regex doesn't allow spaces
        assert validate_hour_format("6-13, 15-22") is False


# ============================================================
# validate_entity_id
# ============================================================


class TestValidateEntityId:
    def test_valid_sensor(self):
        assert validate_entity_id("sensor.energy_total") is True

    def test_empty_is_valid(self):
        assert validate_entity_id("") is True

    def test_binary_sensor_invalid(self):
        assert validate_entity_id("binary_sensor.api") is False

    def test_no_domain(self):
        assert validate_entity_id("energy") is False

    def test_sensor_dot_something(self):
        assert validate_entity_id("sensor.x") is True

    def test_other_domain(self):
        assert validate_entity_id("switch.lamp") is False
