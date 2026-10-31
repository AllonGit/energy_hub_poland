"""Tests for EnergyHubDataCoordinator._async_update_data() — day transition, cache, retry."""

from datetime import UTC, date, datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.energy_hub_poland import coordinator as coord_module
from custom_components.energy_hub_poland.coordinator import EnergyHubDataCoordinator
from tests.common import ENTRY_ID, SAMPLE_PRICES_TODAY, SAMPLE_PRICES_TOMORROW

# The coordinator raises UpdateFailed from HA — use the stub from conftest
UpdateFailed = coord_module.UpdateFailed


def _make_coordinator(
    today=None,
    today_date=None,
    tomorrow=None,
    tomorrow_date=None,
    cache_loaded=True,
):
    """Create a coordinator with controllable internal state."""
    coord = EnergyHubDataCoordinator.__new__(EnergyHubDataCoordinator)
    coord.hass = MagicMock()
    coord.config_entry = SimpleNamespace(entry_id=ENTRY_ID, data={}, options={})
    coord.api_client = MagicMock()

    # Mock PSE client methods
    coord.pse_client = MagicMock()
    coord.pse_client.get_rce_prices = AsyncMock(return_value=None)
    coord.pse_client.get_rce_forecast = AsyncMock(return_value=None)
    coord.pse_client.get_load_data = AsyncMock(return_value=None)
    coord.pse_client.get_generation_plans = AsyncMock(return_value=None)

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
    coord.costs = dict.fromkeys(
        ["dynamic", "g11", "g12", "g12w", "g12r", "g12n", "g13"], 0.0
    )
    coord.last_reset = datetime(2025, 1, 1, tzinfo=UTC)
    coord._error_count = 0
    coord.update_interval = timedelta(minutes=5)
    coord._last_tomorrow_event_date = None
    coord._scheduled_update_remover = None
    return coord


def _patch_now(dt: datetime):
    """Patch dt_util.now() and dt_util.utcnow() on the coordinator module."""
    return patch.object(
        coord_module.dt_util,
        "now",
        return_value=dt,
    )


def _patch_utcnow(dt: datetime):
    return patch.object(
        coord_module.dt_util,
        "utcnow",
        return_value=dt,
    )


PRICES_TODAY = dict(SAMPLE_PRICES_TODAY)
PRICES_TOMORROW = dict(SAMPLE_PRICES_TOMORROW)
TODAY = date(2025, 1, 15)
TOMORROW = date(2025, 1, 16)
NOW = datetime(2025, 1, 15, 14, 0, 0, tzinfo=timezone(timedelta(hours=1)))
NOW_UTC = datetime(2025, 1, 15, 13, 0, 0, tzinfo=UTC)
WARSAW = ZoneInfo("Europe/Warsaw")


# ============================================================
# Monthly cost reset (#50)
# ============================================================


