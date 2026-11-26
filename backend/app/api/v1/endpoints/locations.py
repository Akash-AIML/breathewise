import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from app.core.cache import bound_locks, enforce_limit, prune_expired
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/locations")

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
REVERSE_GEOCODING_URL = "https://nominatim.openstreetmap.org/reverse"
# OpenStreetMap Nominatim usage policy: identify the client and stay under 1 req/s.
REVERSE_USER_AGENT = "BreatheWise/1.0 (air-quality-assistant)"
REVERSE_MIN_INTERVAL_SECONDS = 1.1
REVERSE_CACHE_TTL_SECONDS = 3600
HTTP_OK = 200
MIN_NAME_LENGTH = 2
MAX_GEOCODING_FIELD_LENGTH = 100
GEOCODING_FIELDS = ("id", "name", "latitude", "longitude", "admin1", "country")
NUMERIC_GEOCODING_FIELDS = frozenset({"id", "latitude", "longitude"})

_reverse_cache: dict[tuple[float, float], tuple[datetime, dict[str, Any] | None]] = {}
_reverse_locks: dict[tuple[float, float], asyncio.Lock] = {}
_pace_lock = asyncio.Lock()
_last_reverse_request: datetime | None = None


async def _request_geocoding_payload(name: str) -> Any:
    """Fetch raw geocoding JSON from the upstream provider."""
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
    except httpx.HTTPError as exc:
        logger.warning("Geocoding provider request failed (%s).", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Location search is temporarily unavailable.",
        ) from exc
    if response.status_code != HTTP_OK:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Location search is temporarily unavailable.",
        )
    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Location search returned an invalid response.",
        ) from exc


def _is_coordinate_number(value: Any) -> bool:
    """Booleans are ints in Python but are never valid geographic coordinates."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _sanitize_geocoding_result(item: dict[str, Any]) -> dict[str, Any] | None:
    """Allowlist and bound one geocoding result, rejecting entries without coordinates."""
    has_coords = _is_coordinate_number(item.get("latitude")) and _is_coordinate_number(
        item.get("longitude")
    )
    if not has_coords:
        return None
    entry: dict[str, Any] = {}
    for field in GEOCODING_FIELDS:
        value = item.get(field)
        if isinstance(value, str):
            entry[field] = value[:MAX_GEOCODING_FIELD_LENGTH]
        elif field in NUMERIC_GEOCODING_FIELDS and _is_coordinate_number(value):
            entry[field] = value
    return entry if entry.get("name") else None


def _sanitize_geocoding_results(payload: Any) -> list[dict[str, Any]]:
    """Keep only allowlisted, bounded geocoding fields."""
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list):
        return []
    return [
        entry
        for item in results
        if isinstance(item, dict) and (entry := _sanitize_geocoding_result(item)) is not None
    ]


async def fetch_geocoding(name: str) -> list[dict[str, Any]]:
    """Server-side geocoding proxy so browsers never call a third-party host directly."""
    payload = await _request_geocoding_payload(name)
    return _sanitize_geocoding_results(payload)


@router.get("/search")
async def search_locations(
    name: str = Query(..., min_length=2, max_length=100, description="City or locality name"),
) -> dict[str, Any]:
    """Resolve a place name to exact coordinates through the backend proxy."""
    cleaned_name = name.strip()
    if len(cleaned_name) < MIN_NAME_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Location name must contain at least {MIN_NAME_LENGTH} non-whitespace characters."
            ),
        )
    results = await fetch_geocoding(cleaned_name)
    return {"results": results}


def _reverse_cache_key(lat: float, lon: float) -> tuple[float, float]:
    # ~100 m resolution: enough for a place label, without hammering Nominatim
    # for every small movement of a device GPS fix.
    return round(lat, 3), round(lon, 3)


def _parse_reverse_payload(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    raw_address = payload.get("address")
    address: dict[str, Any] = raw_address if isinstance(raw_address, dict) else {}
    name = (
        address.get("town")
        or address.get("village")
        or address.get("city")
        or address.get("county")
        or payload.get("name")
    )
    if not name:
        return None
    return {
        "name": str(name),
        "state": address.get("state") or address.get("region"),
        "country": address.get("country"),
        "display_name": payload.get("display_name"),
        "source": "OpenStreetMap Nominatim",
    }


async def fetch_reverse_geocoding(lat: float, lon: float) -> dict[str, Any] | None:
    """Resolve exact coordinates to a locality name. Never blocks the UI on failure."""
    global _last_reverse_request  # noqa: PLW0603 - shared module-level pacing state
    key = _reverse_cache_key(lat, lon)

    cached = _reverse_cache.get(key)
    if cached and datetime.now(UTC) < cached[0]:
        return cached[1]

    # Per-key coalescing: different locations do not queue behind one global
    # lock, while repeated lookups for the same key share a single provider call.
    bound_locks(_reverse_locks, settings.CACHE_MAX_ENTRIES - 1)
    key_lock = _reverse_locks.setdefault(key, asyncio.Lock())
    async with key_lock:
        cached = _reverse_cache.get(key)
        if cached and datetime.now(UTC) < cached[0]:
            return cached[1]

        # Nominatim asks for at most one request/second. Only the pacing
        # decision is serialized; the HTTP call below is not.
        async with _pace_lock:
            now = datetime.now(UTC)
            if _last_reverse_request is not None:
                elapsed = (now - _last_reverse_request).total_seconds()
                if elapsed < REVERSE_MIN_INTERVAL_SECONDS:
                    await asyncio.sleep(REVERSE_MIN_INTERVAL_SECONDS - elapsed)
            _last_reverse_request = datetime.now(UTC)

        place: dict[str, Any] | None = None
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=3.0),
                headers={"User-Agent": REVERSE_USER_AGENT, "Accept-Language": "en"},
            ) as client:
                response = await client.get(
                    REVERSE_GEOCODING_URL,
                    params={
                        "format": "jsonv2",
                        "lat": lat,
                        "lon": lon,
                        "zoom": 10,
                        "addressdetails": 1,
                    },
                )
            if response.status_code == HTTP_OK:
                place = _parse_reverse_payload(response.json())
            else:
                logger.warning("Reverse geocoding returned HTTP %s.", response.status_code)
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Reverse geocoding failed: %s", type(exc).__name__)

        _reverse_cache[key] = (
            datetime.now(UTC) + timedelta(seconds=REVERSE_CACHE_TTL_SECONDS),
            place,
        )
        prune_expired(_reverse_cache, lambda entry: entry[0])
        enforce_limit(_reverse_cache, settings.CACHE_MAX_ENTRIES)
        return place


@router.get("/reverse")
async def reverse_locations(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
) -> dict[str, Any]:
    """Return the nearest named locality for exact coordinates, or null if unavailable."""
    return {"place": await fetch_reverse_geocoding(lat, lon)}
