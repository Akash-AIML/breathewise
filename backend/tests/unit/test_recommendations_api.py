import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_generate_plan_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "lat": 28.6139,
            "lon": 77.2090,
            "profile": {
                "has_children": True,
                "has_respiratory_sensitivity": True,
                "commute_method": "two_wheeler",
                "home_area_sqft": 750,
            },
        }
        resp = await client.post("/api/v1/recommendations/plan", json=payload)
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == "no-store"
        data = resp.json()
        assert "environmental_assessment" in data
        assert "morning_recommendations" in data
        assert "indoor_guidance" in data
        assert "sustainable_alternatives" in data
        assert len(data["morning_recommendations"]) >= 1


@pytest.mark.asyncio
async def test_get_indoor_guidance_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/recommendations/indoor", params={"area_sqft": 800, "aqi": 250}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["hepa_sizing_cadr_m3_hr"] > 0
        assert len(data["filter_maintenance_tips"]) >= 3
        assert "NASA" in data["houseplant_scientific_disclaimer"]


@pytest.mark.asyncio
async def test_get_sustainable_alternatives_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/recommendations/sustainable-alternatives", params={"aqi": 320}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 3
        modes = [item["mode"] for item in data]
        assert any("Metro" in m for m in modes)
        assert any("Cycling" in m for m in modes)
