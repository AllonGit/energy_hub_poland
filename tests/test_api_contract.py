"""Contract tests — validate real API response format.

These tests call the live TGE/PSE API and verify the response
matches the schema expected by the integration. Run them periodically
(e.g. daily in CI) to detect API-side changes early.

Usage:
    pytest tests/test_api_contract.py -v -m contract
"""

from datetime import date, datetime

import aiohttp
import pytest

from custom_components.energy_hub_poland.api import EnergyHubApiClient

pytestmark = pytest.mark.contract


@pytest.fixture
async def api_client():
    # Use ThreadedResolver to avoid aiodns issues on some platforms
    resolver = aiohttp.resolver.ThreadedResolver()
    connector = aiohttp.TCPConnector(resolver=resolver)
    async with aiohttp.ClientSession(connector=connector) as session:
        yield EnergyHubApiClient(session)


class TestApiContract:
    """Verify real API still returns data in expected format."""

    @pytest.mark.asyncio
    async def test_api_returns_data_for_today(self, api_client):
        data = await api_client.async_get_prices(date.today())
        assert data is not None, "API returned None — endpoint may be down or changed"
        assert isinstance(data, list), f"Expected list, got {type(data)}"

    @pytest.mark.asyncio
    async def test_response_has_24_records(self, api_client):
        data = await api_client.async_get_prices(date.today())
        assert data is not None
        assert len(data) == 24, f"Expected 24 hourly records, got {len(data)}"

    @pytest.mark.asyncio
    async def test_record_has_date_time_field(self, api_client):
        data = await api_client.async_get_prices(date.today())
        assert data is not None
        record = data[0]
        msg = f"Missing 'date_time' key. Keys: {list(record.keys())}"
        assert "date_time" in record, msg

    @pytest.mark.asyncio
    async def test_date_time_format(self, api_client):
        data = await api_client.async_get_prices(date.today())
        assert data is not None
        dt_str = data[0]["date_time"]
        try:
            datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pytest.fail(
                f"date_time format changed: '{dt_str}' "
                f"does not match '%Y-%m-%d %H:%M:%S'"
            )

    @pytest.mark.asyncio
    async def test_record_has_attributes_array(self, api_client):
        data = await api_client.async_get_prices(date.today())
        assert data is not None
        record = data[0]
        msg = f"Missing 'attributes' key. Keys: {list(record.keys())}"
        assert "attributes" in record, msg
        assert isinstance(record["attributes"], list), "attributes should be a list"

    @pytest.mark.asyncio
    async def test_price_attribute_exists_and_is_numeric(self, api_client):
        data = await api_client.async_get_prices(date.today())
        assert data is not None
        record = data[0]
        price_attrs = [a for a in record["attributes"] if a.get("name") == "price"]
        assert len(price_attrs) == 1, (
            f"Expected 1 'price' attribute, found {len(price_attrs)}. "
            f"Available: {[a.get('name') for a in record['attributes']]}"
        )
        value = price_attrs[0]["value"]
        try:
            float(value)
        except (ValueError, TypeError):
            pytest.fail(f"Price value is not numeric: '{value}'")

    @pytest.mark.asyncio
    async def test_price_is_in_expected_range_mwh(self, api_client):
        """Sanity check — price in mWh should be roughly 50-2000 PLN/MWh."""
        data = await api_client.async_get_prices(date.today())
        assert data is not None
        record = data[0]
        price_attrs = [a for a in record["attributes"] if a.get("name") == "price"]
        assert price_attrs
        price = float(price_attrs[0]["value"])
        msg = f"Price {price} PLN/MWh outside expected range."
        assert -500 < price < 5000, msg

    @pytest.mark.asyncio
    async def test_full_parse_roundtrip(self, api_client):
        """End-to-end: fetch + parse should produce 24 hourly prices."""
        from unittest.mock import patch
        from zoneinfo import ZoneInfo

        from custom_components.energy_hub_poland import coordinator as coord_module
        from custom_components.energy_hub_poland.coordinator import (
            EnergyHubDataCoordinator,
        )

        data = await api_client.async_get_prices(date.today())
        assert data is not None

        coord = EnergyHubDataCoordinator.__new__(EnergyHubDataCoordinator)
        with patch.object(
            coord_module.dt_util, "DEFAULT_TIME_ZONE", ZoneInfo("Europe/Warsaw")
        ):
            prices = coord._parse_prices(data)

        assert prices is not None, "Parser returned None on real API data"
        assert len(prices) == 24, f"Parser returned {len(prices)} hours instead of 24"
        for hour, price in prices.items():
            assert isinstance(hour, int)
            assert 0 <= hour <= 23
            assert isinstance(price, float)
