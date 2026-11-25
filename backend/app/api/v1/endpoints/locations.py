import logging
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/locations")

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


async def fetch_geocoding(name: str) -> List[Dict[str, Any]]:
    """Server-side geocoding proxy so browsers never call a third-party host directly."""
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=settings.CPCB_CONNECT_TIMEOUT_SECONDS,
                read=settings.CPCB_READ_TIMEOUT_SECONDS,
                write=settings.CPCB_CONNECT_TIMEOUT_SECONDS,
                pool=settings.CPCB_CONNECT_TIMEOUT_SECONDS,
            )
        ) as client:
            response = await client.get(
                GEOCODING_URL,
                params={"name": name, "count": 5, "language": "en", "format": "json"},
            )
    except httpx.HTTPError:
        logger.warning("Geocoding provider request failed.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Location search is temporarily unavailable.",
        ) from None
    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Location search is temporarily unavailable.",
        )
    try:
        payload = response.json()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Location search returned an invalid response.",
        )
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return []
    return [
        item
        for item in results
        if isinstance(item, dict)
        and isinstance(item.get("latitude"), (int, float))
        and isinstance(item.get("longitude"), (int, float))
    ]


@router.get("/search")
async def search_locations(
    name: str = Query(..., min_length=2, max_length=100, description="City or locality name"),
) -> Dict[str, Any]:
    """Resolve a place name to exact coordinates through the backend proxy."""
    results = await fetch_geocoding(name.strip())
    return {"results": results}
