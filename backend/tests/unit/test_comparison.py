from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints import comparison as comparison_endpoint
from app.main import app
from app.schemas.cpcb import CPCBPollutantStats, CPCBStationObservation
from app.schemas.observation import DataQualityStatus


@pytest.fixture(autouse=True)
def no_live_cpcb(monkeypatch):
    """Default tests never call the live CPCB provider."""
    monkeypatch.setattr(
        comparison_endpoint.comparison_service.air_quality.cpcb_adapter,
        "get_station_observations",
        AsyncMock(return_value=[]),
    )


def _cpcb_observation(
    station_id: str,
    station: str,
    lat: float,
    lon: float,
    city: str = "Delhi",
    state: str = "Delhi",
):
    now = datetime.now(timezone.utc)
    pollutants = {
        "PM2.5": CPCBPollutantStats(pollutant_id="PM2.5", min=10, max=80, avg=45),
        "PM10": CPCBPollutantStats(pollutant_id="PM10", min=20, max=140, avg=85),
        "NO2": CPCBPollutantStats(pollutant_id="NO2", min=5, max=60, avg=30),
    }
    return CPCBStationObservation(
        state=state,
        city=city,
        station=station,
        station_id=station_id,
        latitude=lat,
        longitude=lon,
        last_update=now,
        retrieval_timestamp=now,
        freshness=DataQualityStatus.VERIFIED,
        pollutants=pollutants,
    )


@pytest.mark.asyncio
async def test_compare_stations_insufficient_ids():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/stations/compare", params={"station_ids": "grid:cpcb_delhi_ito"}
        )
        assert resp.status_code == 400
        assert "At least 2 station IDs" in resp.json()["message"]


@pytest.mark.asyncio
async def test_compare_stations_too_many_ids():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/stations/compare",
            params={"station_ids": "s1,s2,s3,s4,s5"},
        )
        assert resp.status_code == 400
        assert "maximum of 4 stations" in resp.json()["message"]


@pytest.mark.asyncio
async def test_grid_presets_are_labelled_and_data_driven():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stations/comparison-presets")

    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "fallback_registry_coordinate_grid"
    assert len(body["presets"]) == 3
    assert {preset["key"] for preset in body["presets"]} == {
        "delhi-corridors",
        "metro-cross-city",
        "indo-gangetic-plain",
    }
    for preset in body["presets"]:
        assert preset["basis"] == "coordinate_estimate"
        assert all(station_id.startswith("grid:") for station_id in preset["ids"])
        assert all(
            candidate["basis"] == "coordinate_estimate" for candidate in preset["candidates"]
        )


@pytest.mark.asyncio
async def test_grid_comparison_never_claims_physical_station(monkeypatch, clean_observation):
    monkeypatch.setattr(
        comparison_endpoint.comparison_service.air_quality,
        "get_air_quality_for_coordinates",
        AsyncMock(return_value=clean_observation),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/stations/compare",
            params={"station_ids": "grid:cpcb_delhi_ito,grid:cpcb_mumbai_bandra"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["basis"] == "coordinate_estimate"
    assert data["source"] == "fallback_registry_coordinate_grid"
    assert data["stations_count"] == 2
    assert data["differential"] is not None
    for observation in data["observations"]:
        assert observation["station"]["station_id"].startswith("grid:")
        assert "grid estimate" in observation["station"]["station_name"]
        assert "not a physical station observation" in observation["notes"]


@pytest.mark.asyncio
async def test_live_station_presets_use_reported_coordinates(monkeypatch):
    live = [
        _cpcb_observation("cpcb_live_ito", "ITO", 28.6289, 77.2407),
        _cpcb_observation("cpcb_live_anand_vihar", "Anand Vihar", 28.6469, 77.3160),
    ]
    monkeypatch.setattr(
        comparison_endpoint.comparison_service.air_quality.cpcb_adapter,
        "get_station_observations",
        AsyncMock(return_value=live),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        presets_resp = await client.get("/api/v1/stations/comparison-presets")
        compare_resp = await client.get(
            "/api/v1/stations/compare",
            params={"station_ids": "cpcb_live_ito,cpcb_live_anand_vihar"},
        )

    assert presets_resp.status_code == 200
    presets = presets_resp.json()
    assert presets["source"] == "CPCB/data.gov.in"
    delhi_preset = next(p for p in presets["presets"] if p["key"] == "delhi-corridors")
    assert delhi_preset["basis"] == "live_station"
    assert delhi_preset["ids"] == ["cpcb_live_ito", "cpcb_live_anand_vihar"]
    assert all(candidate["latitude"] for candidate in delhi_preset["candidates"])

    assert compare_resp.status_code == 200
    comparison = compare_resp.json()
    assert comparison["basis"] == "live_station"
    assert comparison["source"] == "CPCB/data.gov.in"
    assert [o["station"]["station_name"] for o in comparison["observations"]] == [
        "ITO",
        "Anand Vihar",
    ]
    assert all(o["provider"] == "CPCB/data.gov.in" for o in comparison["observations"])


@pytest.mark.asyncio
async def test_live_presets_tolerate_provider_city_aliases(monkeypatch):
    live = [
        _cpcb_observation("live_ito", "ITO", 28.6289, 77.2407),
        _cpcb_observation("live_anand_vihar", "Anand Vihar", 28.6469, 77.3160),
        _cpcb_observation("live_bandra", "Bandra", 19.0596, 72.8388, "Bombay", "Maharashtra"),
        _cpcb_observation("live_btm", "BTM Layout", 12.9240, 77.6109, "Bangalore", "Karnataka"),
        _cpcb_observation("live_lalbagh", "Lalbagh", 26.8467, 80.9462, "Lucknow", "Uttar Pradesh"),
        _cpcb_observation(
            "live_victoria", "Victoria Memorial", 22.5448, 88.3426, "Calcutta", "West Bengal"
        ),
    ]
    monkeypatch.setattr(
        comparison_endpoint.comparison_service.air_quality.cpcb_adapter,
        "get_station_observations",
        AsyncMock(return_value=live),
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/stations/comparison-presets")

    assert resp.status_code == 200
    keys = {preset["key"] for preset in resp.json()["presets"]}
    assert keys == {"delhi-corridors", "metro-cross-city", "indo-gangetic-plain"}
