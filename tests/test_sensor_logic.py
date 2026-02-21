"""Tests for sensor logic (price sensors, cost sensors, energy delta)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from custom_components.energy_hub_poland.const import (
    CONF_G12_SETTINGS,
    CONF_G12W_SETTINGS,
    CONF_UNIT_TYPE,
    SENSOR_TYPE_DAILY,
    SENSOR_TYPE_TOTAL_INCREASING,
    UNIT_KWH,
    UNIT_MWH,
)

# Import sensor classes
from custom_components.energy_hub_poland.sensor import (
    AveragePriceSensor,
    CheapestHourSensor,
    DynamicPriceEntity,
    EnergyConsumerEntity,
    MinMaxPriceSensor,
    SavingsSensor,
)
from tests.common import ENTRY_ID, SAMPLE_PRICES_TODAY

CET = timezone(timedelta(hours=1))


def _make_entry(**data_overrides):
    return SimpleNamespace(
        entry_id=ENTRY_ID,
        data=data_overrides.get("data", {}),
        options=data_overrides.get("options", {}),
        title="Test",
    )


# ============================================================
# DynamicPriceEntity._scale_price
# ============================================================


class TestScalePrice:
    def _make_entity(self, unit_type=UNIT_KWH):
        entry = _make_entry(data={CONF_UNIT_TYPE: unit_type})
        coord = MagicMock()
        entity = DynamicPriceEntity.__new__(DynamicPriceEntity)
        entity.coordinator = coord
        entity._config = {**entry.data, **entry.options}
        return entity

    def test_kwh_passthrough(self):
        entity = self._make_entity(UNIT_KWH)
        assert entity._scale_price(0.5432) == 0.5432

    def test_mwh_multiplied(self):
        entity = self._make_entity(UNIT_MWH)
        # 0.5432 * 1000 = 543.2 → rounded to 2 decimal places
        assert entity._scale_price(0.5432) == 543.2

    def test_none_returns_none(self):
        entity = self._make_entity(UNIT_KWH)
        assert entity._scale_price(None) is None

    def test_kwh_custom_precision(self):
        entity = self._make_entity(UNIT_KWH)
        assert entity._scale_price(0.54321, precision=2) == 0.54


# ============================================================
# AveragePriceSensor
# ============================================================


class TestAveragePriceSensor:
    def _make_sensor(self, day_data, day="today", unit_type=UNIT_KWH):
        entry = _make_entry(data={CONF_UNIT_TYPE: unit_type})
        coord = MagicMock()
        coord.data = {"today": day_data} if day == "today" else {"tomorrow": day_data}

        sensor = AveragePriceSensor.__new__(AveragePriceSensor)
        sensor.coordinator = coord
        sensor._config = {**entry.data, **entry.options}
        sensor._day = day
        return sensor

    def test_average_of_prices(self):
        prices = {0: 0.10, 1: 0.20, 2: 0.30}
        sensor = self._make_sensor(prices)
        result = sensor.native_value
        # avg = 0.2, scale_price(0.2) = 0.2
        assert result == 0.2

    def test_full_day_average(self):
        sensor = self._make_sensor(dict(SAMPLE_PRICES_TODAY))
        result = sensor.native_value
        expected = sum(SAMPLE_PRICES_TODAY.values()) / 24
        assert result == round(expected, 4)

    def test_none_when_no_data(self):
        sensor = self._make_sensor(None)
        assert sensor.native_value is None

    def test_none_when_empty_prices(self):
        sensor = self._make_sensor({})
        assert sensor.native_value is None


# ============================================================
# CheapestHourSensor
# ============================================================


class TestCheapestHourSensor:
    def _make_sensor(self, day_data, day="today"):
        coord = MagicMock()
        coord.data = {day: day_data} if day_data is not None else {}

        sensor = CheapestHourSensor.__new__(CheapestHourSensor)
        sensor.coordinator = coord
        sensor._day = day
        return sensor

    def test_cheapest_hour(self):
        prices = {0: 0.50, 1: 0.30, 2: 0.40, 3: 0.35}
        sensor = self._make_sensor(prices)
        assert sensor.native_value == "01:00"

    def test_cheapest_hour_midnight(self):
        prices = {h: 0.50 + h * 0.01 for h in range(24)}
        sensor = self._make_sensor(prices)
        assert sensor.native_value == "00:00"

    def test_no_data_returns_none(self):
        coord = MagicMock()
        coord.data = None
        sensor = CheapestHourSensor.__new__(CheapestHourSensor)
        sensor.coordinator = coord
        sensor._day = "today"
        assert sensor.native_value is None

    def test_empty_prices_returns_none(self):
        sensor = self._make_sensor({})
        assert sensor.native_value is None


# ============================================================
# MinMaxPriceSensor
# ============================================================


class TestMinMaxPriceSensor:
    def _make_sensor(self, day_data, mode="min", day="today", unit_type=UNIT_KWH):
        entry = _make_entry(data={CONF_UNIT_TYPE: unit_type})
        coord = MagicMock()
        coord.data = {day: day_data}

        sensor = MinMaxPriceSensor.__new__(MinMaxPriceSensor)
        sensor.coordinator = coord
        sensor._config = {**entry.data, **entry.options}
        sensor._day = day
        sensor._mode = mode
        return sensor

    def test_min_price(self):
        prices = {0: 0.50, 1: 0.30, 2: 0.40}
        sensor = self._make_sensor(prices, mode="min")
        assert sensor.native_value == 0.3

    def test_max_price(self):
        prices = {0: 0.50, 1: 0.30, 2: 0.40}
        sensor = self._make_sensor(prices, mode="max")
        assert sensor.native_value == 0.5

    def test_none_when_no_data(self):
        sensor = self._make_sensor(None, mode="min")
        assert sensor.native_value is None

    def test_none_when_empty(self):
        sensor = self._make_sensor({}, mode="min")
        assert sensor.native_value is None

    def test_attributes_single_hour(self):
        prices = {0: 0.50, 1: 0.30, 2: 0.40}
        sensor = self._make_sensor(prices, mode="min")
        attrs = sensor.extra_state_attributes
        assert attrs["hour"] == "01:00"
        assert "hours" not in attrs

    def test_attributes_multiple_hours(self):
        prices = {0: 0.30, 1: 0.30, 2: 0.40}
        sensor = self._make_sensor(prices, mode="min")
        attrs = sensor.extra_state_attributes
        assert "hours" in attrs
        assert "00:00" in attrs["hours"]
        assert "01:00" in attrs["hours"]

    def test_attributes_empty_data(self):
        sensor = self._make_sensor(None, mode="min")
        assert sensor.extra_state_attributes == {"prices": {}}


# ============================================================
# EnergyConsumerEntity._get_energy_delta
# ============================================================


class TestGetEnergyDelta:
    def _make_consumer(self, sensor_type=SENSOR_TYPE_TOTAL_INCREASING):
        entity = EnergyConsumerEntity.__new__(EnergyConsumerEntity)
        entity._sensor_type = sensor_type
        entity._last_energy_reading = None
        return entity

    def test_first_reading_returns_zero(self):
        entity = self._make_consumer()
        delta = entity._get_energy_delta(100.0)
        assert delta == 0.0
        assert entity._last_energy_reading == 100.0

    def test_total_increasing_normal_increment(self):
        entity = self._make_consumer(SENSOR_TYPE_TOTAL_INCREASING)
        entity._last_energy_reading = 100.0
        delta = entity._get_energy_delta(105.0)
        assert delta == 5.0
        assert entity._last_energy_reading == 105.0

    def test_total_increasing_decrease_ignored(self):
        entity = self._make_consumer(SENSOR_TYPE_TOTAL_INCREASING)
        entity._last_energy_reading = 100.0
        delta = entity._get_energy_delta(50.0)
        assert delta == 0.0
        assert entity._last_energy_reading == 50.0

    def test_total_increasing_same_value(self):
        entity = self._make_consumer(SENSOR_TYPE_TOTAL_INCREASING)
        entity._last_energy_reading = 100.0
        delta = entity._get_energy_delta(100.0)
        assert delta == 0.0

    def test_daily_normal_increment(self):
        entity = self._make_consumer(SENSOR_TYPE_DAILY)
        entity._last_energy_reading = 5.0
        delta = entity._get_energy_delta(8.0)
        assert delta == 3.0

    def test_daily_reset_uses_current_value(self):
        entity = self._make_consumer(SENSOR_TYPE_DAILY)
        entity._last_energy_reading = 10.0
        delta = entity._get_energy_delta(2.0)
        assert delta == 2.0
        assert entity._last_energy_reading == 2.0

    def test_daily_reset_to_zero(self):
        entity = self._make_consumer(SENSOR_TYPE_DAILY)
        entity._last_energy_reading = 10.0
        delta = entity._get_energy_delta(0.0)
        # current < last → energy_delta = current = 0.0
        assert delta == 0.0


# ============================================================
# SavingsSensor._get_current_price
# ============================================================


class TestSavingsGetCurrentPrice:
    def _make_sensor(self, base_tariff, compare_tariff, coordinator_data, config=None):
        if config is None:
            config = {
                CONF_G12_SETTINGS: {
                    "price_peak": 0.80,
                    "price_offpeak": 0.50,
                    "hours_peak_winter": "8-14",
                },
                CONF_G12W_SETTINGS: {
                    "price_peak": 0.85,
                    "price_offpeak": 0.55,
                    "hours_peak_winter": "8-14",
                },
            }
        sensor = SavingsSensor.__new__(SavingsSensor)
        sensor._base_tariff = base_tariff
        sensor._compare_tariff = compare_tariff
        sensor._tariff = base_tariff
        sensor._config = config
        sensor.coordinator = MagicMock()
        sensor.coordinator.data = coordinator_data
        return sensor

    def test_dynamic_vs_g12_price_difference(self):
        """Savings = compare_price - base_price."""
        data = {"today": {10: 0.45}}

        sensor = self._make_sensor("dynamic", "g12", data)

        with patch("custom_components.energy_hub_poland.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 10, 0, 0, tzinfo=CET)
            price = sensor._get_current_price()
            # g12 peak (0.80) - dynamic (0.45) = 0.35
            assert price == pytest.approx(0.35, abs=0.01)

    def test_returns_none_when_base_price_missing(self):
        data = {"today": {}}

        sensor = self._make_sensor("dynamic", "g12", data)

        with patch("custom_components.energy_hub_poland.sensor.dt_util") as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 10, 0, 0, tzinfo=CET)
            price = sensor._get_current_price()
            assert price is None
