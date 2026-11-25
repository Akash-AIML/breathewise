import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.cpcb import (
    CPCBAdapter,
    CPCBProviderError,
    CPCBResponseError,
    CPCBTemporaryError,
    redact_secrets,
)
from app.api.v1.endpoints.cpcb import air_quality_service as cpcb_endpoint_service
from app.core.config import BACKEND_DIR, ENV_FILE, REPO_ROOT, settings
from app.main import app
from app.schemas.cpcb import CPCBStationObservation
from app.schemas.observation import DataQualityStatus

SECRET = "unit-test-secret-key"
NOW = datetime.now(timezone.utc).isoformat()


def make_record(**overrides):
    record = {
        "country": "India",
        "state": "Tamil Nadu",
        "city": "Chennai",
        "station": "Velachery",
        "last_update": NOW,
        "latitude": 12.9815,
        "longitude": 80.2182,
        "pollutant_id": "PM2.5",
        "min_value": "10.0",
        "max_value": "90.0",
        "avg_value": "45.5",
    }
    record.update(overrides)
    return record


def make_observation(**overrides):
    values = {
        "state": "Tamil Nadu",
        "city": "Chennai",
        "station": "Velachery",
        "station_id": "cpcb_tamil_nadu_chennai_velachery",
        "latitude": 12.9815,
        "longitude": 80.2182,
        "last_update": datetime.now(timezone.utc),
        "retrieval_timestamp": datetime.now(timezone.utc),
        "freshness": DataQualityStatus.VERIFIED,
    }
    values.update(overrides)
    return CPCBStationObservation(**values)


def adapter_with_mock(handler):
    adapter = CPCBAdapter(api_key=SECRET)
    adapter._client = lambda: httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return adapter


@pytest.mark.asyncio
async def test_successful_request_uses_configured_key_and_actual_fields():
    seen = {}

    async def handler(request):
        seen["params"] = dict(request.url.params)
        return httpx.Response(200, json={"total": 1, "records": [make_record()]})

    adapter = adapter_with_mock(handler)
    obs = await adapter.fetch_by_coordinates(12.98, 80.21)

    assert obs is not None
    assert obs.provider == "CPCB/data.gov.in"
    assert obs.station.station_name == "Velachery"
    assert seen["params"]["api-key"] == SECRET
    assert seen["params"]["format"] == "json"
    assert seen["params"]["limit"] == str(settings.CPCB_PAGE_SIZE)
    assert obs.calculated_aqi is None
    assert obs.readings["PM2.5"].min_value == 10.0
    assert obs.readings["PM2.5"].max_value == 90.0
    assert obs.readings["PM2.5"].unit is None


@pytest.mark.asyncio
async def test_invalid_key_is_not_retried():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(401, json={"error": "invalid"})

    with pytest.raises(CPCBProviderError):
        await adapter_with_mock(handler)._request_page({"limit": 1})
    assert calls == 1


@pytest.mark.asyncio
async def test_rate_limit_is_retried_then_succeeds(monkeypatch):
    monkeypatch.setattr(settings, "CPCB_BACKOFF_BASE_SECONDS", 0.0)
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json={"total": 0, "records": []})

    records, total = await adapter_with_mock(handler)._request_page({"limit": 1})
    assert (records, total) == ([], 0)
    assert calls == 2


@pytest.mark.asyncio
async def test_timeout_retries_bounded_then_raises(monkeypatch):
    monkeypatch.setattr(settings, "CPCB_BACKOFF_BASE_SECONDS", 0.0)
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.TimeoutException("read timeout")

    with pytest.raises(CPCBTemporaryError):
        await adapter_with_mock(handler)._request_page({"limit": 1})
    assert calls == settings.CPCB_MAX_RETRIES + 1


@pytest.mark.asyncio
async def test_network_failure_is_handled(monkeypatch):
    monkeypatch.setattr(settings, "CPCB_BACKOFF_BASE_SECONDS", 0.0)
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("network down")

    with pytest.raises(CPCBTemporaryError):
        await adapter_with_mock(handler)._request_page({"limit": 1})
    assert calls == settings.CPCB_MAX_RETRIES + 1


@pytest.mark.asyncio
async def test_invalid_json_is_handled():
    async def handler(request):
        return httpx.Response(200, text="{not json")

    with pytest.raises(CPCBResponseError):
        await adapter_with_mock(handler)._request_page({"limit": 1})


@pytest.mark.asyncio
async def test_empty_records_are_not_treated_as_valid_readings():
    async def handler(request):
        return httpx.Response(200, json={"total": 0, "records": []})

    records, total = await adapter_with_mock(handler)._fetch_pages()
    assert records == []
    assert total == 0


@pytest.mark.asyncio
async def test_pagination_uses_limit_and_offset():
    offsets = []

    async def handler(request):
        offset = int(request.url.params.get("offset", "0"))
        offsets.append(offset)
        size = int(request.url.params["limit"])
        records = [make_record(station=f"Station {offset + i}") for i in range(size)]
        total = 5
        remaining = max(0, total - offset)
        records = records[: min(len(records), remaining)]
        return httpx.Response(200, json={"total": total, "records": records})

    records, total = await adapter_with_mock(handler)._fetch_pages(max_pages=3, page_size=2)
    assert offsets == [0, 2, 4]
    assert len(records) == 5
    assert total == 5


