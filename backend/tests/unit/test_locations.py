import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.endpoints import locations
from app.main import app


@pytest.mark.asyncio
async def test_location_proxy_returns_exact_coordinates(monkeypatch):
    async def fake(name):
        assert name == "Patna"
        return [{"id": 1, "name": "Patna", "latitude": 25.5941, "longitude": 85.1376}]

    monkeypatch.setattr(locations, "fetch_geocoding", fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/locations/search", params={"name": "Patna"})
    assert response.status_code == 200
    assert response.json()["results"][0]["latitude"] == 25.5941


@pytest.mark.asyncio
async def test_location_proxy_validates_query_length():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/locations/search", params={"name": "P"})
    assert response.status_code == 422
