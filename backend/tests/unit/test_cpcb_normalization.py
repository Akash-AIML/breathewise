"""CPCB unit tests: record normalization, freshness, caching and request budgets."""

import asyncio
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.adapters.cpcb import CPCBAdapter, CPCBTemporaryError
from app.core.config import settings
from app.schemas.observation import DataQualityStatus

try:  # pytest may import tests as a package or as top-level modules
    from .cpcb_helpers import SECRET, adapter_with_mock, make_record
except ImportError:
    from cpcb_helpers import SECRET, adapter_with_mock, make_record


def test_normalization_preserves_min_max_and_omits_unknown_unit():
    adapter = CPCBAdapter(api_key=SECRET)
    observations = adapter.parse_records([make_record()])
    stats = observations[0].pollutants["PM2.5"]
    assert stats.pollutant_id == "PM2.5"
    assert (stats.min, stats.max, stats.avg) == (10.0, 90.0, 45.5)
    assert stats.unit is None


@pytest.mark.parametrize("bad_value", [None, "", "NA", "not-a-number", "NaN"])
def test_null_and_malformed_pollutant_values_are_ignored(bad_value):
    adapter = CPCBAdapter(api_key=SECRET)
    observations = adapter.parse_records([make_record(avg_value=bad_value)])
    assert observations[0].pollutants["PM2.5"].avg is None
    assert adapter.to_normalized(observations[0]).readings == {}


@pytest.mark.parametrize(
    "overrides",
    [
        {"latitude": "100.0"},
        {"longitude": "200.0"},
        {"latitude": "bad", "longitude": "80.21"},
    ],
)
def test_invalid_coordinates_are_dropped(overrides):
    adapter = CPCBAdapter(api_key=SECRET)
    assert adapter.parse_records([make_record(**overrides)]) == []


def test_missing_station_name_is_dropped():
    adapter = CPCBAdapter(api_key=SECRET)
    assert adapter.parse_records([make_record(station="  ")]) == []


def test_invalid_timestamp_is_dropped():
    adapter = CPCBAdapter(api_key=SECRET)
    assert adapter.parse_records([make_record(last_update="not-a-date")]) == []


def test_duplicate_pollutant_rows_are_collapsed_with_warning():
    adapter = CPCBAdapter(api_key=SECRET)
    observations = adapter.parse_records([make_record(), make_record(avg_value="60.0")])
    assert len(observations) == 1
    assert observations[0].pollutants["PM2.5"].avg == 45.5
    assert any("Duplicate" in warning for warning in observations[0].warnings)


def test_same_station_different_timestamps_are_not_merged():
    later = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    adapter = CPCBAdapter(api_key=SECRET)
    observations = adapter.parse_records(
        [make_record(pollutant_id="PM2.5"), make_record(pollutant_id="NO2", last_update=later)]
    )
    assert len(observations) == 2
    assert sorted(len(obs.pollutants) for obs in observations) == [1, 1]


@pytest.mark.parametrize(
    ("age_hours", "expected"),
    [
        (1, DataQualityStatus.VERIFIED),
        (4, DataQualityStatus.DELAYED),
        (10, DataQualityStatus.STALE),
    ],
)
def test_freshness_thresholds_use_source_time(age_hours, expected):
    timestamp = datetime.now(UTC) - timedelta(hours=age_hours)
    status, _ = CPCBAdapter._freshness(timestamp)
    assert status == expected


def test_future_and_missing_timestamps_are_unavailable():
    future = datetime.now(UTC) + timedelta(hours=1)
    status, warning = CPCBAdapter._freshness(future)
    assert status == DataQualityStatus.UNAVAILABLE
    assert "future" in warning
    status, warning = CPCBAdapter._freshness(None)
    assert status == DataQualityStatus.UNAVAILABLE
    assert "No valid source timestamp" in warning


@pytest.mark.asyncio
async def test_concurrent_requests_are_coalesced_and_cached():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return httpx.Response(200, json={"total": 1, "records": [make_record()]})

    adapter = adapter_with_mock(handler)
    await asyncio.gather(*(adapter._sample_observations() for _ in range(5)))
    await adapter._sample_observations()
    assert calls == 1


@pytest.mark.asyncio
async def test_failed_refresh_keeps_last_valid_observation_as_stale():
    should_fail = {"value": False}

    async def handler(request):
        if should_fail["value"]:
            raise httpx.ConnectError("provider unavailable")
        return httpx.Response(200, json={"total": 1, "records": [make_record()]})

    adapter = adapter_with_mock(handler)
    assert len(await adapter._all_observations()) == 1
    adapter._cache["all"] = (
        datetime.now(UTC) - timedelta(seconds=1),
        adapter._last_valid["all"][1],
    )
    should_fail["value"] = True

    stale = await adapter._all_observations()
    assert len(stale) == 1
    assert stale[0].freshness == DataQualityStatus.STALE
    assert any("last valid observation" in warning for warning in stale[0].warnings)


@pytest.mark.asyncio
async def test_request_budget_caps_slow_provider(monkeypatch):
    """A hanging provider must not hold up the user request or downstream providers."""
    monkeypatch.setattr(settings, "CPCB_REQUEST_BUDGET_SECONDS", 0.05)
    monkeypatch.setattr(settings, "CPCB_MAX_RETRIES", 5)

    async def handler(request):
        await asyncio.sleep(1.0)
        return httpx.Response(200, json={"total": 1, "records": [make_record()]})

    adapter = adapter_with_mock(handler)
    loop = asyncio.get_running_loop()
    started = loop.time()
    with pytest.raises(CPCBTemporaryError):
        await adapter.get_station_observations()
    assert loop.time() - started < 0.5


@pytest.mark.asyncio
async def test_circuit_breaker_skips_provider_after_failure(monkeypatch):
    monkeypatch.setattr(settings, "CPCB_REQUEST_BUDGET_SECONDS", 0.05)
    monkeypatch.setattr(settings, "CPCB_CIRCUIT_BREAKER_SECONDS", 30)
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        await asyncio.sleep(1.0)
        return httpx.Response(200, json={"total": 1, "records": [make_record()]})

    adapter = adapter_with_mock(handler)
    with pytest.raises(CPCBTemporaryError):
        await adapter.get_station_observations()
    with pytest.raises(CPCBTemporaryError):
        await adapter.get_station_observations()
    assert calls == 1


@pytest.mark.asyncio
async def test_budget_timeout_preserves_last_valid_observation(monkeypatch):
    monkeypatch.setattr(settings, "CPCB_CIRCUIT_BREAKER_SECONDS", 0)
    monkeypatch.setattr(settings, "CPCB_CACHE_TTL_SECONDS", 0)
    state = {"slow": False}

    async def handler(request):
        if state["slow"]:
            await asyncio.sleep(1.0)
        return httpx.Response(200, json={"total": 1, "records": [make_record()]})

    adapter = adapter_with_mock(handler)
    first = await adapter.fetch_by_coordinates(12.98, 80.21)
    assert first is not None

    state["slow"] = True
    monkeypatch.setattr(settings, "CPCB_REQUEST_BUDGET_SECONDS", 0.05)
    second = await adapter.fetch_by_coordinates(12.98, 80.21)
    assert second is not None
    assert "Refresh failed" in (second.notes or "")
