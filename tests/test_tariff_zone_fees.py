"""Regression tests for editing zonal network fees and exposing tariff rates."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.energy_hub_poland.config_flow import (
    EnergyHubPolandOptionsFlowHandler,
)
from custom_components.energy_hub_poland.const import (
    CONF_G12_SETTINGS,
    CONF_G12N_SETTINGS,
    CONF_G12W_SETTINGS,
    CONF_G13_SETTINGS,
    CONF_OPERATION_MODE,
    MODE_COMPARISON,
    UNIT_KWH,
)
from custom_components.energy_hub_poland.sensor import CurrentPriceSensor

ZONE_SETTINGS = (
    ("g12", CONF_G12_SETTINGS, ("peak", "offpeak")),
    ("g12w", CONF_G12W_SETTINGS, ("peak", "offpeak")),
    ("g12n", CONF_G12N_SETTINGS, ("peak", "offpeak")),
    ("g13", CONF_G13_SETTINGS, ("peak1", "peak2", "offpeak")),
)


def make_flow(config):
    entry = SimpleNamespace(data=config, options={})
    return EnergyHubPolandOptionsFlowHandler(entry)


@pytest.mark.asyncio
async def test_options_form_has_only_zonal_network_fees():
    flow = make_flow({CONF_OPERATION_MODE: MODE_COMPARISON})
    flow.async_show_form = MagicMock(side_effect=lambda **kwargs: kwargs)
    form = await flow.async_step_reconfigure()
    schema = form["data_schema"]

    for tariff, _, zones in ZONE_SETTINGS:
        assert f"{tariff}_settings_network_variable_fee" not in schema
        for zone in zones:
            assert f"{tariff}_settings_network_variable_fee_{zone}" in schema

    # G11 and G12r have a shared fee in their initial config flow.
    assert "g11_settings_network_variable_fee" in schema
    assert "g12r_settings_network_variable_fee" in schema


@pytest.mark.asyncio
@pytest.mark.parametrize("tariff, settings_key, zones", ZONE_SETTINGS)
async def test_options_store_zone_fees_in_tariff_settings(tariff, settings_key, zones):
    flow = make_flow({CONF_OPERATION_MODE: MODE_COMPARISON})
    flow.async_create_entry = MagicMock(side_effect=lambda **kwargs: kwargs)
    values = {
        f"{tariff}_settings_network_variable_fee_{zone}": (i + 1) / 10
        for i, zone in enumerate(zones)
    }
    result = await flow.async_step_reconfigure(values)
    saved = result["data"][settings_key]

    for zone, value in zip(zones, values.values()):
        assert saved[f"network_variable_fee_{tariff}_{zone}"] == value
    assert not any(k.startswith(f"{tariff}_settings_") for k in result["data"])


@pytest.mark.asyncio
async def test_legacy_single_network_fee_remains_available_to_other_tariffs():
    flow = make_flow({CONF_OPERATION_MODE: MODE_COMPARISON})
    flow.async_create_entry = MagicMock(side_effect=lambda **kwargs: kwargs)
    result = await flow.async_step_reconfigure(
        {"g12r_settings_network_variable_fee": 0.08}
    )
    assert result["data"]["g12r_settings"]["network_variable_fee"] == 0.08


@pytest.mark.parametrize("tariff, settings_key, zones", ZONE_SETTINGS)
def test_tariff_components_match_configured_zone_fees(tariff, settings_key, zones):
    settings = {}
    for i, zone in enumerate(zones):
        zone_name = {"peak1": "peak_1", "peak2": "peak_2"}.get(zone, zone)
        energy_field = f"price_{zone_name}"
        settings[energy_field] = 0.4 + i * 0.1
        settings[f"network_variable_fee_{tariff}_{zone}"] = 0.05 + i * 0.01

    sensor = CurrentPriceSensor.__new__(CurrentPriceSensor)
    sensor._tariff = tariff
    sensor._config = {settings_key: settings, "vat_rate": "23", "network_fixed_fee": 10}
    sensor._price_unit = UNIT_KWH
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = {}

    rates = sensor.extra_state_attributes["tariff_rates"]
    assert rates["unit"] == "PLN/kWh"
    assert rates["fixed_monthly_gross"] == pytest.approx(12.3)
    for i, zone in enumerate(zones):
        zone_name = {"peak1": "peak_1", "peak2": "peak_2"}.get(zone, zone)
        rate = rates[zone_name]
        assert rate["energy_net"] == pytest.approx(0.4 + i * 0.1)
        assert rate["distribution_net"] == pytest.approx(0.05 + i * 0.01)
        assert rate["total_gross"] == pytest.approx((0.45 + i * 0.11) * 1.23)


def test_existing_full_price_g12w_is_unchanged():
    sensor = CurrentPriceSensor.__new__(CurrentPriceSensor)
    sensor._tariff = "g12w"
    sensor._config = {
        CONF_G12W_SETTINGS: {"price_peak": 1.0003, "price_offpeak": 0.5127},
        "vat_rate": "23",
    }
    sensor._price_unit = UNIT_KWH
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = {}
    rates = sensor.extra_state_attributes["tariff_rates"]
    assert rates["peak"]["distribution_net"] == 0
    assert rates["offpeak"]["distribution_net"] == 0
    assert rates["peak"]["total_gross"] == pytest.approx(1.0003 * 1.23)
    assert rates["offpeak"]["total_gross"] == pytest.approx(0.5127 * 1.23)


def test_legacy_shared_fee_falls_back_for_each_zone():
    sensor = CurrentPriceSensor.__new__(CurrentPriceSensor)
    sensor._tariff = "g12"
    sensor._config = {
        CONF_G12_SETTINGS: {
            "price_peak": 0.9,
            "price_offpeak": 0.5,
            "network_variable_fee": 0.1,
        },
        "vat_rate": "23",
    }
    sensor._price_unit = UNIT_KWH
    sensor.coordinator = MagicMock()
    sensor.coordinator.data = {}
    rates = sensor.extra_state_attributes["tariff_rates"]
    assert rates["peak"]["distribution_net"] == pytest.approx(0.1)
    assert rates["offpeak"]["distribution_net"] == pytest.approx(0.1)
