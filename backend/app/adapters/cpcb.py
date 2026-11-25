import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.adapters.base import AirQualityAdapter
from app.adapters.cpcb_parsing import CPCB_POLLUTANT_MAP, CPCBParsingMixin
from app.adapters.cpcb_queries import CPCBQueriesMixin
from app.adapters.cpcb_transport import (
    CPCBConfigurationError,
    CPCBProviderError,
    CPCBRateLimitError,
    CPCBResponseError,
    CPCBTemporaryError,
    CPCBTransportMixin,
    redact_secrets,
)
from app.core.config import settings
from app.core.geo import haversine_distance_km
from app.schemas.cpcb import CPCBStationObservation
from app.schemas.observation import NormalizedObservation, StationMetadata

logger = logging.getLogger(__name__)

__all__ = [
    "CPCBAdapter",
    "CPCBConfigurationError",
    "CPCBProviderError",
    "CPCBRateLimitError",
    "CPCBTemporaryError",
    "CPCBResponseError",
    "CPCB_POLLUTANT_MAP",
    "redact_secrets",
]


class CPCBAdapter(CPCBQueriesMixin, CPCBTransportMixin, CPCBParsingMixin, AirQualityAdapter):
    """
    Async adapter for the CPCB Real-Time Air Quality Index dataset on data.gov.in.

    Resource: 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69
    The adapter never invents units, stations, timestamps, or AQI values.
    """

    RESOURCE_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
    BASE_URL = "https://api.data.gov.in/resource"

    def __init__(
        self,
        api_key: Optional[str] = None,
        station_registry: Optional[List[StationMetadata]] = None,
    ):
        self.api_key = api_key or settings.DATA_GOV_IN_API_KEY
        self.configured = bool(self.api_key)
        self.station_registry = station_registry or []
        self._cache: Dict[str, Tuple[datetime, Any]] = {}
        self._last_valid: Dict[str, Tuple[datetime, List[CPCBStationObservation]]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._circuit_open_until: Optional[datetime] = None
        if not self.configured:
            if settings.ENVIRONMENT.lower() == "production":
                raise CPCBConfigurationError(
                    "DATA_GOV_IN_API_KEY is required in production for the CPCB adapter."
                )
            logger.warning(
                "CPCBAdapter: DATA_GOV_IN_API_KEY not loaded; CPCB provider is disabled."
            )

    @property
    def provider_id(self) -> str:
        return "cpcb_ogd"

    @property
    def provider_name(self) -> str:
        return "Central Pollution Control Board (CPCB / data.gov.in)"

    # ── Public adapter interface ─────────────────────────────────────────────

    async def search_stations(
        self, city: Optional[str] = None, state: Optional[str] = None
    ) -> List[StationMetadata]:
        if not self.configured:
            return []
        try:
            observations = await self.get_station_observations(city=city, state=state)
        except CPCBProviderError as exc:
            logger.warning("CPCBAdapter station search failed: %s", redact_secrets(exc))
            return []
        stations = [
            StationMetadata(
                station_id=obs.station_id,
                station_name=obs.station,
                city=obs.city,
                state=obs.state,
                latitude=obs.latitude,
                longitude=obs.longitude,
                provider="CPCB/data.gov.in",
                source_observation_time=obs.last_update,
            )
            for obs in observations
        ]
        return stations

    async def fetch_by_coordinates(
        self, latitude: float, longitude: float
    ) -> Optional[NormalizedObservation]:
        if not self.configured:
            return None
        try:
            observations = await self.get_station_observations()
        except CPCBProviderError as exc:
            logger.warning("CPCBAdapter coordinate fetch failed: %s", redact_secrets(exc))
            return None

        ranked = sorted(
            (
                (haversine_distance_km(latitude, longitude, obs.latitude, obs.longitude), obs)
                for obs in observations
                if obs.pollutants
            ),
            key=lambda item: item[0],
        )
        if not ranked:
            return None
        distance, observation = ranked[0]
        return self.to_normalized(observation, latitude, longitude, distance)

    async def fetch_nearby(
        self, latitude: float, longitude: float, max_distance_km: float = 50.0
    ) -> List[Tuple[StationMetadata, float]]:
        """Return actual CPCB stations near a user location, sorted by distance."""
        observations = await self.get_station_observations()
        nearby = []
        for obs in observations:
            distance = haversine_distance_km(latitude, longitude, obs.latitude, obs.longitude)
            station = StationMetadata(
                station_id=obs.station_id,
                station_name=obs.station,
                city=obs.city,
                state=obs.state,
                latitude=obs.latitude,
                longitude=obs.longitude,
                distance_km=distance,
                provider="CPCB/data.gov.in",
                source_observation_time=obs.last_update,
            )
            nearby.append((station, distance))
        return sorted(
            (item for item in nearby if item[1] <= max_distance_km), key=lambda item: item[1]
        )

    async def get_station_observation(self, station_id: str) -> Optional[CPCBStationObservation]:
        for obs in await self.get_station_observations():
            if obs.station_id == station_id:
                return obs
        return None

    # Backwards-compatible helper used by existing unit tests.
    def _parse_records_to_observation(
        self, records: List[Dict[str, Any]], lat: float, lon: float
    ) -> Optional[NormalizedObservation]:
        observations = self.parse_records(records)
        if not observations:
            return None
        best = min(
            observations,
            key=lambda obs: haversine_distance_km(lat, lon, obs.latitude, obs.longitude),
        )
        return self.to_normalized(best, lat, lon)
