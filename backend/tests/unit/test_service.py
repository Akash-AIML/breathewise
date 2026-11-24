from app.services.air_quality_service import AirQualityService


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
