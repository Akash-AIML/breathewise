import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from app.adapters.cpcb import CPCBAdapter
from app.adapters.openaq import OpenAQAdapter
from app.adapters.openmeteo import OpenMeteoAdapter
from app.core.config import settings
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


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth in km."""
    r = 6371.0  # Earth's radius in kilometers
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


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
        self.cpcb_adapter = CPCBAdapter()
        self.openaq_adapter = OpenAQAdapter()
        self.openmeteo_adapter = OpenMeteoAdapter()
        self._cache: Dict[str, CacheEntry] = {}

    def _get_cache_key(self, lat: float, lon: float) -> str:
        # 2 decimal places approximates a ~1.1km grid
        return f"{round(lat, 2)}:{round(lon, 2)}"

    def check_stale_status(self, observation: NormalizedObservation) -> NormalizedObservation:
        """Flags observations older than STALE_DATA_THRESHOLD_HOURS as STALE."""
        now = datetime.now(timezone.utc)
        meas_time = observation.measurement_timestamp
        if meas_time.tzinfo is None:
            meas_time = meas_time.replace(tzinfo=timezone.utc)

        age = now - meas_time
        if age > timedelta(hours=settings.STALE_DATA_THRESHOLD_HOURS):
            observation.data_quality_status = DataQualityStatus.STALE
            note = f"Data is {round(age.total_seconds() / 3600, 1)} hours old (threshold is {settings.STALE_DATA_THRESHOLD_HOURS}h)"
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
                return entry.observation

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

            # Store in cache
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.CACHE_TTL_SECONDS)
            self._cache[cache_key] = CacheEntry(observation, expires_at)
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
                station_copy = station.model_copy()
                station_copy.distance_km = dist
                results.append((station_copy, dist))

        results.sort(key=lambda x: x[1])
        return results

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
