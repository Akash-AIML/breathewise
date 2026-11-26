"""List endpoints must enforce a server-side response budget."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints import cpcb as cpcb_endpoint
from app.api.v1.endpoints import stations as stations_endpoint
from app.core.config import settings
from app.main import app
from app.schemas.cpcb import CPCBStationObservation
from app.schemas.observation import DataQualityStatus


def _cpcb_observation() -> CPCBStationObservation:
    now = datetime.now(UTC)
    return CPCBStationObservation(
        state="Tamil Nadu",
        city="Chennai",
        station="Velachery",
        station_id="cpcb_tamil_nadu_chennai_velachery",
        latitude=12.9815,
        longitude=80.2182,
        last_update=now,
        retrieval_timestamp=now,
        freshness=DataQualityStatus.VERIFIED,
    )


@pytest.mark.asyncio
async def test_stations_list_enforces_page_size(monkeypatch, clean_observation):
    station = clean_observation.station
    monkeypatch.setattr(
        stations_endpoint.air_quality_service,
        "search_stations_live",
        AsyncMock(return_value=([station] * 600, "fallback_registry")),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/stations", params={"limit": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 5
    assert len(body["data"]) == 5

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        oversized = await client.get(
            "/api/v1/stations", params={"limit": settings.API_MAX_PAGE_SIZE + 1}
        )
    assert oversized.status_code == 422


@pytest.mark.asyncio
async def test_cpcb_list_endpoints_enforce_page_size(monkeypatch):
    monkeypatch.setattr(
        cpcb_endpoint.air_quality_service.cpcb_adapter,
        "get_station_observations",
        AsyncMock(return_value=[_cpcb_observation()] * 600),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        summary = await client.get(
            "/api/v1/air-quality/summary", params={"city": "Delhi", "limit": 7}
        )
        nearby = await client.get(
            "/api/v1/air-quality/nearby",
            params={"lat": 12.9815, "lon": 80.2182, "limit": 3},
        )
        oversized = await client.get(
            "/api/v1/air-quality/summary",
            params={"city": "Chennai", "limit": settings.API_MAX_PAGE_SIZE + 1},
        )

    assert summary.status_code == 200
    assert summary.json()["count"] == 7
    assert len(summary.json()["data"]) == 7

    assert nearby.status_code == 200
    assert nearby.json()["count"] == 3
    assert len(nearby.json()["data"]) == 3

    assert oversized.status_code == 422
