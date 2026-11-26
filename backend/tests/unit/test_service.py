from datetime import UTC, datetime, timedelta

import pytest

from app.schemas.observation import (
    DataQualityStatus,
    NormalizedObservation,
    StationMetadata,
)
from app.services.air_quality_service import AirQualityService, CacheEntry


def test_station_registry_search_by_city():
    service = AirQualityService()
    results = service.search_stations_by_query("delhi")
    assert len(results) >= 2
    for r in results:
        assert "delhi" in r.city.lower() or "delhi" in r.station_name.lower()


def test_station_registry_search_empty_returns_all():
    service = AirQualityService()
    results = service.search_stations_by_query("")
    assert len(results) >= 10


@pytest.mark.asyncio
async def test_cache_uses_precise_coordinates_and_returns_isolated_copy():
    service = AirQualityService()
    observation = NormalizedObservation(
        provider="openmeteo_cams",
        station=StationMetadata(
            station_id="grid",
            station_name="Grid",
            city="",
            state="",
            latitude=28.6289,
            longitude=77.2407,
        ),
        measurement_timestamp=datetime.now(UTC),
        retrieval_timestamp=datetime.now(UTC),
        data_quality_status=DataQualityStatus.VERIFIED,
    )
    service._cache[service._get_cache_key(28.6289, 77.2407)] = CacheEntry(
        observation, datetime.now(UTC) + timedelta(minutes=5)
    )

    result = await service.get_air_quality_for_coordinates(28.6289, 77.2407)
    assert result is not None
    result.station.station_name = "mutated"
    result.data_quality_status = DataQualityStatus.STALE
    cached = await service.get_air_quality_for_coordinates(28.6289, 77.2407)
    assert cached is not None
    assert cached.station.station_name == "Grid"
    assert cached.data_quality_status == DataQualityStatus.VERIFIED

    # A nearby but distinct precise location must not hit the same cache entry.
    assert service._get_cache_key(28.6290, 77.2407) != service._get_cache_key(28.6289, 77.2407)


def test_nearby_stations_discovery():
    service = AirQualityService()
    # Near central Delhi (28.61, 77.21)
    nearby = service.search_nearby_stations(28.61, 77.21, max_distance_km=25.0)
    assert len(nearby) >= 1
    # Check that results are sorted ascending by distance
    distances = [dist for _, dist in nearby]
    assert distances == sorted(distances)
    # Closest station has distance under 15 km
    assert distances[0] < 15.0
