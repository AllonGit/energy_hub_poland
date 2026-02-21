"""Tests for EnergyHubDataCoordinator._async_update_data() — day transition, cache, retry."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.common import ENTRY_ID, SAMPLE_PRICES_TODAY, SAMPLE_PRICES_TOMORROW

from custom_components.energy_hub_poland.coordinator import EnergyHubDataCoordinator
from custom_components.energy_hub_poland import coordinator as coord_module

# The coordinator raises UpdateFailed from HA — use the stub from conftest
UpdateFailed = coord_module.UpdateFailed


def _make_coordinator(
    today=None, today_date=None,
    tomorrow=None, tomorrow_date=None,
    cache_loaded=True,
):
    """Create a coordinator with controllable internal state."""
    coord = EnergyHubDataCoordinator.__new__(EnergyHubDataCoordinator)
    coord.config_entry = SimpleNamespace(entry_id=ENTRY_ID, data={}, options={})
    coord.api_client = MagicMock()
    coord.store = AsyncMock()
    coord._cache_loaded = cache_loaded
    coord._internal_data = {
        "today": today,
        "today_date": today_date,
        "tomorrow": tomorrow,
        "tomorrow_date": tomorrow_date,
    }
    coord.last_update_time = None
    coord.api_connected = True
    return coord


def _patch_now(dt: datetime):
    """Patch dt_util.now() and dt_util.utcnow() on the coordinator module."""
    return patch.object(
        coord_module.dt_util, "now", return_value=dt,
    )


def _patch_utcnow(dt: datetime):
    return patch.object(
        coord_module.dt_util, "utcnow", return_value=dt,
    )


PRICES_TODAY = dict(SAMPLE_PRICES_TODAY)
PRICES_TOMORROW = dict(SAMPLE_PRICES_TOMORROW)
TODAY = date(2025, 1, 15)
TOMORROW = date(2025, 1, 16)
NOW = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone(timedelta(hours=1)))
NOW_UTC = datetime(2025, 1, 15, 13, 0, 0, tzinfo=timezone.utc)


# ============================================================
# Day transition
# ============================================================


class TestDayTransition:
    @pytest.mark.asyncio
    async def test_tomorrow_becomes_today_on_new_day(self):
        """When the date changes, yesterday's 'tomorrow' data moves to 'today'."""
        coord = _make_coordinator(
            today=PRICES_TODAY,
            today_date=date(2025, 1, 14),  # yesterday
            tomorrow=PRICES_TOMORROW,
            tomorrow_date=TODAY,
        )
        # _fetch_data returns None (API unavailable), but transition should still work
        coord._fetch_data = AsyncMock(return_value=None)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            result = await coord._async_update_data()

        # Today should now be what was tomorrow
        assert result["today"] == PRICES_TOMORROW
        assert coord._internal_data["today_date"] == TODAY
        # Tomorrow should be cleared
        assert coord._internal_data["tomorrow"] is None
        assert coord._internal_data["tomorrow_date"] is None

    @pytest.mark.asyncio
    async def test_no_transition_when_same_day(self):
        """No transition when today_date matches current date."""
        coord = _make_coordinator(
            today=PRICES_TODAY,
            today_date=TODAY,
            tomorrow=PRICES_TOMORROW,
            tomorrow_date=TOMORROW,
        )
        coord._fetch_data = AsyncMock(return_value=None)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            result = await coord._async_update_data()

        # Data should be unchanged
        assert result["today"] == PRICES_TODAY
        assert result["tomorrow"] == PRICES_TOMORROW

    @pytest.mark.asyncio
    async def test_transition_then_fetch_new_today(self):
        """After transition, if transitioned today is wrong date, fetch new data."""
        new_today_prices = {h: 0.99 for h in range(24)}
        coord = _make_coordinator(
            today=PRICES_TODAY,
            today_date=date(2025, 1, 14),
            tomorrow=None,  # no tomorrow data available
            tomorrow_date=None,
        )

        async def mock_fetch(fetch_date):
            if fetch_date == TODAY:
                return new_today_prices
            return None

        coord._fetch_data = AsyncMock(side_effect=mock_fetch)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            result = await coord._async_update_data()

        # After transition, tomorrow was None → today becomes None → fetch is called
        assert result["today"] == new_today_prices
        assert coord._internal_data["today_date"] == TODAY


