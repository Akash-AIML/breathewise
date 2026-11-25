from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.api import StationsResponse
from app.schemas.observation import StationMetadata
from app.services.air_quality_service import INDIAN_CITIES_REGISTRY, AirQualityService

router = APIRouter()
air_quality_service = AirQualityService()


@router.get("/stations", response_model=StationsResponse)
async def list_or_search_stations(
    query: Optional[str] = Query(
        None, max_length=100, description="City, state or station search query"
    ),
    city: Optional[str] = Query(None, max_length=100, description="Exact city filter"),
    state: Optional[str] = Query(None, max_length=100, description="Exact state filter"),
    lat: Optional[float] = Query(
        None, ge=-90.0, le=90.0, description="Optional user latitude for proximity search"
    ),
    lon: Optional[float] = Query(
        None, ge=-180.0, le=180.0, description="Optional user longitude for proximity search"
    ),
    max_distance_km: float = Query(
        50.0, ge=1.0, le=500.0, description="Radius in km for nearby stations"
    ),
) -> StationsResponse:
    """
    Discovers real CPCB monitoring stations from live provider data.
    A labelled fallback registry is used only when CPCB has no usable stations.
    """
    if lat is not None and lon is not None:
        stations, source = await air_quality_service.search_nearby_stations_live(
            lat, lon, max_distance_km=max_distance_km
        )
    elif query or city or state:
        stations, source = await air_quality_service.search_stations_live(
            query=query, city=city, state=state
        )
    else:
        stations, source = await air_quality_service.search_stations_live()

    return StationsResponse(
        success=True,
        count=len(stations),
        data=stations,
        message=f"Station metadata source: {source}",
    )


@router.get("/stations/{station_id}", response_model=StationMetadata)
async def get_station_by_id(station_id: str) -> StationMetadata:
    """Retrieves metadata for a specific station identifier."""
    for s in INDIAN_CITIES_REGISTRY:
        if s.station_id == station_id:
            return s.model_copy(update={"provider": "fallback_registry"})

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Station with ID '{station_id}' not found.",
    )
