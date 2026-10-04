"""Test for disabled tariff in comparison mode (Issue fix)."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from custom_components.energy_hub_poland.const import (
    CONF_ENABLED_TARIFFS,
    CONF_ENERGY_SENSOR,
    CONF_G11_SETTINGS,
    CONF_G12_SETTINGS,
    CONF_G12N_SETTINGS,
    CONF_G12W_SETTINGS,
    CONF_G13_SETTINGS,
    CONF_NETWORK_VARIABLE_FEE,
    CONF_PRICE_UNIT,
    CONF_VAT_RATE,
    UNIT_KWH,
)
from custom_components.energy_hub_poland.sensor import RecommendationSensor

ENTRY_ID = "test_entry_id"


def _make_entry(**data_overrides):
    return SimpleNamespace(
        entry_id=ENTRY_ID,
        data=data_overrides.get("data", {}),
        options=data_overrides.get("options", {}),
        title="Test",
    )


class TestDisabledTariffRecommendation:
    """Test that disabled tariffs are not recommended even with 0 cost."""

    def _make_recommendation_sensor(self, config_data=None):
        """Create a RecommendationSensor with test configuration."""
        if config_data is None:
            config_data = {
                CONF_PRICE_UNIT: UNIT_KWH,
                CONF_VAT_RATE: "23",
                CONF_ENERGY_SENSOR: "sensor.energy",
                CONF_NETWORK_VARIABLE_FEE: 0.5,
                CONF_G11_SETTINGS: {"price_peak": 0.40},
                CONF_G12_SETTINGS: {
                    "price_peak": 0.50,
                    "price_offpeak": 0.30,
                    "hours_peak": "6-13,15-22",
                },
                CONF_G12W_SETTINGS: {
                    "price_peak": 0.45,
                    "price_offpeak": 0.28,
                    "hours_peak": "6-13,15-22",
                },
                CONF_G12N_SETTINGS: {
                    "price_peak": 0.48,
                    "price_offpeak": 0.32,
                    "hours_peak": "5-13,15-1",
                },
                CONF_G13_SETTINGS: {
                    "price_peak_1": 0.55,
                    "price_peak_2": 0.60,
                    "price_offpeak": 0.25,
                    "hours_peak_1_summer": "7-13",
                    "hours_peak_2_summer": "19-22",
                    "hours_peak_1_winter": "7-13",
                    "hours_peak_2_winter": "16-21",
                },
            }

        entry = _make_entry(
            data=config_data,
            options=config_data,
        )

        coordinator = MagicMock()
        coordinator.data = {
            "costs": {
                "dynamic": 10.0,
                "g11": 8.0,
                "g12": 7.0,
                "g12w": 6.5,
                "g12n": 7.5,
                "g13": 0.0,  # This is the problem: G13 not configured, cost is 0
            },
            "today": {0: 0.35, 1: 0.32},
        }

        sensor = RecommendationSensor.__new__(RecommendationSensor)
        sensor.coordinator = coordinator
        sensor._config = {**entry.data, **entry.options}
        sensor._attr_translation_key = "recommendation"
        sensor._attr_unique_id = f"recommendation_{entry.entry_id}"
        sensor.hass = MagicMock()
        sensor._energy_sensor_id = config_data.get(CONF_ENERGY_SENSOR)

        # This is the key fix: set enabled_tariffs
        sensor._enabled_tariffs = config_data.get(
            CONF_ENABLED_TARIFFS, ["dynamic", "g11", "g12", "g12w", "g12n", "g13"]
        )

        return sensor

    def test_disabled_g13_not_recommended_with_zero_cost(self):
        """
        Test that G13 is not recommended when:
        1. It's disabled (not in CONF_ENABLED_TARIFFS)
        2. Its cost is 0 (not configured)
        """

        enabled_tariffs = ["dynamic", "g11", "g12", "g12w", "g12n"]
        config = {
            CONF_ENABLED_TARIFFS: enabled_tariffs,
            CONF_PRICE_UNIT: UNIT_KWH,
            CONF_VAT_RATE: "23",
            CONF_ENERGY_SENSOR: "sensor.energy",
            CONF_NETWORK_VARIABLE_FEE: 0.5,
            CONF_G11_SETTINGS: {"price_peak": 0.40},
            CONF_G12_SETTINGS: {
                "price_peak": 0.50,
                "price_offpeak": 0.30,
                "hours_peak": "6-13,15-22",
            },
            CONF_G12W_SETTINGS: {
                "price_peak": 0.45,
                "price_offpeak": 0.28,
                "hours_peak": "6-13,15-22",
            },
            CONF_G12N_SETTINGS: {
                "price_peak": 0.48,
                "price_offpeak": 0.32,
                "hours_peak": "5-13,15-1",
            },
            CONF_G13_SETTINGS: {
                "price_peak_1": 0.55,
                "price_peak_2": 0.60,
                "price_offpeak": 0.25,
                "hours_peak_1_summer": "7-13",
                "hours_peak_2_summer": "19-22",
                "hours_peak_1_winter": "7-13",
                "hours_peak_2_winter": "16-21",
            },
        }

        sensor = self._make_recommendation_sensor(config)

        recommendation = sensor.native_value
        print(f"Recommendation: {recommendation}")
        print(f"Enabled tariffs: {sensor._enabled_tariffs}")
        print(f"Costs: {sensor.coordinator.data['costs']}")

        assert recommendation != "g13", (
            "BUG: G13 should not be recommended when disabled!"
        )
        assert recommendation == "g12w", (
            f"Expected recommendation 'g12w' but got '{recommendation}'"
        )

    def test_tariff_prices_return_cost_breakdown(self):
        """Test that tariff price values include split cost components and total."""
        sensor = self._make_recommendation_sensor()
        sensor.coordinator.data = {"today": {0: 0.35, 1: 0.32}}

        frozen_now = datetime(2024, 1, 1, 0, tzinfo=ZoneInfo("Europe/Warsaw"))
        with patch(
            "custom_components.energy_hub_poland.sensor.dt_util.now",
            return_value=frozen_now,
        ):
            prices = sensor._get_tariff_prices()

        assert "dynamic" in prices
        assert isinstance(prices["dynamic"], dict)
        assert set(prices["dynamic"]) == {"energy", "variable_fee", "vat", "total"}
        assert prices["dynamic"]["total"] > prices["dynamic"]["energy"]

    def test_attributes_exclude_disabled_tariffs(self):
        """Test that extra_state_attributes only includes enabled tariffs."""
        enabled_tariffs = ["dynamic", "g11", "g12", "g12w"]
        config = {
            CONF_ENABLED_TARIFFS: enabled_tariffs,
            CONF_PRICE_UNIT: UNIT_KWH,
            CONF_VAT_RATE: "23",
            CONF_ENERGY_SENSOR: "sensor.energy",
            CONF_NETWORK_VARIABLE_FEE: 0.5,
            CONF_G11_SETTINGS: {"price_peak": 0.40},
            CONF_G12_SETTINGS: {
                "price_peak": 0.50,
                "price_offpeak": 0.30,
                "hours_peak": "6-13,15-22",
            },
            CONF_G12W_SETTINGS: {
                "price_peak": 0.45,
                "price_offpeak": 0.28,
                "hours_peak": "6-13,15-22",
            },
            CONF_G12N_SETTINGS: {
                "price_peak": 0.48,
                "price_offpeak": 0.32,
                "hours_peak": "5-13,15-1",
            },
            CONF_G13_SETTINGS: {
                "price_peak_1": 0.55,
                "price_peak_2": 0.60,
                "price_offpeak": 0.25,
                "hours_peak_1_summer": "7-13",
                "hours_peak_2_summer": "19-22",
                "hours_peak_1_winter": "7-13",
                "hours_peak_2_winter": "16-21",
            },
        }

        sensor = self._make_recommendation_sensor(config)

        attrs = sensor.extra_state_attributes
        costs = attrs.get("costs", {})

        # Costs should only include enabled tariffs
        assert "dynamic" in costs
        assert "g11" in costs
        assert "g12" in costs
        assert "g12w" in costs
        # Disabled tariffs should NOT be in costs
        assert "g12n" not in costs, "g12n should not be in costs (disabled)"
        assert "g13" not in costs, "g13 should not be in costs (disabled)"

    def test_process_energy_delta_filters_disabled_tariffs(self):
        """Test that _process_energy_delta only processes enabled tariffs."""
        enabled_tariffs = ["dynamic", "g11", "g12"]
        config = {
            CONF_ENABLED_TARIFFS: enabled_tariffs,
            CONF_PRICE_UNIT: UNIT_KWH,
            CONF_VAT_RATE: "23",
            CONF_ENERGY_SENSOR: "sensor.energy",
            CONF_NETWORK_VARIABLE_FEE: 0.5,
            CONF_G11_SETTINGS: {"price_peak": 0.40},
            CONF_G12_SETTINGS: {
                "price_peak": 0.50,
                "price_offpeak": 0.30,
                "hours_peak": "6-13,15-22",
            },
            CONF_G12W_SETTINGS: {
                "price_peak": 0.45,
                "price_offpeak": 0.28,
                "hours_peak": "6-13,15-22",
            },
            CONF_G12N_SETTINGS: {
                "price_peak": 0.48,
                "price_offpeak": 0.32,
                "hours_peak": "5-13,15-1",
            },
            CONF_G13_SETTINGS: {
                "price_peak_1": 0.55,
                "price_peak_2": 0.60,
                "price_offpeak": 0.25,
                "hours_peak_1_summer": "7-13",
                "hours_peak_2_summer": "19-22",
                "hours_peak_1_winter": "7-13",
                "hours_peak_2_winter": "16-21",
            },
        }

        sensor = self._make_recommendation_sensor(config)

        # Mock _get_tariff_prices to return all prices
        mock_prices = {
            "dynamic": 0.35,
            "g11": 0.40,
            "g12": 0.50,
            "g12w": 0.45,
            "g12n": 0.48,
            "g13": 0.55,
        }

        sensor._get_tariff_prices = MagicMock(return_value=mock_prices)
        sensor.coordinator.async_update_costs = MagicMock()

        # Process energy delta
        sensor._process_energy_delta(1.5)

        # Verify that async_update_costs was called with filtered prices
        sensor.coordinator.async_update_costs.assert_called_once()
        call_args = sensor.coordinator.async_update_costs.call_args
        delta, prices = call_args[0]

        assert delta == 1.5
        # Only enabled tariffs should be passed
        assert "dynamic" in prices
        assert "g11" in prices
        assert "g12" in prices
        # Disabled tariffs should NOT be passed
        assert "g12w" not in prices, "g12w should not be in prices (disabled)"
        assert "g12n" not in prices, "g12n should not be in prices (disabled)"
        assert "g13" not in prices, "g13 should not be in prices (disabled)"
