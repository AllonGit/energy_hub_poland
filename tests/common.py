"""Shared test constants and helpers."""

from datetime import date, timedelta, timezone

ENTRY_ID = "test_entry_123"

CET = timezone(timedelta(hours=1))
CEST = timezone(timedelta(hours=2))

# Sample 24-hour price data (PLN/kWh after /1000 conversion)
SAMPLE_PRICES_TODAY = {h: round(0.30 + h * 0.02, 4) for h in range(24)}
SAMPLE_PRICES_TOMORROW = {h: round(0.28 + h * 0.015, 4) for h in range(24)}


def make_raw_api_data(for_date: date, prices: dict[int, float] | None = None):
    """Build raw API response data matching the TGE format."""
    if prices is None:
        prices = {h: (300 + h * 20) for h in range(24)}  # raw mWh values
    records = []
    for hour in range(24):
        raw_price = prices.get(hour, 300.0)
        records.append(
            {
                "date_time": f"{for_date.isoformat()} {hour:02d}:00:00",
                "attributes": [{"name": "price", "value": str(raw_price)}],
            }
        )
    return records