@pytest.mark.asyncio
async def test_verified_state_filter_is_sent_upstream():
    captured = []

    async def handler(request):
        captured.append(dict(request.url.params))
        return httpx.Response(200, json={"total": 1, "records": [make_record()]})

    observations = await adapter_with_mock(handler).get_station_observations(state="Tamil Nadu")
    assert len(observations) == 1
    assert any(params.get("filters[state]") == "Tamil Nadu" for params in captured)


@pytest.mark.asyncio
async def test_verified_city_filter_is_sent_upstream():
    captured = []

    async def handler(request):
        captured.append(dict(request.url.params))
        return httpx.Response(200, json={"total": 1, "records": [make_record()]})

    observations = await adapter_with_mock(handler).get_station_observations(city="Chennai")
    assert len(observations) == 1
    assert any(params.get("filters[city]") == "Chennai" for params in captured)


@pytest.mark.asyncio
async def test_unverified_filter_value_is_not_sent_upstream(monkeypatch):
    monkeypatch.setattr(settings, "CPCB_MAX_PAGES", 1)
    captured = []

    async def handler(request):
        captured.append(dict(request.url.params))
        return httpx.Response(
            200, json={"total": 1, "records": [make_record(city="Delhi", state="Delhi")]}
        )

    observations = await adapter_with_mock(handler).get_station_observations(city="Mumbai")
    assert observations == []
    assert not any(params.get("filters[city]") == "Mumbai" for params in captured)


@pytest.mark.asyncio
async def test_zero_record_filter_falls_back_to_unfiltered_pagination():
    async def handler(request):
        if "filters[city]" in request.url.params:
            return httpx.Response(200, json={"total": 0, "records": []})
        return httpx.Response(200, json={"total": 1, "records": [make_record()]})

    observations = await adapter_with_mock(handler).get_station_observations(city="Chennai")
    assert len(observations) == 1
    assert observations[0].city == "Chennai"


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
    later = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
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
    timestamp = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    status, _ = CPCBAdapter._freshness(timestamp)
    assert status == expected


def test_future_and_missing_timestamps_are_unavailable():
    future = datetime.now(timezone.utc) + timedelta(hours=1)
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
        datetime.now(timezone.utc) - timedelta(seconds=1),
        adapter._last_valid["all"][1],
    )
    should_fail["value"] = True

    stale = await adapter._all_observations()
    assert len(stale) == 1
    assert stale[0].freshness == DataQualityStatus.STALE
    assert any("last valid observation" in warning for warning in stale[0].warnings)


def test_secret_is_redacted_from_messages_and_logs(caplog):
    secret_url = f"https://api.data.gov.in/resource/x?api-key={SECRET}&format=json"
    assert SECRET not in redact_secrets(secret_url)
    with caplog.at_level(logging.WARNING):
        logged = redact_secrets(secret_url)
    assert SECRET not in logged
    assert SECRET not in caplog.text


def test_configuration_resolves_one_env_file_path():
    assert ENV_FILE == BACKEND_DIR / ".env" or ENV_FILE == REPO_ROOT / ".env"
    assert settings.CPCB_PAGE_SIZE > 0
    assert settings.CPCB_MAX_PAGES > 0


@pytest.mark.asyncio
async def test_nearby_endpoint_returns_each_station_with_distance(monkeypatch):
    observation = make_observation()
    monkeypatch.setattr(
        cpcb_endpoint_service.cpcb_adapter,
        "get_station_observations",
        _async_return([observation]),
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/air-quality/nearby", params={"lat": 12.98, "lon": 80.21}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["selected_station_id"] == observation.station_id
    assert data["data"][0]["distance_km"] >= 0
    assert "haversine" in data["message"]


@pytest.mark.asyncio
async def test_summary_endpoint_passes_city_to_adapter(monkeypatch):
    calls = {}

    async def fake(city=None, state=None):
        calls["city"] = city
        calls["state"] = state
        return [make_observation()]

    monkeypatch.setattr(cpcb_endpoint_service.cpcb_adapter, "get_station_observations", fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/air-quality/summary", params={"city": "Chennai"})
    assert response.status_code == 200
    assert calls == {"city": "Chennai", "state": None}


@pytest.mark.asyncio
async def test_station_endpoint_returns_observation(monkeypatch):
    observation = make_observation()

    async def fake(station_id):
        return observation if station_id == observation.station_id else None

    monkeypatch.setattr(cpcb_endpoint_service.cpcb_adapter, "get_station_observation", fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/air-quality/station/{observation.station_id}")
    assert response.status_code == 200
    assert response.json()["data"]["station"] == "Velachery"


@pytest.mark.asyncio
async def test_filter_verification_endpoint_returns_statuses(monkeypatch):
    async def fake():
        return {"city": {"verified": True, "status": "verified"}, "state": {"verified": False}}

    monkeypatch.setattr(cpcb_endpoint_service.cpcb_adapter, "verify_filters", fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/air-quality/filters/verification")
    assert response.status_code == 200
    assert response.json()["data"]["city"]["verified"] is True


@pytest.mark.asyncio
async def test_provider_failure_returns_503_without_upstream_url(monkeypatch):
    async def fake(*args, **kwargs):
        raise CPCBProviderError(f"failed at https://upstream?api-key={SECRET}")

    monkeypatch.setattr(cpcb_endpoint_service.cpcb_adapter, "get_station_observations", fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/air-quality/summary", params={"city": "Chennai"})
    assert response.status_code == 503
    assert SECRET not in response.text
    assert "upstream" not in response.text


def _async_return(value):
    async def fake(*args, **kwargs):
        return value

    return fake


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
