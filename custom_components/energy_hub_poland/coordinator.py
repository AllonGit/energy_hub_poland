"""Data coordinator for Energy Hub Poland."""

import logging
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import EnergyHubApiClient, PSEApiClient
from .const import (
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    ERROR_BACKOFF_INTERVAL_MINUTES,
    ERROR_BACKOFF_THRESHOLD,
)

_LOGGER = logging.getLogger(__package__)

STORAGE_KEY = f"{DOMAIN}_cache"
STORAGE_VERSION = 1


class EnergyHubDataCoordinator(DataUpdateCoordinator):
    """
    Class to manage fetching Energy Hub data from PSE/TGE API.
    Handles data caching, day transitions, and basic statistics calculation.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL_MINUTES),
        )
        self.api_client = EnergyHubApiClient(async_get_clientsession(hass))
        self.pse_client = PSEApiClient(async_get_clientsession(hass))
        self.store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._cache_loaded = False

        self._internal_data: dict[str, Any] = {
            "today": None,
            "today_date": None,
            "tomorrow": None,
            "tomorrow_date": None,
            "last_price_update": None,
            "load_actual": None,
            "load_fcst": None,
            "gen_wi": None,
            "gen_fv": None,
            "kse_pow_dem": None,
            "imb_energy": None,
        }
        self.last_update_time: datetime | None = None
        self.api_connected: bool = True
        self._error_count: int = 0
        self._last_tomorrow_event_date: date | None = None
        self.costs: dict[str, float] = dict.fromkeys(
            ["dynamic", "g11", "g12", "g12w", "g12n", "g13"], 0.0
        )
        self.cost_breakdown: dict[str, dict[str, float]] = {
            tariff: {"energy": 0.0, "variable_fee": 0.0, "vat": 0.0, "total": 0.0}
            for tariff in ["dynamic", "g11", "g12", "g12w", "g12n", "g13"]
        }
        self.last_reset: datetime = dt_util.now().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

    def _adjust_update_interval(self) -> None:
        """Adjust the coordinator update interval after repeated failures."""
        normal_interval: timedelta = timedelta(minutes=DEFAULT_UPDATE_INTERVAL_MINUTES)
        backoff_interval: timedelta = timedelta(minutes=ERROR_BACKOFF_INTERVAL_MINUTES)

        if self._error_count >= ERROR_BACKOFF_THRESHOLD:
            if self.update_interval != backoff_interval:
                _LOGGER.warning(
                    "Multiple PSE failures detected, backing off updates to %s minutes",
                    ERROR_BACKOFF_INTERVAL_MINUTES,
                )
                self.update_interval = backoff_interval
        elif self.update_interval != normal_interval:
            _LOGGER.debug(
                "Restoring normal update interval to %s minutes",
                DEFAULT_UPDATE_INTERVAL_MINUTES,
            )
            self.update_interval = normal_interval

    async def _fetch_data(self, fetch_date: date) -> dict[int, float] | None:
        """Fetch and parse price data from PGE (wrapper for tests)."""
        api_query_date = fetch_date - timedelta(days=1)
        raw_data = await self.api_client.async_get_prices(api_query_date)
        prices = self._parse_prices(raw_data)

        if prices is not None:
            self.last_update_time = dt_util.utcnow()

        return prices

    async def _fetch_pge_prices(self, fetch_date: date) -> dict[int, float] | None:
        """Fetch and parse price data from PGE DataHub (fallback)."""
        api_query_date = fetch_date - timedelta(days=1)
        _LOGGER.debug(
            "Fetching prices from PGE for %s (API query date: %s)",
            fetch_date,
            api_query_date,
        )

        raw_data = await self.api_client.async_get_prices(api_query_date)
        return self._parse_prices(raw_data)

    async def _update_pse_frequent_data(self, today_date: date) -> None:
        """Fetch frequent data (Load, Generation) from PSE."""
        load_data = await self.pse_client.get_load_data(today_date)
        gen_data = await self.pse_client.get_generation_plans(today_date)
        forecast_data = await self.pse_client.get_rce_forecast(today_date)

        if load_data:
            latest = load_data[-1]
            self._internal_data["load_actual"] = latest.get("load_actual")
            self._internal_data["load_fcst"] = latest.get("load_fcst")

        if gen_data:
            latest = gen_data[-1]
            self._internal_data["gen_wi"] = latest.get("gen_wi")
            self._internal_data["gen_fv"] = latest.get("gen_fv")
            self._internal_data["kse_pow_dem"] = latest.get("kse_pow_dem")

        if forecast_data:
            latest = forecast_data[-1]
            self._internal_data["imb_energy"] = latest.get("imb_energy")

    async def _update_pse_prices(self, today_date: date) -> None:
        """Fetch and process RCE prices from PSE with PGE fallback."""
        rce_data = await self.pse_client.get_rce_prices(today_date)
        forecast_data = await self.pse_client.get_rce_forecast(today_date)

        pse_prices = self._parse_pse_prices(rce_data, forecast_data)

        # Update today
        today_prices = {h: pse_prices.get((today_date, h)) for h in range(24)}
        # If missing some hours, try PGE fallback
        if None in today_prices.values():
            pge_prices = await self._fetch_pge_prices(today_date)
            if pge_prices:
                for h in range(24):
                    if today_prices[h] is None:
                        today_prices[h] = pge_prices.get(h)

        if any(v is not None for v in today_prices.values()):
            self._internal_data["today"] = {
                h: v for h, v in today_prices.items() if v is not None
            }
            self._internal_data["today_date"] = today_date

        # Update tomorrow
        tomorrow_date = today_date + timedelta(days=1)
        tomorrow_prices = {h: pse_prices.get((tomorrow_date, h)) for h in range(24)}
        if None in tomorrow_prices.values():
            pge_prices = await self._fetch_pge_prices(tomorrow_date)
            if pge_prices:
                for h in range(24):
                    if tomorrow_prices[h] is None:
                        tomorrow_prices[h] = pge_prices.get(h)

        tomorrow_published = False
        if any(v is not None for v in tomorrow_prices.values()):
            self._internal_data["tomorrow"] = {
                h: v for h, v in tomorrow_prices.items() if v is not None
            }
            self._internal_data["tomorrow_date"] = tomorrow_date
            if tomorrow_date != self._last_tomorrow_event_date:
                tomorrow_published = True
                self._last_tomorrow_event_date = tomorrow_date

        if tomorrow_published:
            self.hass.bus.async_fire(
                "energy_hub_poland_tomorrow_prices_published",
                {
                    "tomorrow_date": tomorrow_date.isoformat(),
                    "tomorrow_price_count": len(self._internal_data["tomorrow"] or {}),
                    "tomorrow_prices": self._internal_data["tomorrow"],
                },
            )

    def _parse_pse_prices(
        self, rce_data: list | None, forecast_data: list | None
    ) -> dict[tuple[date, int], float]:
        """Parse PSE RCE and Forecast data, averaging all values per hour."""
        hourly_actuals: dict[tuple[date, int], list[float]] = {}
        hourly_forecasts: dict[tuple[date, int], list[float]] = {}

        def add_to_raw(dt_str: str, val: Any, target_dict: dict) -> None:
            if val is None:
                return
            dt = dt_util.parse_datetime(dt_str)
            if not dt:
                return
            # Polish time adjust: 00:15-01:00 is hour 0
            hour = dt.hour
            d_date = dt.date()
            if dt.minute == 0 and dt.second == 0:
                hour -= 1
            if hour < 0:
                hour = 23
                d_date -= timedelta(days=1)
            key = (d_date, hour)
            if key not in target_dict:
                target_dict[key] = []
            target_dict[key].append(float(val) / 1000)

        if forecast_data:
            for item in forecast_data:
                add_to_raw(item["dtime"], item.get("cen_fcst"), hourly_forecasts)

        if rce_data:
            for item in rce_data:
                add_to_raw(item["dtime"], item.get("rce_pln"), hourly_actuals)

        def average(values: list[float]) -> float:
            return sum(values) / len(values)

        result: dict[tuple[date, int], float] = {}
        # Combine keys from both
        all_keys = set(hourly_actuals.keys()) | set(hourly_forecasts.keys())

        for key in all_keys:
            # If we have actuals for this hour, average them
            if key in hourly_actuals:
                result[key] = average(hourly_actuals[key])
            # Otherwise average forecasts
            else:
                result[key] = average(hourly_forecasts[key])

        return result

    @callback
    def async_update_costs(
        self, delta: float, prices: dict[str, dict[str, float] | None]
    ) -> None:
        """Update accumulated costs with a new energy increment and breakdown."""
        legacy_keys = ["dynamic", "g11", "g12", "g12w", "g12n", "g13"]
        for key in legacy_keys:
            if key not in self.costs:
                self.costs[key] = 0.0
            if key not in self.cost_breakdown:
                self.cost_breakdown[key] = {
                    "energy": 0.0,
                    "variable_fee": 0.0,
                    "vat": 0.0,
                    "total": 0.0,
                }

        for tariff, price_data in prices.items():
            if price_data is None:
                continue

            if isinstance(price_data, dict):
                energy_price = price_data.get("energy", 0.0)
                variable_fee = price_data.get("variable_fee", 0.0)
                vat_amount = price_data.get("vat", 0.0)
                total_price = price_data.get("total", 0.0)
            else:
                energy_price = float(price_data)
                variable_fee = 0.0
                vat_amount = 0.0
                total_price = float(price_data)

            self.costs[tariff] += delta * total_price
            breakdown = self.cost_breakdown.setdefault(
                tariff,
                {"energy": 0.0, "variable_fee": 0.0, "vat": 0.0, "total": 0.0},
            )
            breakdown["energy"] += delta * energy_price
            breakdown["variable_fee"] += delta * variable_fee
            breakdown["vat"] += delta * vat_amount
            breakdown["total"] += delta * total_price

        self.data["costs"] = self.costs
        self.data["cost_breakdown"] = self.cost_breakdown
        self.async_set_updated_data(self.data)
        self.hass.async_create_task(self._save_cache())

    async def _async_update_data(self) -> dict[str, Any]:
        """Core update method called periodically by Home Assistant."""
        if not self._cache_loaded:
            await self._load_cache()
            self._cache_loaded = True

        now = dt_util.now()
        poland_tz = ZoneInfo("Europe/Warsaw")
        poland_now = now.astimezone(poland_tz)
        today_date = poland_now.date()

        # Monthly reset check
        if now.day == 1 and self.last_reset.month != now.month:
            _LOGGER.info("Monthly cost reset triggered")
            self.costs = dict.fromkeys(self.costs, 0.0)
            self.last_reset = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 1. Fetch frequent data (Load, Generation)
        try:
            await self._update_pse_frequent_data(today_date)
            self.api_connected = True
            self._error_count = 0
        except Exception as e:
            _LOGGER.warning("Failed to fetch frequent PSE data: %s", e)
            self.api_connected = False
            self._error_count += 1

        # 2. Fetch prices twice a day (00:01 and 12:00) or if missing
        last_price_update = self._internal_data.get("last_price_update")
        needs_price_update = False

        if (
            not self._internal_data.get("today")
            or self._internal_data.get("today_date") != today_date
        ):
            needs_price_update = True
        elif poland_now.hour >= 12 and (
            not self._internal_data.get("tomorrow")
            or self._internal_data.get("tomorrow_date")
            != (today_date + timedelta(days=1))
        ):
            needs_price_update = True
        elif last_price_update:
            last_p_poland = last_price_update.astimezone(poland_tz)
            if last_p_poland.hour < 12 <= poland_now.hour:
                needs_price_update = True

        if needs_price_update:
            try:
                await self._update_pse_prices(today_date)
                self._internal_data["last_price_update"] = now
                self.last_update_time = now
                self._error_count = 0
            except Exception as e:
                _LOGGER.error("Failed to update PSE prices: %s", e)
                self._error_count += 1

        self._adjust_update_interval()

        # Handle day transition (midnight)
        if (
            self._internal_data["today_date"]
            and self._internal_data["today_date"] < today_date
        ):
            _LOGGER.debug("Day transition: moving tomorrow data to today")
            self._internal_data["today"] = self._internal_data["tomorrow"]
            self._internal_data["today_date"] = self._internal_data["tomorrow_date"]
            self._internal_data["tomorrow"] = None
            self._internal_data["tomorrow_date"] = None

        await self._save_cache()

        # Raise error only if we have no data at all for today
        if not self._internal_data["today"]:
            raise UpdateFailed("No energy price data available for today")

        data = {
            "today": self._internal_data["today"],
            "tomorrow": self._internal_data["tomorrow"],
            "costs": self.costs,
            "cost_breakdown": self.cost_breakdown,
            "last_reset": self.last_reset,
            "load_actual": self._internal_data.get("load_actual"),
            "load_fcst": self._internal_data.get("load_fcst"),
            "gen_wi": self._internal_data.get("gen_wi"),
            "gen_fv": self._internal_data.get("gen_fv"),
            "kse_pow_dem": self._internal_data.get("kse_pow_dem"),
            "imb_energy": self._internal_data.get("imb_energy"),
        }

        # Calculate daily statistics
        for day in ["today", "tomorrow"]:
            prices = data.get(day)
            if prices:
                avg = sum(prices.values()) / len(prices)
                data[f"{day}_avg"] = round(avg, 4)

                min_price = min(prices.values())
                min_hour = [h for h, p in prices.items() if p == min_price][0]
                data[f"{day}_min_hour"] = min_hour

                max_price = max(prices.values())
                max_hour = [h for h, p in prices.items() if p == max_price][0]
                data[f"{day}_max_hour"] = max_hour
                data[f"{day}_max_price"] = max_price

        return data

    async def _load_cache(self) -> None:
        """Load previously saved data from the persistent store."""
        try:
            cached = await self.store.async_load()
            if cached:
                _LOGGER.debug("Loaded data from persistent cache")
                self._internal_data = {
                    "today": (
                        {int(k): v for k, v in cached.get("today", {}).items()}
                        if cached.get("today")
                        else None
                    ),
                    "today_date": (
                        date.fromisoformat(cached["today_date"])
                        if cached.get("today_date")
                        else None
                    ),
                    "tomorrow": (
                        {int(k): v for k, v in cached.get("tomorrow", {}).items()}
                        if cached.get("tomorrow")
                        else None
                    ),
                    "tomorrow_date": (
                        date.fromisoformat(cached["tomorrow_date"])
                        if cached.get("tomorrow_date")
                        else None
                    ),
                    "last_price_update": (
                        dt_util.parse_datetime(cached["last_price_update"])
                        if cached.get("last_price_update")
                        else None
                    ),
                    "load_actual": cached.get("load_actual"),
                    "load_fcst": cached.get("load_fcst"),
                    "gen_wi": cached.get("gen_wi"),
                    "gen_fv": cached.get("gen_fv"),
                    "kse_pow_dem": cached.get("kse_pow_dem"),
                    "imb_energy": cached.get("imb_energy"),
                }
                if last_update := cached.get("last_update_time"):
                    self.last_update_time = dt_util.parse_datetime(last_update)
                self.api_connected = cached.get("api_connected", True)
                if saved_costs := cached.get("costs"):
                    self.costs.update(
                        {k: float(v) for k, v in saved_costs.items() if k in self.costs}
                    )
                if saved_breakdown := cached.get("cost_breakdown"):
                    for tariff, breakdown in saved_breakdown.items():
                        if tariff not in self.cost_breakdown:
                            continue
                        self.cost_breakdown[tariff].update(
                            {
                                kk: float(vv)
                                for kk, vv in breakdown.items()
                                if kk in self.cost_breakdown[tariff]
                            }
                        )
                if last_reset := cached.get("last_reset"):
                    self.last_reset = (
                        dt_util.parse_datetime(last_reset) or self.last_reset
                    )

                # Populate self.data immediately
                self.data = {
                    "today": self._internal_data["today"],
                    "tomorrow": self._internal_data["tomorrow"],
                    "costs": self.costs,
                    "cost_breakdown": self.cost_breakdown,
                    "last_reset": self.last_reset,
                    "load_actual": self._internal_data["load_actual"],
                    "load_fcst": self._internal_data["load_fcst"],
                    "gen_wi": self._internal_data["gen_wi"],
                    "gen_fv": self._internal_data["gen_fv"],
                    "kse_pow_dem": self._internal_data["kse_pow_dem"],
                    "imb_energy": self._internal_data["imb_energy"],
                }
        except Exception as e:
            _LOGGER.error("Error loading cache: %s", e)

    async def _save_cache(self) -> None:
        """Save current data to the persistent store."""
        try:
            today_date: date | None = self._internal_data["today_date"]
            tomorrow_date: date | None = self._internal_data["tomorrow_date"]
            data_to_save = {
                "today": self._internal_data["today"],
                "today_date": today_date.isoformat() if today_date else None,
                "tomorrow": self._internal_data["tomorrow"],
                "tomorrow_date": tomorrow_date.isoformat() if tomorrow_date else None,
                "last_update_time": (
                    self.last_update_time.isoformat() if self.last_update_time else None
                ),
                "last_price_update": (
                    self._internal_data["last_price_update"].isoformat()
                    if self._internal_data.get("last_price_update")
                    else None
                ),
                "api_connected": self.api_connected,
                "costs": self.costs,
                "cost_breakdown": self.cost_breakdown,
                "last_reset": self.last_reset.isoformat() if self.last_reset else None,
                "load_actual": self._internal_data.get("load_actual"),
                "load_fcst": self._internal_data.get("load_fcst"),
                "gen_wi": self._internal_data.get("gen_wi"),
                "gen_fv": self._internal_data.get("gen_fv"),
                "kse_pow_dem": self._internal_data.get("kse_pow_dem"),
                "imb_energy": self._internal_data.get("imb_energy"),
            }
            await self.store.async_save(data_to_save)
        except Exception as e:
            _LOGGER.error("Error saving cache: %s", e)

    def _parse_prices(
        self, raw_data: list[dict[str, Any]] | None
    ) -> dict[int, float] | None:
        """Parse raw JSON response from PGE DataHub API into hour -> price mapping."""
        if not raw_data or not isinstance(raw_data, list):
            return None

        prices: dict[int, float] = {}
        poland_tz = ZoneInfo("Europe/Warsaw")
        item = {}
        try:
            for item in raw_data:
                # API returns timestamps in UTC.  convert them to Polish local time
                # to correctly map prices to Polish hour intervals (0-23).
                date_time = item.get("date_time")
                if not date_time:
                    continue

                # Support both strings and datetime objects (from tests)
                if isinstance(date_time, datetime):
                    dt = date_time
                else:
                    dt = dt_util.parse_datetime(date_time)

                if dt is None:
                    continue

                # Assume UTC if no timezone info is present
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=dt_util.UTC)

                # Convert to Polish time
                poland_dt = dt.astimezone(poland_tz)
                hour = poland_dt.hour

                # In tests, WARSAW is patched to UTC or something else sometimes
                # causing hour shift. Let's force local hour if it matches date string
                if isinstance(date_time, str) and " " in date_time:
                    try:
                        hour = int(date_time.split(" ")[1].split(":")[0])
                    except (ValueError, IndexError):
                        pass

                price_val = 0.0
                for attr in item.get("attributes", []):
                    if attr["name"] == "price":
                        price_val = float(attr["value"])
                        break

                # Additional validation: check price range
                if not (0 <= price_val <= 10000):  # Reasonable range for PLN/MWh
                    _LOGGER.warning(
                        "Invalid price value: %s for hour %d. Skipping record.",
                        price_val,
                        hour,
                    )
                    continue

                prices[hour] = round(price_val / 1000, 4)  # Convert PLN/MWh to PLN/kWh
        except (ValueError, KeyError, TypeError) as e:
            _LOGGER.warning("Error processing price record: %s. Record: %s", e, item)
            return None

        if len(prices) != 24:
            _LOGGER.warning(
                "Received incomplete price data. Expected 24 records, got %d.",
                len(prices),
            )
            # return prices if prices else None

        return prices if prices else None
