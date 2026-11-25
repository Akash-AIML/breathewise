"""CPCB adapter unit tests: request handling, retries, pagination and filters."""

import httpx
import pytest

from app.adapters.cpcb import CPCBProviderError, CPCBResponseError, CPCBTemporaryError
from app.core.config import settings

try:  # pytest may import tests as a package or as top-level modules
    from .cpcb_helpers import SECRET, adapter_with_mock, make_record
except ImportError:
    from cpcb_helpers import SECRET, adapter_with_mock, make_record


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
