"""CPCB unit tests: secret redaction, configuration and HTTP endpoint wiring."""

import logging

import pytest
from httpx import ASGITransport, AsyncClient

from app.adapters.cpcb import CPCBProviderError, redact_secrets
from app.api.v1.endpoints.cpcb import air_quality_service as cpcb_endpoint_service
from app.core.config import BACKEND_DIR, ENV_FILE, REPO_ROOT, settings
from app.main import app

try:  # pytest may import tests as a package or as top-level modules
    from .cpcb_helpers import SECRET, _async_return, make_observation
except ImportError:
    from cpcb_helpers import SECRET, _async_return, make_observation


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
