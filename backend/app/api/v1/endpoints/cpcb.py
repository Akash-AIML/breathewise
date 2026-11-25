from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.adapters.cpcb import CPCBProviderError
from app.core.geo import haversine_distance_km
from app.schemas.cpcb import (
    CPCBFiltersResponse,
    CPCBObservationResponse,
    CPCBObservationsResponse,
)
from app.services.air_quality_service import AirQualityService

router = APIRouter()
air_quality_service = AirQualityService()


def _unavailable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=detail,
    )


@router.get("/air-quality/nearby", response_model=CPCBObservationsResponse)
async def get_nearby_cpcb_observations(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    max_distance_km: float = Query(50.0, ge=1.0, le=500.0),
) -> CPCBObservationsResponse:
    """Return every CPCB station observation near the supplied exact coordinates."""
    try:
        observations = await air_quality_service.cpcb_adapter.get_station_observations()
    except CPCBProviderError:
        raise _unavailable("CPCB observations are temporarily unavailable.")

    nearby = []
    for observation in observations:
        distance = haversine_distance_km(lat, lon, observation.latitude, observation.longitude)
        if distance <= max_distance_km:
            nearby.append((distance, observation.model_copy(update={"distance_km": distance})))
    nearby.sort(key=lambda item: item[0])

    if not nearby:
        return CPCBObservationsResponse(
            success=True,
            count=0,
            data=[],
            message="No CPCB station reports within the requested radius.",
        )

    return CPCBObservationsResponse(
        success=True,
        count=len(nearby),
        data=[observation for _, observation in nearby],
        selected_station_id=nearby[0][1].station_id,
        message=(
            "Distances use haversine great-circle calculation. The selected station is the "
            "nearest reporting monitor, not a measurement at the exact user coordinate."
        ),
    )


@router.get("/air-quality/summary", response_model=CPCBObservationsResponse)
async def get_cpcb_summary(
    city: Optional[str] = Query(None, max_length=100),
    state: Optional[str] = Query(None, max_length=100),
) -> CPCBObservationsResponse:
    """Return CPCB station observations for a city and/or state."""
    if not city and not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of city or state.",
        )
    try:
        observations = await air_quality_service.cpcb_adapter.get_station_observations(
            city=city, state=state
        )
    except CPCBProviderError:
        raise _unavailable("CPCB observations are temporarily unavailable.")

    return CPCBObservationsResponse(
        success=True,
        count=len(observations),
        data=observations,
        message="Source: CPCB / data.gov.in. Pollutant averages are not labelled as AQI.",
    )


@router.get("/air-quality/station/{station_id}", response_model=CPCBObservationResponse)
async def get_cpcb_station(station_id: str) -> CPCBObservationResponse:
    """Return one CPCB station observation, including source timestamp and freshness."""
    try:
        observation = await air_quality_service.cpcb_adapter.get_station_observation(station_id)
    except CPCBProviderError:
        raise _unavailable("CPCB observations are temporarily unavailable.")
    if not observation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CPCB station observation not found.",
        )
    return CPCBObservationResponse(success=True, data=observation)


@router.get("/air-quality/filters/verification", response_model=CPCBFiltersResponse)
async def get_cpcb_filter_verification() -> CPCBFiltersResponse:
    """Expose verified/unverified state for the Tamil Nadu and Chennai filters."""
    try:
        verification = await air_quality_service.cpcb_adapter.verify_filters()
    except CPCBProviderError:
        raise _unavailable("CPCB filter verification is temporarily unavailable.")
    return CPCBFiltersResponse(
        success=True,
        data=verification,
        message="Filters are used only when observed in live records or independently probed.",
    )
