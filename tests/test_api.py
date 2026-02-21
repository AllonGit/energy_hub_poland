"""Tests for EnergyHubApiClient."""

import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.energy_hub_poland.api import EnergyHubApiClient
from custom_components.energy_hub_poland.const import API_URL


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def api_client(mock_session):
    return EnergyHubApiClient(mock_session)


class TestAsyncGetPrices:
    @pytest.mark.asyncio
    async def test_successful_request(self, api_client, mock_session):
        expected_data = [{"date_time": "2025-01-15 00:00:00", "attributes": []}]
        response = AsyncMock()
        response.json = AsyncMock(return_value=expected_data)
        response.raise_for_status = MagicMock()
        mock_session.get = AsyncMock(return_value=response)

        result = await api_client.async_get_prices(date(2025, 1, 15))
        assert result == expected_data

        # Verify URL construction
        call_args = mock_session.get.call_args
        url = call_args[0][0]
        assert API_URL in url
        assert "2025-01-15" in url
        assert "source=TGE" in url
        assert "contract=Fix_1" in url

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self, api_client, mock_session):
        mock_session.get = AsyncMock(side_effect=asyncio.TimeoutError())

        result = await api_client.async_get_prices(date(2025, 1, 15))
        assert result is None

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self, api_client, mock_session):
        response = AsyncMock()
        response.raise_for_status = MagicMock(side_effect=Exception("HTTP 500"))
        mock_session.get = AsyncMock(return_value=response)

        result = await api_client.async_get_prices(date(2025, 1, 15))
        assert result is None

    @pytest.mark.asyncio
    async def test_connection_error_returns_none(self, api_client, mock_session):
        mock_session.get = AsyncMock(side_effect=ConnectionError("Connection refused"))

        result = await api_client.async_get_prices(date(2025, 1, 15))
        assert result is None

    @pytest.mark.asyncio
    async def test_json_parse_error_returns_none(self, api_client, mock_session):
        response = AsyncMock()
        response.raise_for_status = MagicMock()
        response.json = AsyncMock(side_effect=ValueError("Invalid JSON"))
        mock_session.get = AsyncMock(return_value=response)

        result = await api_client.async_get_prices(date(2025, 1, 15))
        assert result is None

    @pytest.mark.asyncio
    async def test_url_contains_correct_date(self, api_client, mock_session):
        response = AsyncMock()
        response.json = AsyncMock(return_value=[])
        response.raise_for_status = MagicMock()
        mock_session.get = AsyncMock(return_value=response)

        await api_client.async_get_prices(date(2025, 12, 31))

        url = mock_session.get.call_args[0][0]
        assert "2025-12-31 00:00:00" in url
        assert "2025-12-31 23:59:59" in url

    @pytest.mark.asyncio
    async def test_user_agent_header(self, api_client, mock_session):
        response = AsyncMock()
        response.json = AsyncMock(return_value=[])
        response.raise_for_status = MagicMock()
        mock_session.get = AsyncMock(return_value=response)

        await api_client.async_get_prices(date(2025, 1, 15))

        headers = mock_session.get.call_args[1].get("headers", {})
        assert "User-Agent" in headers
