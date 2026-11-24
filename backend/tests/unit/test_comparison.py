import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_compare_stations_insufficient_ids():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Only 1 station provided
        resp = await client.get("/api/v1/stations/compare", params={"station_ids": "cpcb_delhi_ito"})
        assert resp.status_code == 400
        assert "At least 2 station IDs" in resp.json()["message"]


@pytest.mark.asyncio
async def test_compare_stations_too_many_ids():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 5 stations provided
        resp = await client.get(
            "/api/v1/stations/compare",
            params={"station_ids": "s1,s2,s3,s4,s5"},
        )
        assert resp.status_code == 400
        assert "maximum of 4 stations" in resp.json()["message"]


@pytest.mark.asyncio
async def test_compare_two_valid_stations():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/stations/compare",
            params={"station_ids": "cpcb_delhi_ito,cpcb_mumbai_bandra"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["stations_count"] == 2
        assert len(data["observations"]) == 2
        assert data["differential"] is not None
        assert "compared to" in data["differential"]["summary"]