# ============================================================
# Cache
# ============================================================


class TestCache:
    @pytest.mark.asyncio
    async def test_cache_loaded_on_first_run(self):
        """_load_cache is called on first update when cache_loaded is False."""
        coord = _make_coordinator(cache_loaded=False)
        coord._load_cache = AsyncMock()
        coord._fetch_data = AsyncMock(return_value=PRICES_TODAY)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            await coord._async_update_data()

        coord._load_cache.assert_awaited_once()
        assert coord._cache_loaded is True

    @pytest.mark.asyncio
    async def test_cache_not_loaded_on_subsequent_runs(self):
        """_load_cache is NOT called when cache_loaded is True."""
        coord = _make_coordinator(
            today=PRICES_TODAY, today_date=TODAY,
            cache_loaded=True,
        )
        coord._load_cache = AsyncMock()
        coord._fetch_data = AsyncMock(return_value=None)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            await coord._async_update_data()

        coord._load_cache.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cache_saved_when_data_updated(self):
        """_save_cache is called when new data is fetched."""
        coord = _make_coordinator()
        coord._fetch_data = AsyncMock(return_value=PRICES_TODAY)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            await coord._async_update_data()

        coord.store.async_save.assert_awaited()

    @pytest.mark.asyncio
    async def test_cache_not_saved_when_no_change(self):
        """_save_cache is NOT called when data didn't change."""
        coord = _make_coordinator(
            today=PRICES_TODAY, today_date=TODAY,
            tomorrow=PRICES_TOMORROW, tomorrow_date=TOMORROW,
        )
        coord._fetch_data = AsyncMock(return_value=None)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            await coord._async_update_data()

        coord.store.async_save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_load_cache_restores_data(self):
        """_load_cache correctly deserializes cached data."""
        cached_data = {
            "today": {"0": 0.30, "1": 0.32},
            "today_date": "2025-01-15",
            "tomorrow": {"0": 0.28},
            "tomorrow_date": "2025-01-16",
            "last_update_time": "2025-01-15T13:00:00+00:00",
            "api_connected": True,
        }
        coord = _make_coordinator()
        coord.store.async_load = AsyncMock(return_value=cached_data)
        coord.data = None

        with patch.object(
            coord_module.dt_util, "parse_datetime",
            side_effect=datetime.fromisoformat,
        ):
            await coord._load_cache()

        assert coord._internal_data["today"] == {0: 0.30, 1: 0.32}
        assert coord._internal_data["today_date"] == date(2025, 1, 15)
        assert coord._internal_data["tomorrow"] == {0: 0.28}
        assert coord._internal_data["tomorrow_date"] == date(2025, 1, 16)
        assert coord.data["today"] == {0: 0.30, 1: 0.32}

    @pytest.mark.asyncio
    async def test_load_cache_handles_empty_cache(self):
        """_load_cache handles None (no cache file)."""
        coord = _make_coordinator()
        coord.store.async_load = AsyncMock(return_value=None)

        await coord._load_cache()

        assert coord._internal_data["today"] is None

    @pytest.mark.asyncio
    async def test_load_cache_handles_corrupt_data(self):
        """_load_cache doesn't crash on corrupt cache."""
        coord = _make_coordinator()
        coord.store.async_load = AsyncMock(side_effect=Exception("corrupt"))

        await coord._load_cache()  # should not raise

        assert coord._internal_data["today"] is None


# ============================================================
# API failure / retry
# ============================================================


