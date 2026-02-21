"""Tests for EnergyHubDataCoordinator._parse_prices()."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from tests.common import ENTRY_ID, make_raw_api_data

from custom_components.energy_hub_poland.coordinator import EnergyHubDataCoordinator
from custom_components.energy_hub_poland import coordinator as coord_module

# The coordinator uses dt_util.DEFAULT_TIME_ZONE — patch it to a real tz
WARSAW = ZoneInfo("Europe/Warsaw")


def _make_coordinator():
    """Create a coordinator instance with minimal mocks."""
    coord = EnergyHubDataCoordinator.__new__(EnergyHubDataCoordinator)
    coord.config_entry = SimpleNamespace(entry_id=ENTRY_ID, data={}, options={})
    coord.api_client = MagicMock()
    coord.store = MagicMock()
    coord._cache_loaded = False
    coord._internal_data = {
        "today": None, "today_date": None,
        "tomorrow": None, "tomorrow_date": None,
    }
    coord.last_update_time = None
    coord.api_connected = True
    return coord


class TestParsePrice:
    def test_valid_24_records(self):
        coord = _make_coordinator()
        raw_data = make_raw_api_data(date(2025, 1, 15))
        with patch.object(coord_module.dt_util, "DEFAULT_TIME_ZONE", WARSAW):
            result = coord._parse_prices(raw_data)
        assert result is not None
        assert len(result) == 24
        assert result[0] == 0.3
        assert result[12] == 0.54

    def test_none_input(self):
        coord = _make_coordinator()
        assert coord._parse_prices(None) is None

    def test_empty_list(self):
        coord = _make_coordinator()
        assert coord._parse_prices([]) is None

    def test_not_a_list(self):
        coord = _make_coordinator()
        assert coord._parse_prices("not a list") is None

    def test_incomplete_data_returns_partial(self):
        coord = _make_coordinator()
        raw_data = make_raw_api_data(date(2025, 1, 15))[:12]
        with patch.object(coord_module.dt_util, "DEFAULT_TIME_ZONE", WARSAW):
            result = coord._parse_prices(raw_data)
        assert result is not None
        assert len(result) == 12

    def test_missing_price_attribute_defaults_to_zero(self):
        coord = _make_coordinator()
        raw_data = [
            {
                "date_time": "2025-01-15 10:00:00",
                "attributes": [{"name": "volume", "value": "100"}],
            }
        ]
        with patch.object(coord_module.dt_util, "DEFAULT_TIME_ZONE", WARSAW):
            result = coord._parse_prices(raw_data)
        assert result is not None
        assert result[10] == 0.0

    def test_invalid_date_format_returns_none(self):
        coord = _make_coordinator()
        raw_data = [
            {
                "date_time": "invalid-date",
                "attributes": [{"name": "price", "value": "300"}],
            }
        ]
        assert coord._parse_prices(raw_data) is None

    def test_missing_date_time_key_returns_none(self):
        coord = _make_coordinator()
        raw_data = [
            {
                "timestamp": "2025-01-15 10:00:00",
                "attributes": [{"name": "price", "value": "300"}],
            }
        ]
        assert coord._parse_prices(raw_data) is None

    def test_price_division_and_rounding(self):
        coord = _make_coordinator()
        raw_data = [
            {
                "date_time": f"2025-01-15 {h:02d}:00:00",
                "attributes": [{"name": "price", "value": "123.456"}],
            }
            for h in range(24)
        ]
        with patch.object(coord_module.dt_util, "DEFAULT_TIME_ZONE", WARSAW):
            result = coord._parse_prices(raw_data)
        assert result is not None
        # 123.456 / 1000 = 0.123456 → round(4) = 0.1235
        assert result[0] == 0.1235
