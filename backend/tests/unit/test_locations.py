import pytest
from httpx import ASGITransport, AsyncClient, MockTransport, Response

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


@pytest.mark.asyncio
async def test_reverse_endpoint_returns_tier2_locality(monkeypatch):
    async def fake(lat, lon):
        assert (lat, lon) == (11.4953, 77.2793)
        return {
            "name": "Sathyamangalam",
            "state": "Tamil Nadu",
            "country": "India",
            "display_name": "Sathyamangalam, Erode, Tamil Nadu, India",
            "source": "OpenStreetMap Nominatim",
        }

    monkeypatch.setattr(locations, "fetch_reverse_geocoding", fake)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/locations/reverse", params={"lat": 11.4953, "lon": 77.2793}
        )
    assert response.status_code == 200
    assert response.json()["place"]["name"] == "Sathyamangalam"


def test_geocoding_sanitizer_rejects_boolean_coordinates():
    assert (
        locations._sanitize_geocoding_result(
            {"name": "Nowhere", "latitude": True, "longitude": 77.2793}
        )
        is None
    )
    assert (
        locations._sanitize_geocoding_result(
            {"name": "Nowhere", "latitude": 11.4953, "longitude": False}
        )
        is None
    )


def test_reverse_parser_prefers_town_over_county():
    payload = {
        "name": "Sathyamangalam",
        "display_name": "Satyamangalam, Erode, Tamil Nadu, India",
        "address": {"town": "Satyamangalam", "county": "Erode", "state": "Tamil Nadu"},
    }
    place = locations._parse_reverse_payload(payload)
    assert place["name"] == "Satyamangalam"
    assert place["state"] == "Tamil Nadu"
    assert locations._parse_reverse_payload({"address": {}}) is None


@pytest.mark.asyncio
async def test_reverse_geocoding_uses_cache(monkeypatch):
    calls = 0

    def handler(request):
        nonlocal calls
        calls += 1
        assert request.headers["user-agent"] == locations.REVERSE_USER_AGENT
        return Response(
            200,
            json={
                "name": "Sathyamangalam",
                "address": {"town": "Sathyamangalam", "state": "Tamil Nadu"},
            },
        )

    monkeypatch.setattr(
        locations.httpx,
        "AsyncClient",
        lambda **kwargs: AsyncClient(
            transport=MockTransport(handler), headers=kwargs.get("headers", {})
        ),
    )
    locations._reverse_cache.clear()
    locations._last_reverse_request = None
    first = await locations.fetch_reverse_geocoding(11.4953, 77.2793)
    second = await locations.fetch_reverse_geocoding(11.4953, 77.2793)
    assert first["name"] == "Sathyamangalam"
    assert second == first
    assert calls == 1