class TestApiFailure:
    @pytest.mark.asyncio
    async def test_api_failure_with_cached_today_still_works(self):
        """If API fails but we have cached today data, return it (no raise)."""
        coord = _make_coordinator(
            today=PRICES_TODAY, today_date=TODAY,
        )
        coord._fetch_data = AsyncMock(return_value=None)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            result = await coord._async_update_data()

        assert result["today"] == PRICES_TODAY
        # api_connected stays True because we have data from cache/transition
        assert coord.api_connected is True

    @pytest.mark.asyncio
    async def test_api_failure_no_data_raises_update_failed(self):
        """If API fails and no cached data exists, raise UpdateFailed."""
        coord = _make_coordinator()
        coord._fetch_data = AsyncMock(return_value=None)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            with pytest.raises(UpdateFailed):
                await coord._async_update_data()

        assert coord.api_connected is False

    @pytest.mark.asyncio
    async def test_api_failure_sets_disconnected_only_when_no_data(self):
        """api_connected=False only when today data is completely empty."""
        coord = _make_coordinator(
            today=PRICES_TODAY, today_date=date(2025, 1, 14),  # stale date
        )
        coord._fetch_data = AsyncMock(return_value=None)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            # Day transition moves tomorrow (None) to today → today becomes None
            # Then fetch fails → no data → UpdateFailed
            with pytest.raises(UpdateFailed):
                await coord._async_update_data()

        assert coord.api_connected is False

    @pytest.mark.asyncio
    async def test_tomorrow_fetch_failure_is_silent(self):
        """Failure to fetch tomorrow's data is not an error."""
        coord = _make_coordinator(
            today=PRICES_TODAY, today_date=TODAY,
        )

        async def mock_fetch(fetch_date):
            if fetch_date == TOMORROW:
                return None  # tomorrow not available yet
            return None

        coord._fetch_data = AsyncMock(side_effect=mock_fetch)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            result = await coord._async_update_data()

        # Should succeed — today data exists
        assert result["today"] == PRICES_TODAY
        assert result["tomorrow"] is None

    @pytest.mark.asyncio
    async def test_successful_fetch_sets_connected(self):
        """Successful API call sets api_connected=True."""
        coord = _make_coordinator()
        coord.api_connected = False
        coord._fetch_data = AsyncMock(return_value=PRICES_TODAY)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            await coord._async_update_data()

        assert coord.api_connected is True


# ============================================================
# _fetch_data
# ============================================================


class TestFetchData:
    @pytest.mark.asyncio
    async def test_fetch_returns_parsed_prices(self):
        """_fetch_data calls API and parses response."""
        coord = _make_coordinator()
        coord.api_client.async_get_prices = AsyncMock(return_value=[{"mock": "data"}])
        coord._parse_prices = MagicMock(return_value=PRICES_TODAY)

        with _patch_utcnow(NOW_UTC):
            result = await coord._fetch_data(TODAY)

        assert result == PRICES_TODAY
        assert coord.last_update_time == NOW_UTC

    @pytest.mark.asyncio
    async def test_fetch_returns_none_on_parse_failure(self):
        """_fetch_data returns None when parsing fails."""
        coord = _make_coordinator()
        coord.api_client.async_get_prices = AsyncMock(return_value=[{"bad": "data"}])
        coord._parse_prices = MagicMock(return_value=None)

        with _patch_utcnow(NOW_UTC):
            result = await coord._fetch_data(TODAY)

        assert result is None
        assert coord.last_update_time is None

    @pytest.mark.asyncio
    async def test_fetch_returns_none_on_api_failure(self):
        """_fetch_data returns None when API returns None."""
        coord = _make_coordinator()
        coord.api_client.async_get_prices = AsyncMock(return_value=None)
        coord._parse_prices = MagicMock(return_value=None)

        with _patch_utcnow(NOW_UTC):
            result = await coord._fetch_data(TODAY)

        assert result is None
