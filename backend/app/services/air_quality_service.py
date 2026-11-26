import logging
from datetime import UTC, datetime, timedelta

import httpx

from app.adapters.cpcb import (
    CPCBAdapter,
    CPCBConfigurationError,
    CPCBProviderError,
    redact_secrets,
)
from app.adapters.openaq import OpenAQAdapter
from app.adapters.openmeteo import OpenMeteoAdapter
from app.core.cache import enforce_limit, prune_expired
from app.core.config import settings
from app.core.geo import (
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MIN_LATITUDE,
    MIN_LONGITUDE,
    haversine_distance_km,
)
from app.schemas.cpcb import CPCBStationObservation
from app.schemas.observation import (
    DataQualityStatus,
    NormalizedObservation,
    StationMetadata,
)

logger = logging.getLogger(__name__)

# Known provider failure modes. A tier may fail but must never abort failover.
PROVIDER_FETCH_ERRORS = (
    CPCBProviderError,
    CPCBConfigurationError,
    httpx.HTTPError,
    TimeoutError,
    ValueError,
    KeyError,
    TypeError,
)

# Predefined verified Indian city centers and key stations
INDIAN_CITIES_REGISTRY: list[StationMetadata] = [
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
        return datetime.now(UTC) > self.expires_at


class AirQualityService:
    """
    Core orchestrator for air quality data retrieval, validation,
    caching, provenance tracking, and multi-provider failover.
    """

    def __init__(self) -> None:
        self.cpcb_adapter = CPCBAdapter(station_registry=INDIAN_CITIES_REGISTRY)
        self.openaq_adapter = OpenAQAdapter()
        self.openmeteo_adapter = OpenMeteoAdapter()
        self._cache: dict[str, CacheEntry] = {}

    def _get_cache_key(self, lat: float, lon: float) -> str:
        # Match the upstream request precision (~11 m) so nearby precise
        # locations do not silently share an observation.
        return f"{round(lat, 4)}:{round(lon, 4)}"

    def check_stale_status(self, observation: NormalizedObservation) -> NormalizedObservation:
        """Flags observations older than STALE_DATA_THRESHOLD_HOURS as STALE."""
        now = datetime.now(UTC)
        meas_time = observation.measurement_timestamp
        if meas_time.tzinfo is None:
            meas_time = meas_time.replace(tzinfo=UTC)

        age = now - meas_time
        if age > timedelta(hours=settings.STALE_DATA_THRESHOLD_HOURS):
            note = f"Data is {round(age.total_seconds() / 3600, 1)} hours old (threshold is {settings.STALE_DATA_THRESHOLD_HOURS}h)"
            if not observation.notes or note not in observation.notes:
                observation.data_quality_status = DataQualityStatus.STALE
                observation.notes = f"{observation.notes}; {note}" if observation.notes else note
        return observation

    async def _fetch_from_tiers(
        self, latitude: float, longitude: float
    ) -> NormalizedObservation | None:
        tiers = (
            ("Tier 1 CPCB", self.cpcb_adapter),
            ("Tier 2 OpenAQ", self.openaq_adapter),
            ("Tier 3 Open-Meteo", self.openmeteo_adapter),
        )
        for label, adapter in tiers:
            try:
                observation = await adapter.fetch_by_coordinates(latitude, longitude)
                if observation is not None:
                    return observation
            except PROVIDER_FETCH_ERRORS as exc:
                logger.warning("%s failed (%s): %s", label, type(exc).__name__, redact_secrets(exc))
        return None

    async def get_air_quality_for_coordinates(
        self, latitude: float, longitude: float, bypass_cache: bool = False
    ) -> NormalizedObservation | None:
        """Coordinates-aware air quality retrieval with strict multi-source fallback."""
        if not (
            MIN_LATITUDE <= latitude <= MAX_LATITUDE and MIN_LONGITUDE <= longitude <= MAX_LONGITUDE
        ):
            raise ValueError(f"Invalid coordinates: latitude={latitude}, longitude={longitude}")

        cache_key = self._get_cache_key(latitude, longitude)
        if not bypass_cache and cache_key in self._cache:
            entry = self._cache[cache_key]
            if not entry.is_expired():
                logger.debug("Serving air quality from cache for %s", cache_key)
                return self.check_stale_status(entry.observation.model_copy(deep=True))
            self._cache.pop(cache_key, None)

        observation = await self._fetch_from_tiers(latitude, longitude)
        if not observation:
            return None

        observation = self.check_stale_status(observation)
        if observation.station.distance_km is None:
            observation.station.distance_km = haversine_distance_km(
                latitude, longitude, observation.station.latitude, observation.station.longitude
            )

        expires_at = datetime.now(UTC) + timedelta(seconds=settings.CACHE_TTL_SECONDS)
        self._cache[cache_key] = CacheEntry(observation.model_copy(deep=True), expires_at)
        prune_expired(self._cache, lambda entry: entry.expires_at)
        enforce_limit(self._cache, settings.CACHE_MAX_ENTRIES)
        return observation

    def search_nearby_stations(
        self, latitude: float, longitude: float, max_distance_km: float = 50.0
    ) -> list[tuple[StationMetadata, float]]:
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
    ) -> tuple[list[StationMetadata], str]:
        """Prefer real CPCB stations; fall back to the labelled static registry."""
        try:
            stations = await self.cpcb_adapter.fetch_nearby(latitude, longitude, max_distance_km)
        except PROVIDER_FETCH_ERRORS as exc:
            # CPCB errors (including malformed records) fall back to the labelled registry.
            logger.warning("Live station search failed: %s", redact_secrets(exc))
            stations = []
        if stations:
            return [station for station, _ in stations], "CPCB/data.gov.in"
        return [
            station
            for station, _ in self.search_nearby_stations(latitude, longitude, max_distance_km)
        ], "fallback_registry"

    @staticmethod
    def _station_from_observation(observation: CPCBStationObservation) -> StationMetadata:
        return StationMetadata(
            station_id=observation.station_id,
            station_name=observation.station,
            city=observation.city,
            state=observation.state,
            latitude=observation.latitude,
            longitude=observation.longitude,
            provider="CPCB/data.gov.in",
            source_observation_time=observation.last_update,
        )

    @staticmethod
    def _observation_matches(observation: CPCBStationObservation, needle: str) -> bool:
        return not needle or any(
            needle in field.lower()
            for field in (observation.station, observation.city, observation.state)
        )

    async def search_stations_live(
        self,
        query: str | None = None,
        city: str | None = None,
        state: str | None = None,
    ) -> tuple[list[StationMetadata], str]:
        """Search real CPCB station metadata, with a labelled registry fallback."""
        observations: list[CPCBStationObservation] = []
        try:
            observations = await self.cpcb_adapter.get_station_observations(city=city, state=state)
        except PROVIDER_FETCH_ERRORS as exc:
            logger.warning("Live CPCB station search failed: %s", redact_secrets(exc))

        needle = (query or "").strip().lower()
        stations = [
            self._station_from_observation(obs)
            for obs in observations
            if self._observation_matches(obs, needle)
        ]
        if stations:
            return stations, "CPCB/data.gov.in"

        fallback = self.search_stations_by_query(query or city or state or "")
        return [
            station.model_copy(update={"provider": "fallback_registry"}) for station in fallback
        ], "fallback_registry"

    def search_stations_by_query(self, query: str) -> list[StationMetadata]:
        """Case-insensitive search across station names, cities, and states."""
        q = query.strip().lower()
        if not q:
            return INDIAN_CITIES_REGISTRY

        return [
            station
            for station in INDIAN_CITIES_REGISTRY
            if (
                q in station.station_name.lower()
                or q in station.city.lower()
                or q in station.state.lower()
            )
        ]
