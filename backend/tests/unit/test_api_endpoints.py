from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.observation import (
    DataQualityStatus,
    NormalizedObservation,
    NormalizedPollutantReading,
    PollutantType,
    StationMetadata,
)


@pytest.fixture
def mock_observation():
    return NormalizedObservation(
        provider="openmeteo_cams",
        station=StationMetadata(
            station_id="test_delhi_ito",
            station_name="ITO Delhi",
            city="Delhi",
            state="Delhi",
            latitude=28.6289,
            longitude=77.2407,
            distance_km=2.5,
        ),
        readings={
            "PM2.5": NormalizedPollutantReading(
                pollutant=PollutantType.PM2_5, value=65.0, unit="µg/m³"
            ),
            "PM10": NormalizedPollutantReading(
                pollutant=PollutantType.PM10, value=120.0, unit="µg/m³"
            ),
            "NO2": NormalizedPollutantReading(
                pollutant=PollutantType.NO2, value=45.0, unit="µg/m³"
            ),
        },
        calculated_aqi=117,
        dominant_pollutant=PollutantType.PM2_5,
        data_sufficiency_met=True,
        measurement_timestamp=datetime.now(timezone.utc),
        retrieval_timestamp=datetime.now(timezone.utc),
        data_quality_status=DataQualityStatus.VERIFIED,
    )


@pytest.mark.asyncio
async def test_health_check_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "openmeteo_cams" in data["providers"]
        assert data["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_security_headers_present():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"
        assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "max-age=" in resp.headers["strict-transport-security"]


@pytest.mark.asyncio
async def test_stations_listing():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["count"] >= 10
        assert len(data["data"]) >= 10


@pytest.mark.asyncio
async def test_stations_search_by_query():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stations", params={"query": "mumbai"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["count"] >= 1
        assert "mumbai" in data["data"][0]["city"].lower()


@pytest.mark.asyncio
async def test_station_by_id_found_and_not_found():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Valid station ID
        resp_valid = await client.get("/api/v1/stations/cpcb_delhi_ito")
        assert resp_valid.status_code == 200
        assert resp_valid.json()["station_id"] == "cpcb_delhi_ito"

        # Invalid station ID -> 404
        resp_invalid = await client.get("/api/v1/stations/nonexistent_id_9999")
        assert resp_invalid.status_code == 404
        assert "not found" in resp_invalid.json()["message"]


@pytest.mark.asyncio
async def test_air_quality_endpoint_success(mock_observation):
    with patch(
        "app.api.v1.endpoints.air_quality.air_quality_service.get_air_quality_for_coordinates",
        new_callable=AsyncMock,
    ) as mock_get:
        mock_get.return_value = mock_observation
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/air-quality", params={"lat": 28.6139, "lon": 77.2090})
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is True
            assert data["data"]["calculated_aqi"] == 117
            assert data["data"]["provider"] == "openmeteo_cams"


@pytest.mark.asyncio
async def test_air_quality_validation_errors():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Latitude out of bounds (> 90.0)
        resp = await client.get("/api/v1/air-quality", params={"lat": 95.0, "lon": 77.0})
        assert resp.status_code == 422
        data = resp.json()
        assert data["success"] is False
        assert data["error_code"] == "VALIDATION_ERROR"
        assert len(data["details"]) > 0


@pytest.mark.asyncio
async def test_rate_limiting():
    # Test rate limiter directly on an endpoint with isolated test IP
    headers = {"X-Test-Client-IP": "rate-limit-burst-ip"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Make a burst of requests to /api/v1/stations
        for _ in range(125):
            resp = await client.get("/api/v1/stations", headers=headers)
            if resp.status_code == 429:
                data = resp.json()
                assert data["success"] is False
                assert data["error_code"] == "RATE_LIMIT_EXCEEDED"
                assert "Retry-After" in resp.headers
                return
        pytest.fail("Rate limiter did not trigger within 125 requests")
