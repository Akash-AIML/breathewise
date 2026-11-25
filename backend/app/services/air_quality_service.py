import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from app.adapters.cpcb import CPCBAdapter
from app.adapters.openaq import OpenAQAdapter
from app.adapters.openmeteo import OpenMeteoAdapter
from app.core.cache import enforce_limit, prune_expired
from app.core.config import settings
from app.core.geo import haversine_distance_km
from app.schemas.observation import (
    DataQualityStatus,
    NormalizedObservation,
    StationMetadata,
)

logger = logging.getLogger(__name__)

# Predefined verified Indian city centers and key stations
INDIAN_CITIES_REGISTRY: List[StationMetadata] = [
    StationMetadata(
        station_id="cpcb_delhi_ito",
        station_name="ITO, Central Delhi",
        city="Delhi",
        state="Delhi",
        latitude=28.6289,
        longitude=77.2407,
    ),
    StationMetadata(
        station_id="cpcb_delhi_anand_vihar",
        station_name="Anand Vihar, East Delhi",
        city="Delhi",
        state="Delhi",
        latitude=28.6469,
        longitude=77.3160,
    ),
    StationMetadata(
        station_id="cpcb_mumbai_bandra",
        station_name="Bandra Kurla Complex, Mumbai",
        city="Mumbai",
        state="Maharashtra",
        latitude=19.0657,
        longitude=72.8687,
    ),
    StationMetadata(
        station_id="cpcb_bengaluru_btm",
        station_name="BTM Layout, Bengaluru",
        city="Bengaluru",
        state="Karnataka",
        latitude=12.9166,
        longitude=77.6101,
    ),
    StationMetadata(
        station_id="cpcb_kolkata_victoria",
        station_name="Victoria Memorial, Kolkata",
        city="Kolkata",
        state="West Bengal",
        latitude=22.5448,
        longitude=88.3426,
    ),
    StationMetadata(
        station_id="cpcb_chennai_alandur",
        station_name="Alandur, Chennai",
        city="Chennai",
        state="Tamil Nadu",
        latitude=13.0033,
        longitude=80.2014,
    ),
    StationMetadata(
        station_id="cpcb_hyderabad_sanathnagar",
        station_name="Sanathnagar, Hyderabad",
        city="Hyderabad",
        state="Telangana",
        latitude=17.4589,
        longitude=78.4347,
    ),
    StationMetadata(
        station_id="cpcb_ahmedabad_maninagar",
        station_name="Maninagar, Ahmedabad",
        city="Ahmedabad",
        state="Gujarat",
        latitude=22.9984,
        longitude=72.6033,
    ),
    StationMetadata(
        station_id="cpcb_pune_shivajinagar",
        station_name="Shivajinagar, Pune",
        city="Pune",
        state="Maharashtra",
        latitude=18.5314,
        longitude=73.8446,
    ),
    StationMetadata(
        station_id="cpcb_lucknow_lalbagh",
        station_name="Lalbagh, Lucknow",
        city="Lucknow",
        state="Uttar Pradesh",
        latitude=26.8467,
        longitude=80.9462,
    ),
]


class CacheEntry:
    def __init__(self, observation: NormalizedObservation, expires_at: datetime):
        self.observation = observation
        self.expires_at = expires_at

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at


