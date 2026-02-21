"""Shared fixtures for Energy Hub Poland tests."""

import sys
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# =============================================================================
# Stub HA modules with proper base classes to avoid metaclass conflicts
# =============================================================================


def _identity_decorator(*args, **kwargs):
    """Decorator that returns the function/class unchanged."""
    if args and callable(args[0]):
        return args[0]
    return lambda f: f


# --- Stub base classes ---


class _StubCoordinatorEntity:
    """Stub for homeassistant.helpers.update_coordinator.CoordinatorEntity."""

    def __init__(self, coordinator=None):
        self.coordinator = coordinator


class _StubSensorEntity:
    """Stub for homeassistant.components.sensor.SensorEntity."""

    pass


class _StubBinarySensorEntity:
    """Stub for homeassistant.components.binary_sensor.BinarySensorEntity."""

    pass


class _StubRestoreEntity:
    """Stub for homeassistant.helpers.restore_state.RestoreEntity."""

    async def async_get_last_state(self):
        return None


class _StubConfigFlow:
    """Stub for homeassistant.config_entries.ConfigFlow."""

    pass


class _StubOptionsFlow:
    """Stub for homeassistant.config_entries.OptionsFlow."""

    pass


# --- Build stub modules ---

# homeassistant (root)
ha_mod = MagicMock()
sys.modules.setdefault("homeassistant", ha_mod)

# homeassistant.const
ha_const = MagicMock()
ha_const.Platform = MagicMock()
sys.modules.setdefault("homeassistant.const", ha_const)

# homeassistant.core
ha_core = MagicMock()
ha_core.callback = _identity_decorator
ha_core.HomeAssistant = MagicMock
sys.modules.setdefault("homeassistant.core", ha_core)

# homeassistant.config_entries
ha_ce = MagicMock()
ha_ce.ConfigFlow = _StubConfigFlow
ha_ce.OptionsFlow = _StubOptionsFlow
ha_ce.ConfigEntry = MagicMock
sys.modules.setdefault("homeassistant.config_entries", ha_ce)

# homeassistant.data_entry_flow
ha_def = MagicMock()
sys.modules.setdefault("homeassistant.data_entry_flow", ha_def)

# homeassistant.components.sensor
ha_sensor = MagicMock()
ha_sensor.SensorEntity = _StubSensorEntity
sys.modules.setdefault("homeassistant.components.sensor", ha_sensor)

# homeassistant.components.binary_sensor
ha_bs = MagicMock()
ha_bs.BinarySensorEntity = _StubBinarySensorEntity
sys.modules.setdefault("homeassistant.components.binary_sensor", ha_bs)

# homeassistant.helpers
sys.modules.setdefault("homeassistant.helpers", MagicMock())

# homeassistant.helpers.update_coordinator
ha_uc = MagicMock()
ha_uc.CoordinatorEntity = _StubCoordinatorEntity
ha_uc.DataUpdateCoordinator = type(
    "DataUpdateCoordinator", (), {"__init__": lambda self, *a, **kw: None}
)
ha_uc.UpdateFailed = Exception
sys.modules.setdefault("homeassistant.helpers.update_coordinator", ha_uc)

# homeassistant.helpers.entity
ha_entity = MagicMock()
ha_entity.DeviceInfo = dict
ha_entity.EntityCategory = MagicMock()
sys.modules.setdefault("homeassistant.helpers.entity", ha_entity)

# homeassistant.helpers.restore_state
ha_rs = MagicMock()
ha_rs.RestoreEntity = _StubRestoreEntity
sys.modules.setdefault("homeassistant.helpers.restore_state", ha_rs)

# homeassistant.helpers.event
ha_event = MagicMock()
ha_event.async_track_state_change_event = MagicMock()
ha_event.async_track_time_change = MagicMock()
sys.modules.setdefault("homeassistant.helpers.event", ha_event)

# Other helpers
sys.modules.setdefault("homeassistant.helpers.aiohttp_client", MagicMock())
sys.modules.setdefault("homeassistant.helpers.config_validation", MagicMock())
sys.modules.setdefault("homeassistant.helpers.entity_registry", MagicMock())
sys.modules.setdefault("homeassistant.helpers.selector", MagicMock())
sys.modules.setdefault("homeassistant.helpers.storage", MagicMock())

# homeassistant.util and homeassistant.util.dt
ha_util = MagicMock()
sys.modules.setdefault("homeassistant.util", ha_util)

ha_dt_util = MagicMock()
sys.modules.setdefault("homeassistant.util.dt", ha_dt_util)

# voluptuous (used in config_flow)
vol_mock = MagicMock()
vol_mock.Schema = lambda x: x
vol_mock.Required = lambda key, **kw: key
vol_mock.Optional = lambda key, **kw: key
vol_mock.Coerce = lambda t: t
sys.modules.setdefault("voluptuous", vol_mock)


# =============================================================================
# Imports & Fixtures
# =============================================================================

from .common import (  # noqa: E402, I001
    CEST,
    CET,
    ENTRY_ID,
    SAMPLE_PRICES_TODAY,
    SAMPLE_PRICES_TOMORROW,
)


@pytest.fixture
def sample_prices_today():
    return dict(SAMPLE_PRICES_TODAY)


@pytest.fixture
def sample_prices_tomorrow():
    return dict(SAMPLE_PRICES_TOMORROW)


@pytest.fixture
def coordinator_data(sample_prices_today, sample_prices_tomorrow):
    """Standard coordinator.data dict."""
    return {
        "today": sample_prices_today,
        "tomorrow": sample_prices_tomorrow,
    }


@pytest.fixture
def mock_entry():
    """Minimal ConfigEntry mock."""
    return SimpleNamespace(
        entry_id=ENTRY_ID,
        data={},
        options={},
        title="Energy Hub",
    )


@pytest.fixture
def mock_coordinator(coordinator_data):
    """Minimal coordinator mock with .data and .api_connected."""
    coord = MagicMock()
    coord.data = coordinator_data
    coord.api_connected = True
    return coord


@pytest.fixture
def winter_weekday():
    """Wednesday in January (winter, no DST)."""
    return datetime(2025, 1, 15, 10, 0, 0, tzinfo=CET)


@pytest.fixture
def summer_weekday():
    """Wednesday in July (summer, DST active)."""
    return datetime(2025, 7, 16, 10, 0, 0, tzinfo=CEST)


@pytest.fixture
def saturday():
    """Saturday in winter."""
    return datetime(2025, 1, 18, 10, 0, 0, tzinfo=CET)


@pytest.fixture
def polish_holiday():
    """Polish Independence Day (Nov 11) - a weekday."""
    return datetime(2025, 11, 11, 10, 0, 0, tzinfo=CET)
