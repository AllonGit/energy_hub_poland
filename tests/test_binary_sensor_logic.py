"""Tests for binary sensor logic (PriceSpikeBinarySensor, ApiStatusBinarySensor)."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from custom_components.energy_hub_poland.binary_sensor import (
    ApiStatusBinarySensor,
    PriceSpikeBinarySensor,
)
from tests.common import ENTRY_ID, SAMPLE_PRICES_TODAY


def _make_spike_sensor(coordinator, entry=None):
    """Create PriceSpikeBinarySensor bypassing HA base __init__."""
    if entry is None:
        entry = SimpleNamespace(entry_id=ENTRY_ID, data={}, options={})
    sensor = PriceSpikeBinarySensor.__new__(PriceSpikeBinarySensor)
    sensor.coordinator = coordinator
    sensor._attr_translation_key = "price_spike"
    sensor._attr_unique_id = f"price_spike_{entry.entry_id}"
    sensor._attr_icon = "mdi:trending-up"
    return sensor


def _make_api_status_sensor(coordinator, entry=None):
    """Create ApiStatusBinarySensor bypassing HA base __init__."""
    if entry is None:
        entry = SimpleNamespace(entry_id=ENTRY_ID, data={}, options={})
    sensor = ApiStatusBinarySensor.__new__(ApiStatusBinarySensor)
    sensor.coordinator = coordinator
    sensor._attr_translation_key = "api_status"
    sensor._attr_unique_id = f"api_status_{entry.entry_id}"
    return sensor


# ============================================================
# PriceSpikeBinarySensor
# ============================================================


class TestPriceSpikeBinarySensor:
    def test_spike_detected(self):
        """Price significantly above average → True."""
        # Set up prices where hour 23 (0.76) is above 130% of avg
        # avg of SAMPLE_PRICES_TODAY ≈ 0.53, 130% ≈ 0.689
        # hour 23 = 0.76 > 0.689 → spike
        coord = MagicMock()
        coord.data = {"today": dict(SAMPLE_PRICES_TODAY)}

        sensor = _make_spike_sensor(coord)

        CET = timezone(timedelta(hours=1))
        with patch(
            "custom_components.energy_hub_poland.binary_sensor.dt_util"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 23, 0, 0, tzinfo=CET)
            assert sensor.is_on is True

    def test_no_spike(self):
        """Price near average → False."""
        coord = MagicMock()
        coord.data = {"today": dict(SAMPLE_PRICES_TODAY)}

        sensor = _make_spike_sensor(coord)

        CET = timezone(timedelta(hours=1))
        # hour 12 = 0.54, avg ≈ 0.53, 130% of avg ≈ 0.689 → 0.54 < 0.689
        with patch(
            "custom_components.energy_hub_poland.binary_sensor.dt_util"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 12, 0, 0, tzinfo=CET)
            assert sensor.is_on is False

    def test_no_coordinator_data(self):
        """No data at all → False."""
        coord = MagicMock()
        coord.data = None

        sensor = _make_spike_sensor(coord)
        assert sensor.is_on is False

    def test_empty_today_prices(self):
        """Today prices is empty dict → False."""
        coord = MagicMock()
        coord.data = {"today": {}}

        sensor = _make_spike_sensor(coord)
        assert sensor.is_on is False

    def test_current_hour_missing(self):
        """Current hour not in prices dict → False."""
        coord = MagicMock()
        coord.data = {"today": {10: 0.50, 11: 0.55}}

        sensor = _make_spike_sensor(coord)

        CET = timezone(timedelta(hours=1))
        with patch(
            "custom_components.energy_hub_poland.binary_sensor.dt_util"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 15, 0, 0, tzinfo=CET)
            assert sensor.is_on is False

    def test_avg_zero_price_positive(self):
        """Average is 0, current price > 0 → True."""
        coord = MagicMock()
        coord.data = {"today": {0: 0.0, 1: 0.0, 10: 0.01}}

        sensor = _make_spike_sensor(coord)

        CET = timezone(timedelta(hours=1))
        with patch(
            "custom_components.energy_hub_poland.binary_sensor.dt_util"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 10, 0, 0, tzinfo=CET)
            assert sensor.is_on is True

    def test_avg_zero_price_zero(self):
        """Average is 0, current price is also 0 → False."""
        coord = MagicMock()
        coord.data = {"today": {0: 0.0, 10: 0.0}}

        sensor = _make_spike_sensor(coord)

        CET = timezone(timedelta(hours=1))
        with patch(
            "custom_components.energy_hub_poland.binary_sensor.dt_util"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2025, 1, 15, 10, 0, 0, tzinfo=CET)
            assert sensor.is_on is False


# ============================================================
# ApiStatusBinarySensor
# ============================================================


class TestApiStatusBinarySensor:
    def test_connected(self):
        coord = MagicMock()
        coord.api_connected = True

        sensor = _make_api_status_sensor(coord)
        assert sensor.is_on is True

    def test_disconnected(self):
        coord = MagicMock()
        coord.api_connected = False

        sensor = _make_api_status_sensor(coord)
        assert sensor.is_on is False
