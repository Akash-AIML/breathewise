import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.comparison import (
    ComparisonDifferential,
    ComparisonPresetsResponse,
    ComparisonResponse,
)
from app.schemas.observation import NormalizedObservation, PollutantType
from app.services.comparison_service import ComparisonService

logger = logging.getLogger(__name__)
router = APIRouter()
comparison_service = ComparisonService()


@router.get("/stations/comparison-presets", response_model=ComparisonPresetsResponse)
async def get_comparison_presets() -> ComparisonPresetsResponse:
    """Return presets derived from live stations, or clearly labelled grid estimates."""
    presets, source, message = await comparison_service.get_presets()
    return ComparisonPresetsResponse(
        success=True,
        source=source,
        presets=presets,
        message=message,
    )


@router.get("/stations/compare", response_model=ComparisonResponse)
async def compare_stations(
    station_ids: str = Query(
        ...,
        description="Comma-separated IDs from /stations/comparison-presets",
        max_length=200,
    ),
) -> ComparisonResponse:
    """Compare observations for live stations or labelled coordinate-grid estimates."""
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

    resolution = await comparison_service.resolve(ids)
    observations: list[NormalizedObservation] = resolution.observations
    if len(observations) < 2:
        unresolved = ", ".join(resolution.unresolved_ids) or "none"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Could not retrieve at least two observations. "
                f"Unresolved IDs: {unresolved}. Reload comparison presets and try again."
            ),
        )

    differential: ComparisonDifferential | None = None
    valid_aqi_obs = [o for o in observations if o.calculated_aqi is not None]
    if len(valid_aqi_obs) >= 2:
        sorted_by_aqi = sorted(valid_aqi_obs, key=lambda x: x.calculated_aqi or 0)
        cleanest = sorted_by_aqi[0]
        worst = sorted_by_aqi[-1]
        aqi_diff = (worst.calculated_aqi or 0) - (cleanest.calculated_aqi or 0)

        def pm25(observation) -> float:
            reading = observation.readings.get(PollutantType.PM2_5.value)
            return reading.value if reading else 0.0

        pm25_diff = round(pm25(worst) - pm25(cleanest), 1)
        basis_label = {
            "live_station": "Live stations",
            "coordinate_estimate": "Grid estimates",
            "mixed": "Mixed sources",
        }[resolution.basis]
        summary = (
            f"{basis_label}: {cleanest.station.station_name} reports cleaner air "
            f"({cleanest.calculated_aqi} AQI) compared to "
            f"{worst.station.station_name} ({worst.calculated_aqi} AQI), "
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

    message = (
        "Live CPCB station observations."
        if resolution.basis == "live_station"
        else (
            "Coordinate-grid estimates at registered locations, not physical station observations."
            if resolution.basis == "coordinate_estimate"
            else "Mixed live stations and coordinate-grid estimates."
        )
    )
    if resolution.unresolved_ids:
        message += f" Unresolved IDs: {', '.join(resolution.unresolved_ids)}."

    return ComparisonResponse(
        success=True,
        stations_count=len(observations),
        observations=observations,
        differential=differential,
        basis=resolution.basis,
        source=resolution.source,
        requested_ids=ids,
        unresolved_ids=resolution.unresolved_ids,
        message=message,
    )
