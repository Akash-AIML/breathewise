import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.comparison import ComparisonDifferential, ComparisonResponse
from app.schemas.observation import NormalizedObservation, PollutantType
from app.services.air_quality_service import INDIAN_CITIES_REGISTRY, AirQualityService

logger = logging.getLogger(__name__)
router = APIRouter()
air_quality_service = AirQualityService()


@router.get("/stations/compare", response_model=ComparisonResponse)
async def compare_stations(
    station_ids: str = Query(
        ...,
        description="Comma-separated station IDs to compare (e.g. 'cpcb_delhi_ito,cpcb_delhi_anand_vihar')",
        max_length=200,
    ),
) -> ComparisonResponse:
    """
    Compares real-time air quality observations across multiple monitoring stations.
    Calculates differential AQI, identifies cleanest vs most polluted zones,
    and returns full observation breakdowns for side-by-side analysis.
    """
    ids = [s.strip() for s in station_ids.split(",") if s.strip()]
    if len(ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least 2 station IDs must be provided for comparison.",
        )
    if len(ids) > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A maximum of 4 stations can be compared simultaneously.",
        )

    observations: List[NormalizedObservation] = []
    station_lookup = {s.station_id: s for s in INDIAN_CITIES_REGISTRY}

    for sid in ids:
        station_meta = station_lookup.get(sid)
        if not station_meta:
            continue
        try:
            obs = await air_quality_service.get_air_quality_for_coordinates(
                latitude=station_meta.latitude, longitude=station_meta.longitude
            )
            if obs:
                # Override station name with registered physical station name
                obs.station.station_id = station_meta.station_id
                obs.station.station_name = station_meta.station_name
                obs.station.city = station_meta.city
                obs.station.state = station_meta.state
                observations.append(obs)
        except Exception as e:
            logger.warning("Failed to fetch comparison observation for %s: %s", sid, str(e))

    if not observations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Could not retrieve observations for the requested stations.",
        )

    # Compute differential analysis if multiple observations retrieved
    differential: Optional[ComparisonDifferential] = None
    valid_aqi_obs = [o for o in observations if o.calculated_aqi is not None]

    if len(valid_aqi_obs) >= 2:
        sorted_by_aqi = sorted(valid_aqi_obs, key=lambda x: x.calculated_aqi or 0)
        cleanest = sorted_by_aqi[0]
        worst = sorted_by_aqi[-1]

        aqi_diff = (worst.calculated_aqi or 0) - (cleanest.calculated_aqi or 0)

        # Calculate PM2.5 difference if available
        cleanest_pm25 = (
            cleanest.readings.get(PollutantType.PM2_5.value).value
            if PollutantType.PM2_5.value in cleanest.readings
            else 0.0
        )
        worst_pm25 = (
            worst.readings.get(PollutantType.PM2_5.value).value
            if PollutantType.PM2_5.value in worst.readings
            else 0.0
        )
        pm25_diff = round(worst_pm25 - cleanest_pm25, 1)

        summary = (
            f"{cleanest.station.station_name} reports cleaner air ({cleanest.calculated_aqi} AQI) "
            f"compared to {worst.station.station_name} ({worst.calculated_aqi} AQI), "
            f"with an AQI difference of {aqi_diff} points."
        )

        differential = ComparisonDifferential(
            cleanest_station_id=cleanest.station.station_id,
            cleanest_station_name=cleanest.station.station_name,
            most_polluted_station_id=worst.station.station_id,
            most_polluted_station_name=worst.station.station_name,
            aqi_difference=aqi_diff,
            pm25_difference_ug_m3=pm25_diff,
            summary=summary,
        )

    return ComparisonResponse(
        success=True,
        stations_count=len(observations),
        observations=observations,
        differential=differential,
    )