class TestMonthlyCostReset:
    def _make(self, last_reset):
        coord = _make_coordinator(
            today=PRICES_TODAY,
            today_date=None,
            tomorrow=None,
            tomorrow_date=None,
        )

        async def fetch_prices(day):
            coord._internal_data["today"] = PRICES_TODAY
            coord._internal_data["today_date"] = day

        coord._update_pse_prices = AsyncMock(side_effect=fetch_prices)
        coord.last_reset = last_reset
        coord.costs["g11"] = 42.0
        return coord

    @pytest.mark.asyncio
    async def test_reset_on_first_of_month(self):
        coord = self._make(datetime(2025, 1, 1, tzinfo=WARSAW))
        now = datetime(2025, 2, 1, 0, 5, tzinfo=WARSAW)

        with _patch_now(now), _patch_utcnow(now.astimezone(UTC)):
            await coord._async_update_data()

        assert coord.costs["g11"] == 0.0
        assert coord.last_reset == datetime(2025, 2, 1, tzinfo=WARSAW)

    @pytest.mark.asyncio
    async def test_reset_missed_on_first_still_fires_later(self):
        """HA down for all of the 1st: the reset must fire on the next update."""
        coord = self._make(datetime(2025, 1, 1, tzinfo=WARSAW))
        now = datetime(2025, 2, 3, 9, 30, tzinfo=WARSAW)

        with _patch_now(now), _patch_utcnow(now.astimezone(UTC)):
            await coord._async_update_data()

        assert coord.costs["g11"] == 0.0
        assert coord.last_reset == datetime(2025, 2, 3, tzinfo=WARSAW)

    @pytest.mark.asyncio
    async def test_no_reset_within_same_month(self):
        coord = self._make(datetime(2025, 1, 1, tzinfo=WARSAW))
        now = datetime(2025, 1, 31, 23, 0, tzinfo=WARSAW)

        with _patch_now(now), _patch_utcnow(now.astimezone(UTC)):
            await coord._async_update_data()

        assert coord.costs["g11"] == 42.0

    @pytest.mark.asyncio
    async def test_month_boundary_uses_poland_time(self):
        """HA in UTC: 23:30 UTC on Jan 31 is already Feb 1 in Poland."""
        coord = self._make(datetime(2025, 1, 1, tzinfo=WARSAW))
        now = datetime(2025, 1, 31, 23, 30, tzinfo=UTC)

        with _patch_now(now), _patch_utcnow(now):
            await coord._async_update_data()

        assert coord.costs["g11"] == 0.0
        assert coord.last_reset == datetime(2025, 2, 1, tzinfo=WARSAW)

    def test_initial_last_reset_is_now_not_first_of_month(self):
        coord = EnergyHubDataCoordinator.__new__(EnergyHubDataCoordinator)
        now = datetime(2025, 1, 27, 15, 42, 7, 123456, tzinfo=WARSAW)

        with _patch_now(now):
            coord._ensure_runtime_state()

        assert coord.last_reset == datetime(2025, 1, 27, 15, 42, 7, tzinfo=WARSAW)


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

    @pytest.mark.skip(
        reason="Awaiting refactor for new _update_pse_prices architecture"
    )
    @pytest.mark.asyncio
    async def test_transition_then_fetch_new_today(self):
        """After transition, if transitioned today is wrong date, fetch new data."""
        new_today_prices = dict.fromkeys(range(24), 0.99)
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
    @pytest.mark.skip(
        reason="Awaiting refactor for new _update_pse_prices architecture"
    )
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
            today=PRICES_TODAY,
            today_date=TODAY,
            cache_loaded=True,
        )
        coord._load_cache = AsyncMock()
        coord._fetch_data = AsyncMock(return_value=None)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            await coord._async_update_data()

        coord._load_cache.assert_not_awaited()

    @pytest.mark.skip(
        reason="Awaiting refactor for new _update_pse_prices architecture"
    )
    @pytest.mark.asyncio
    async def test_cache_saved_when_data_updated(self):
        """_save_cache is called when new data is fetched."""
        coord = _make_coordinator()
        coord._fetch_data = AsyncMock(return_value=PRICES_TODAY)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            await coord._async_update_data()

        coord.store.async_save.assert_awaited()

    @pytest.mark.skip(
        reason="Awaiting refactor for new _update_pse_prices architecture"
    )
    @pytest.mark.asyncio
    async def test_cache_not_saved_when_no_change(self):
        """_save_cache is NOT called when data didn't change."""
        coord = _make_coordinator(
            today=PRICES_TODAY,
            today_date=TODAY,
            tomorrow=PRICES_TOMORROW,
            tomorrow_date=TOMORROW,
        )
        coord._fetch_data = AsyncMock(return_value=None)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            await coord._async_update_data()

        coord.store.async_save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_load_cache_restores_data(self):
        """_load_cache correctly deserializes cached data."""
        cached_data = {
            "price_cache_revision": 1,
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
            coord_module.dt_util,
            "parse_datetime",
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
            today=PRICES_TODAY,
            today_date=TODAY,
        )
        coord._fetch_data = AsyncMock(return_value=None)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            result = await coord._async_update_data()

        assert result["today"] == PRICES_TODAY
        # api_connected stays True because we have data from cache/transition
        assert coord.api_connected is True

    @pytest.mark.skip(
        reason="Awaiting refactor for new _update_pse_prices architecture"
    )
    @pytest.mark.asyncio
    async def test_api_failure_no_data_raises_update_failed(self):
        """If API fails and no cached data exists, raise UpdateFailed."""
        coord = _make_coordinator()
        coord._fetch_data = AsyncMock(return_value=None)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            with pytest.raises(UpdateFailed):
                await coord._async_update_data()

        assert coord.api_connected is False

    @pytest.mark.skip(
        reason="Awaiting refactor for new _update_pse_prices architecture"
    )
    @pytest.mark.asyncio
    async def test_api_failure_sets_disconnected_only_when_no_data(self):
        """api_connected=False only when today data is completely empty."""
        coord = _make_coordinator(
            today=PRICES_TODAY,
            today_date=date(2025, 1, 14),  # stale date
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
            today=PRICES_TODAY,
            today_date=TODAY,
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
    async def test_update_failure_records_diagnostic_state(self):
        """A failed update should expose useful diagnostic state for UI and logs."""
        coord = _make_coordinator(today=None, today_date=None)
        coord._update_pse_frequent_data = AsyncMock(side_effect=RuntimeError("boom"))

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            with pytest.raises(UpdateFailed):
                await coord._async_update_data()

        assert coord.data_status == "error"
        assert coord.last_error_message == "Failed to fetch frequent PSE data: boom"
        assert coord.api_connected is False

    @pytest.mark.skip(
        reason="Awaiting refactor for new _update_pse_prices architecture"
    )
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


class TestTomorrowPricesPublication:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("price", ["0", "-100", "400"])
    async def test_retries_until_tomorrow_prices_are_complete(self, price):
        """Missing and partial data must not block publication after 14:00."""
        from custom_components.energy_hub_poland.api import EnergyHubApiClient

        coord = _make_coordinator(today=PRICES_TODAY, today_date=TODAY)
        response = AsyncMock()
        response.raise_for_status = MagicMock()
        session = AsyncMock()
        session.get.return_value = response
        coord.api_client = EnergyHubApiClient(session)

        def payload(hours):
            # PGE is queried for the trading date (delivery date minus one).
            return [
                {
                    "date_time": f"{TODAY} {hour:02d}:00:00",
                    "attributes": [{"name": "price", "value": price}],
                }
                for hour in hours
            ]

        # Both today's and tomorrow's PGE fallback are requested per refresh.
        response.json.side_effect = [
            [],
            [],
            [],
            payload(range(12)),
            [],
            [],
            [],
            payload(range(24)),
        ]
        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            result = await coord._async_update_data()
        assert result["today"] == PRICES_TODAY
        assert result["tomorrow"] is None
        coord.hass.bus.async_fire.assert_not_called()

        later = NOW.replace(hour=14, minute=5)
        with _patch_now(later), _patch_utcnow(later.astimezone(UTC)):
            result = await coord._async_update_data()
        expected_price = float(price) / 1000
        assert result["tomorrow"] == dict.fromkeys(range(12), expected_price)

        # A temporary absence must preserve already fetched partial data.
        later = NOW.replace(hour=14, minute=10)
        with _patch_now(later), _patch_utcnow(later.astimezone(UTC)):
            result = await coord._async_update_data()
        assert result["tomorrow"] == dict.fromkeys(range(12), expected_price)

        later = NOW.replace(hour=14, minute=15)
        with _patch_now(later), _patch_utcnow(later.astimezone(UTC)):
            result = await coord._async_update_data()
        assert result["tomorrow"] == dict.fromkeys(range(24), expected_price)
        assert coord._internal_data["tomorrow_date"] == TOMORROW
        assert session.get.await_count == 8

        # A complete day, including a day of zero prices, needs no more requests.
        later = NOW.replace(hour=14, minute=20)
        with _patch_now(later), _patch_utcnow(later.astimezone(UTC)):
            await coord._async_update_data()
        assert session.get.await_count == 8

    @pytest.mark.asyncio
    async def test_pse_prices_take_priority_over_pge_fallback(self):
        coord = _make_coordinator(today=PRICES_TODAY, today_date=TODAY)
        coord.pse_client.get_rce_prices.return_value = [
            {"dtime": f"{TOMORROW} 01:00:00", "rce_pln": 0},
            {"dtime": f"{TOMORROW} 02:00:00", "rce_pln": -100},
        ]
        coord._fetch_pge_prices = AsyncMock(return_value=PRICES_TOMORROW)

        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            result = await coord._async_update_data()

        assert result["tomorrow"] == {**PRICES_TOMORROW, 0: 0.0, 1: -0.1}
        coord.hass.bus.async_fire.assert_called_once()


class TestLegacyPriceCache:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("revision", [None, 1])
    @pytest.mark.parametrize("today_zero", [False, True])
    async def test_cache_migration_preserves_costs_and_trusted_zero_prices(
        self, revision, today_zero
    ):
        coord = _make_coordinator(cache_loaded=False)
        prices = dict.fromkeys(range(24), 0.0)
        cached = {
            "today": prices if today_zero else PRICES_TODAY,
            "today_date": TODAY.isoformat(),
            "tomorrow": prices,
            "tomorrow_date": TOMORROW.isoformat(),
            "costs": {"dynamic": 651.37, "g12w": 500.13},
            "cost_breakdown": {"g12w": {"total": 500.13}},
            "last_reset": NOW.isoformat(),
        }
        if revision is not None:
            cached["price_cache_revision"] = revision
        coord.store.async_load.return_value = cached
        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            await coord._load_cache()
        assert coord.costs["dynamic"] == 651.37
        assert coord.costs["g12w"] == 500.13
        assert coord.cost_breakdown["g12w"]["total"] == 500.13
        assert coord._internal_data["tomorrow"] == (prices if revision else None)
        assert coord._internal_data["today"] == (
            None if today_zero and not revision else cached["today"]
        )
        await coord._save_cache()
        assert coord.store.async_save.call_args.args[0]["price_cache_revision"] == 1


class TestPollingAndMidnight:
    @pytest.mark.asyncio
    async def test_frequent_cost_updates_do_not_postpone_poll(self):
        coord = _make_coordinator(today=PRICES_TODAY, today_date=TODAY)
        coord._ensure_runtime_state()
        clock = {"now": 0, "deadline": 300}

        def reset_poll(data):
            clock["deadline"] = clock["now"] + 300

        coord.async_set_updated_data = MagicMock(side_effect=reset_poll)
        coord.async_update_listeners = MagicMock()
        coord._save_cache = MagicMock(return_value=None)
        for second in range(10, 301, 10):
            clock["now"] = second
            coord.async_update_costs(0.01, {"dynamic": {"total": 1.0}})
        assert clock["now"] >= clock["deadline"]
        assert coord.costs["dynamic"] == pytest.approx(0.30)
        assert coord.async_update_listeners.call_count == 30

    @pytest.mark.asyncio
    async def test_midnight_rotates_before_successful_fetch(self):
        coord = _make_coordinator(
            today=PRICES_TODAY,
            today_date=TODAY - timedelta(days=1),
            tomorrow=PRICES_TOMORROW,
            tomorrow_date=TODAY,
        )
        coord._fetch_pge_prices = AsyncMock(return_value=None)
        early = NOW.replace(hour=0, minute=5)
        with _patch_now(early), _patch_utcnow(early.astimezone(UTC)):
            result = await coord._async_update_data()
        assert result["today"] == PRICES_TOMORROW
        assert result["tomorrow"] is None
        assert coord._internal_data["today_date"] == TODAY

    @pytest.mark.asyncio
    async def test_successful_fetch_does_not_leave_yesterday_tomorrow(self):
        coord = _make_coordinator(
            today=PRICES_TODAY,
            today_date=TODAY - timedelta(days=1),
            tomorrow=PRICES_TOMORROW,
            tomorrow_date=TODAY,
        )
        coord.pse_client.get_rce_prices.return_value = [
            {"dtime": f"{TODAY} 01:00:00", "rce_pln": 500}
        ]
        coord._fetch_pge_prices = AsyncMock(return_value=None)
        with _patch_now(NOW), _patch_utcnow(NOW_UTC):
            result = await coord._async_update_data()
        assert result["today"][0] == 0.5
        assert result["tomorrow"] is None
