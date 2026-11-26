import logging

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from app.adapters.cpcb_transport import CPCBProviderError
from app.core.config import settings
from app.schemas.api import AirQualityResponse
from app.services.air_quality_service import AirQualityService

logger = logging.getLogger(__name__)
router = APIRouter()
air_quality_service = AirQualityService()


@router.get("/air-quality", response_model=AirQualityResponse)
async def get_air_quality(
    lat: float = Query(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees"),
    lon: float = Query(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees"),
    bypass_cache: bool = Query(False, description="Whether to bypass internal in-memory cache"),
) -> AirQualityResponse:
    """
    Fetches verified, normalized air quality observations for given geographic coordinates.
    Evaluates official CPCB AQI using multi-tier fallback.
    Returns honest unavailable response if all external sources fail.
    """
    if bypass_cache and settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cache bypass is disabled in production.",
        )

    try:
        observation = await air_quality_service.get_air_quality_for_coordinates(
            latitude=lat, longitude=lon, bypass_cache=bypass_cache
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        ) from e
    except (httpx.HTTPError, TimeoutError, CPCBProviderError, RuntimeError) as e:
        logger.error("Error retrieving air quality for (%s, %s): %s", lat, lon, str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve air quality data. Please retry shortly.",
        ) from e

    if not observation:
        return AirQualityResponse(
            success=False,
            data=None,
            message="No active monitoring stations or environmental observations available for this location.",
        )

    return AirQualityResponse(
        success=True,
        data=observation,
        message=f"Air quality data retrieved from {observation.provider}.",
    )
