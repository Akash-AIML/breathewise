from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest

from app.schemas.observation import (
    DataQualityStatus,
    NormalizedObservation,
    NormalizedPollutantReading,
    PollutantType,
    StationMetadata,
)
from app.services.air_quality_service import AirQualityService, haversine_distance_km


@pytest.fixture
def service():
    return AirQualityService()


@pytest.fixture
def sample_observation():
    return NormalizedObservation(
        provider="test_provider",
        station=StationMetadata(
            station_id="test_stn",
            station_name="Test Station",
            city="Delhi",
            state="Delhi",
            latitude=28.61,
            longitude=77.21,
        ),
        readings={
            "PM2.5": NormalizedPollutantReading(
                pollutant=PollutantType.PM2_5, value=45.0, unit="µg/m³"
            ),
            "PM10": NormalizedPollutantReading(
                pollutant=PollutantType.PM10, value=85.0, unit="µg/m³"
            ),
            "NO2": NormalizedPollutantReading(
                pollutant=PollutantType.NO2, value=40.0, unit="µg/m³"
            ),
        },
        calculated_aqi=75,
        dominant_pollutant=PollutantType.PM2_5,
        data_sufficiency_met=True,
        measurement_timestamp=datetime.now(UTC),
        retrieval_timestamp=datetime.now(UTC),
        data_quality_status=DataQualityStatus.VERIFIED,
    )


def test_haversine_distance_calculation():
    # Delhi to Mumbai distance is ~1148 km
    dist = haversine_distance_km(28.6139, 77.2090, 19.0760, 72.8777)
    assert 1140 <= dist <= 1160


def test_stale_measurement_detection(service, sample_observation):
    # Set measurement timestamp to 8 hours ago (threshold is 6h)
    sample_observation.measurement_timestamp = datetime.now(UTC) - timedelta(hours=8)
    checked = service.check_stale_status(sample_observation)
    assert checked.data_quality_status == DataQualityStatus.STALE
    assert "hours old" in checked.notes


def test_fresh_measurement_preserves_verified_status(service, sample_observation):
    sample_observation.measurement_timestamp = datetime.now(UTC) - timedelta(minutes=30)
    checked = service.check_stale_status(sample_observation)
    assert checked.data_quality_status == DataQualityStatus.VERIFIED


@pytest.mark.asyncio
async def test_invalid_coordinates_raises_value_error(service):
    with pytest.raises(ValueError):
        await service.get_air_quality_for_coordinates(120.0, 77.0)

    with pytest.raises(ValueError):
        await service.get_air_quality_for_coordinates(28.0, 200.0)


@pytest.mark.asyncio
async def test_failover_chain_cpcb_to_openaq_to_openmeteo(service, sample_observation):
    # Mock Tier 1 (CPCB) raising error, Tier 2 (OpenAQ) returning None, Tier 3 (OpenMeteo) succeeding
    service.cpcb_adapter.fetch_by_coordinates = AsyncMock(
        side_effect=Exception("CPCB Rate Limited")
    )
    service.openaq_adapter.fetch_by_coordinates = AsyncMock(return_value=None)
    service.openmeteo_adapter.fetch_by_coordinates = AsyncMock(return_value=sample_observation)

    result = await service.get_air_quality_for_coordinates(28.61, 77.21, bypass_cache=True)
    assert result is not None
    assert result.station.station_id == "test_stn"
    assert service.cpcb_adapter.fetch_by_coordinates.called
    assert service.openaq_adapter.fetch_by_coordinates.called
    assert service.openmeteo_adapter.fetch_by_coordinates.called


@pytest.mark.asyncio
async def test_all_providers_failing_returns_honest_unavailable_state(service):
    # When every provider fails or times out, system returns None rather than generating synthetic data
    service.cpcb_adapter.fetch_by_coordinates = AsyncMock(
        side_effect=httpx.TimeoutException("Timeout")
    )
    service.openaq_adapter.fetch_by_coordinates = AsyncMock(
        side_effect=httpx.HTTPError("500 Error")
    )
    service.openmeteo_adapter.fetch_by_coordinates = AsyncMock(
        side_effect=httpx.ConnectError("Network Down")
    )

    result = await service.get_air_quality_for_coordinates(28.61, 77.21, bypass_cache=True)
    assert result is None  # Honest unavailable state, never synthetic!


@pytest.mark.asyncio
async def test_caching_deduplication(service, sample_observation):
    service.openmeteo_adapter.fetch_by_coordinates = AsyncMock(return_value=sample_observation)

    # First call: hits adapter
    res1 = await service.get_air_quality_for_coordinates(28.6139, 77.2090)
    assert res1 is not None
    assert service.openmeteo_adapter.fetch_by_coordinates.call_count == 1

    # Second call for same coordinates: served from cache without calling adapter again
    res2 = await service.get_air_quality_for_coordinates(28.6139, 77.2090)
    assert res2 is not None
    assert service.openmeteo_adapter.fetch_by_coordinates.call_count == 1  # Deduplicated!