class AirQualityService:
    """
    Core orchestrator for air quality data retrieval, validation,
    caching, provenance tracking, and multi-provider failover.
    """

    def __init__(self):
        self.cpcb_adapter = CPCBAdapter(station_registry=INDIAN_CITIES_REGISTRY)
        self.openaq_adapter = OpenAQAdapter()
        self.openmeteo_adapter = OpenMeteoAdapter()
        self._cache: Dict[str, CacheEntry] = {}

    def _get_cache_key(self, lat: float, lon: float) -> str:
        # Match the upstream request precision (~11 m) so nearby precise
        # locations do not silently share an observation.
        return f"{round(lat, 4)}:{round(lon, 4)}"

    def check_stale_status(self, observation: NormalizedObservation) -> NormalizedObservation:
        """Flags observations older than STALE_DATA_THRESHOLD_HOURS as STALE."""
        now = datetime.now(timezone.utc)
        meas_time = observation.measurement_timestamp
        if meas_time.tzinfo is None:
            meas_time = meas_time.replace(tzinfo=timezone.utc)

        age = now - meas_time
        if age > timedelta(hours=settings.STALE_DATA_THRESHOLD_HOURS):
            note = f"Data is {round(age.total_seconds() / 3600, 1)} hours old (threshold is {settings.STALE_DATA_THRESHOLD_HOURS}h)"
            if not observation.notes or note not in observation.notes:
                observation.data_quality_status = DataQualityStatus.STALE
                observation.notes = f"{observation.notes}; {note}" if observation.notes else note
        return observation

    async def get_air_quality_for_coordinates(
        self, latitude: float, longitude: float, bypass_cache: bool = False
    ) -> Optional[NormalizedObservation]:
        """
        Coordinates-aware air quality retrieval with strict multi-source fallback:
        1. In-memory TTL cache lookup
        2. CPCB OGD adapter (if configured and available)
        3. OpenAQ v3 adapter (if configured and available)
        4. Open-Meteo High-Resolution CAMS adapter (verified real-time live data)
        5. Returns None (Honest unavailable state) if all providers fail
        """
        # Validate coordinates bounds
        if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
            raise ValueError(f"Invalid coordinates: latitude={latitude}, longitude={longitude}")

        cache_key = self._get_cache_key(latitude, longitude)
        if not bypass_cache and cache_key in self._cache:
            entry = self._cache[cache_key]
            if not entry.is_expired():
                logger.debug("Serving air quality from cache for %s", cache_key)
                # Return a copy: callers must not be able to mutate shared cache
                # state, and staleness must be re-evaluated on every hit.
                return self.check_stale_status(entry.observation.model_copy(deep=True))
            # Delete expired entries instead of leaving them to accumulate.
            self._cache.pop(cache_key, None)

        observation: Optional[NormalizedObservation] = None

        # Tier 1: CPCB (Primary Official Source)
        try:
            observation = await self.cpcb_adapter.fetch_by_coordinates(latitude, longitude)
        except Exception as e:
            logger.warning("Tier 1 CPCB failed: %s", str(e))

        # Tier 2: OpenAQ (Secondary Source)
        if not observation:
            try:
                observation = await self.openaq_adapter.fetch_by_coordinates(latitude, longitude)
            except Exception as e:
                logger.warning("Tier 2 OpenAQ failed: %s", str(e))

        # Tier 3: Open-Meteo Environmental Grid (Verified Real-Time Source)
        if not observation:
            try:
                observation = await self.openmeteo_adapter.fetch_by_coordinates(latitude, longitude)
            except Exception as e:
                logger.warning("Tier 3 Open-Meteo failed: %s", str(e))

        if observation:
            # Check for stale timestamp
            observation = self.check_stale_status(observation)

            # Calculate distance to station if physical coordinates exist
            if observation.station.distance_km is None:
                observation.station.distance_km = haversine_distance_km(
                    latitude, longitude, observation.station.latitude, observation.station.longitude
                )

            # Store an immutable-to-callers copy in cache
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.CACHE_TTL_SECONDS)
            self._cache[cache_key] = CacheEntry(observation.model_copy(deep=True), expires_at)
            prune_expired(self._cache, lambda entry: entry.expires_at)
            enforce_limit(self._cache, settings.CACHE_MAX_ENTRIES)
            return observation

        # Honest unavailable state: return None
        return None

    def search_nearby_stations(
        self, latitude: float, longitude: float, max_distance_km: float = 50.0
    ) -> List[Tuple[StationMetadata, float]]:
        """Returns stations from the registry within max_distance_km, sorted by distance."""
        results = []
        for station in INDIAN_CITIES_REGISTRY:
            dist = haversine_distance_km(latitude, longitude, station.latitude, station.longitude)
            if dist <= max_distance_km:
                station_copy = station.model_copy(update={"provider": "fallback_registry"})
                station_copy.distance_km = dist
                results.append((station_copy, dist))

        results.sort(key=lambda x: x[1])
        return results

    async def search_nearby_stations_live(
        self, latitude: float, longitude: float, max_distance_km: float = 50.0
    ) -> Tuple[List[StationMetadata], str]:
        """Prefer real CPCB stations; fall back to the labelled static registry."""
        try:
            stations = await self.cpcb_adapter.fetch_nearby(latitude, longitude, max_distance_km)
        except Exception as exc:
            logger.warning("Live station search failed: %s", str(exc))
            stations = []
        if stations:
            return [station for station, _ in stations], "CPCB/data.gov.in"
        return [
            station
            for station, _ in self.search_nearby_stations(latitude, longitude, max_distance_km)
        ], "fallback_registry"

    async def search_stations_live(
        self,
        query: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
    ) -> Tuple[List[StationMetadata], str]:
        """Search real CPCB station metadata, with a labelled registry fallback."""
        observations = []
        try:
            observations = await self.cpcb_adapter.get_station_observations(city=city, state=state)
        except Exception as exc:
            logger.warning("Live CPCB station search failed: %s", str(exc))

        needle = (query or "").strip().lower()
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
            if not needle
            or needle in obs.station.lower()
            or needle in obs.city.lower()
            or needle in obs.state.lower()
        ]
        if stations:
            return stations, "CPCB/data.gov.in"

        fallback = self.search_stations_by_query(query or city or state or "")
        return [
            station.model_copy(update={"provider": "fallback_registry"}) for station in fallback
        ], "fallback_registry"

    def search_stations_by_query(self, query: str) -> List[StationMetadata]:
        """Case-insensitive search across station names, cities, and states."""
        q = query.strip().lower()
        if not q:
            return INDIAN_CITIES_REGISTRY

        matches = []
        for station in INDIAN_CITIES_REGISTRY:
            if (
                q in station.station_name.lower()
                or q in station.city.lower()
                or q in station.state.lower()
            ):
                matches.append(station)
        return matches
