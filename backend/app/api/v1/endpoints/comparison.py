import logging

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.comparison import ComparisonPresetsResponse, ComparisonResponse
from app.services.comparison_service import (
    MAX_COMPARISON_STATIONS,
    MIN_COMPARISON_STATIONS,
    ComparisonService,
)

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
    if len(ids) < MIN_COMPARISON_STATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"At least {MIN_COMPARISON_STATIONS} station IDs must be provided for comparison."
            ),
        )
    if len(ids) > MAX_COMPARISON_STATIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"A maximum of {MAX_COMPARISON_STATIONS} stations can be compared simultaneously."
            ),
        )

    resolution = await comparison_service.resolve(ids)
    if len(resolution.observations) < MIN_COMPARISON_STATIONS:
        unresolved = ", ".join(resolution.unresolved_ids) or "none"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Could not retrieve at least two observations. "
                f"Unresolved IDs: {unresolved}. Reload comparison presets and try again."
            ),
        )

    return comparison_service.build_response(ids, resolution)
