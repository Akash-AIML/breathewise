import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import httpx

from app.adapters.base import AirQualityAdapter
from app.core.aqi_calculator import compute_official_cpcb_aqi
from app.core.config import settings
from app.core.geo import haversine_distance_km
from app.schemas.cpcb import CPCBPollutantStats, CPCBStationObservation
from app.schemas.observation import (
    DataQualityStatus,
    NormalizedObservation,
    NormalizedPollutantReading,
    PollutantType,
    StationMetadata,
)

logger = logging.getLogger(__name__)

# httpx logs full request URLs at INFO. data.gov.in requires api-key as a query
# parameter, so INFO logging would leak the secret into application logs.
logging.getLogger("httpx").setLevel(logging.WARNING)

CPCB_POLLUTANT_MAP: Dict[str, PollutantType] = {
    "pm2.5": PollutantType.PM2_5,
    "pm25": PollutantType.PM2_5,
    "pm10": PollutantType.PM10,
    "no2": PollutantType.NO2,
    "so2": PollutantType.SO2,
    "co": PollutantType.CO,
    "ozone": PollutantType.O3,
    "o3": PollutantType.O3,
    "nh3": PollutantType.NH3,
    "pb": PollutantType.PB,
}

REDACTED = "REDACTED"
_SECRET_QUERY = re.compile(r"(api-key=)[^&\s]+", re.IGNORECASE)
_SLUG = re.compile(r"[^a-z0-9]+")
_IST = ZoneInfo("Asia/Kolkata")


class CPCBConfigurationError(RuntimeError):
    """Raised when CPCB is required but not configured."""


class CPCBProviderError(RuntimeError):
    """Base class for upstream CPCB failures with redacted messages."""


class CPCBRateLimitError(CPCBProviderError):
    pass


class CPCBTemporaryError(CPCBProviderError):
    pass


class CPCBResponseError(CPCBProviderError):
    pass


def redact_secrets(value: object) -> str:
    """Remove api-key query values from any text before logging or returning it."""
    return _SECRET_QUERY.sub(r"\1" + REDACTED, str(value))


class CPCBAdapter(AirQualityAdapter):
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

    # ── HTTP client ──────────────────────────────────────────────────────────

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=settings.CPCB_CONNECT_TIMEOUT_SECONDS,
                read=settings.CPCB_READ_TIMEOUT_SECONDS,
                write=settings.CPCB_CONNECT_TIMEOUT_SECONDS,
                pool=settings.CPCB_CONNECT_TIMEOUT_SECONDS,
            )
        )

    async def _request_page(
        self, params: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        """Fetch one page with bounded retries. Never logs the credentialed URL."""
        if not self.api_key:
            raise CPCBConfigurationError("DATA_GOV_IN_API_KEY is not configured.")

        url = f"{self.BASE_URL}/{self.RESOURCE_ID}"
        request_params = {"api-key": self.api_key, "format": "json", **params}
        max_attempts = max(1, settings.CPCB_MAX_RETRIES + 1)

        async with self._client() as client:
            for attempt in range(max_attempts):
                try:
                    response = await client.get(url, params=request_params)
                except httpx.TimeoutException:
                    if attempt + 1 < max_attempts:
                        await asyncio.sleep(settings.CPCB_BACKOFF_BASE_SECONDS * (2**attempt))
                        continue
                    raise CPCBTemporaryError("CPCB provider timed out.") from None
                except httpx.TransportError:
                    if attempt + 1 < max_attempts:
                        await asyncio.sleep(settings.CPCB_BACKOFF_BASE_SECONDS * (2**attempt))
                        continue
                    raise CPCBTemporaryError("CPCB provider network failure.") from None

                if response.status_code == 429:
                    if attempt + 1 < max_attempts:
                        retry_after = response.headers.get("Retry-After", "")
                        delay = (
                            float(retry_after)
                            if retry_after.isdigit()
                            else settings.CPCB_BACKOFF_BASE_SECONDS * (2**attempt)
                        )
                        await asyncio.sleep(min(delay, 10.0))
                        continue
                    raise CPCBRateLimitError("CPCB provider rate limit exceeded.")

                if response.status_code in {500, 502, 503, 504}:
                    if attempt + 1 < max_attempts:
                        await asyncio.sleep(settings.CPCB_BACKOFF_BASE_SECONDS * (2**attempt))
                        continue
                    raise CPCBTemporaryError(f"CPCB provider HTTP {response.status_code}.")

                if response.status_code in {400, 401, 403}:
                    # Permanent failures must not be retried.
                    raise CPCBProviderError(
                        f"CPCB provider rejected the request (HTTP {response.status_code})."
                    )

                if response.status_code != 200:
                    raise CPCBProviderError(f"CPCB provider HTTP {response.status_code}.")

                try:
                    payload = response.json()
                except ValueError:
                    raise CPCBResponseError("CPCB provider returned invalid JSON.") from None

                if not isinstance(payload, dict):
                    raise CPCBResponseError("CPCB provider returned a non-object payload.")
                records = payload.get("records")
                if not isinstance(records, list):
                    raise CPCBResponseError("CPCB provider response has no records list.")
                total = payload.get("total")
                return records, int(total) if isinstance(total, (int, str)) and str(
                    total
                ).isdigit() else None

        raise CPCBTemporaryError("CPCB provider request exhausted retries.")

    async def _fetch_pages(
        self,
        filters: Optional[Dict[str, str]] = None,
        max_pages: Optional[int] = None,
        page_size: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[int]]:
        size = page_size or settings.CPCB_PAGE_SIZE
        pages = max_pages or settings.CPCB_MAX_PAGES
        records: List[Dict[str, Any]] = []
        seen: set[str] = set()
        offset = 0
        reported_total: Optional[int] = None

        for _ in range(pages):
            params: Dict[str, Any] = {"limit": size, "offset": offset}
            params.update(filters or {})
            page, total = await self._request_page(params)
            reported_total = total if total is not None else reported_total
            if not page:
                break
            for record in page:
                fingerprint = str(sorted((str(k), str(v)) for k, v in record.items()))
                if fingerprint not in seen:
                    seen.add(fingerprint)
                    records.append(record)
            if reported_total is not None and offset + len(page) >= reported_total:
                break
            offset += len(page)

        return records, reported_total

    # ── Caching ──────────────────────────────────────────────────────────────

    def _cache_key(self, label: str) -> str:
        return label

    def _cached(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if datetime.now(timezone.utc) >= expires_at:
            return None
        if isinstance(value, list) and all(
            isinstance(item, CPCBStationObservation) for item in value
        ):
            return [self._with_current_freshness(obs) for obs in value]
        return value

    def _store(self, key: str, value: Any) -> None:
        expires = datetime.now(timezone.utc) + timedelta(seconds=settings.CPCB_CACHE_TTL_SECONDS)
        self._cache[key] = (expires, value)
        if (
            isinstance(value, list)
            and value
            and all(isinstance(item, CPCBStationObservation) for item in value)
        ):
            self._last_valid[key] = (datetime.now(timezone.utc), value)

    @staticmethod
    def _as_stale(
        observations: List[CPCBStationObservation], reason: str
    ) -> List[CPCBStationObservation]:
        stale: List[CPCBStationObservation] = []
        for observation in observations:
            warnings = [w for w in observation.warnings if w != reason]
            warnings.append(reason)
            stale.append(
                observation.model_copy(
                    update={"freshness": DataQualityStatus.STALE, "warnings": warnings}
                )
            )
        return stale

    def _previous_valid(self, key: str) -> Optional[List[CPCBStationObservation]]:
        entry = self._last_valid.get(key)
        if not entry:
            return None
        saved_at, observations = entry
        if datetime.now(timezone.utc) - saved_at > timedelta(
            hours=settings.CPCB_LAST_VALID_MAX_HOURS
        ):
            return None
        return self._as_stale(observations, "Refresh failed; showing the last valid observation.")

    async def _load_with_fallback(self, key: str, loader) -> Any:
        """Cache + coalesce requests, preserving the last valid data on failure."""
        cached = self._cached(key)
        if cached is not None:
            return cached
        async with self._lock_for(key):
            cached = self._cached(key)
            if cached is not None:
                return cached
            try:
                value = await loader()
            except CPCBProviderError as exc:
                previous = self._previous_valid(key)
                if previous is not None:
                    logger.warning(
                        "CPCBAdapter refresh failed for %s; using stale cache: %s",
                        key,
                        redact_secrets(exc),
                    )
                    return previous
                raise
            if not value:
                previous = self._previous_valid(key)
                if previous is not None:
                    return previous
                return value
            self._store(key, value)
            return value

    def _lock_for(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    # ── Parsing and normalization ────────────────────────────────────────────

    @staticmethod
    def _parse_number(value: Any) -> Optional[float]:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            number = float(value)
        else:
            text = str(value).strip().replace(",", "")
            if not text or text.upper() in {"NA", "N/A", "NONE", "NULL", "-"}:
                return None
            try:
                number = float(text)
            except ValueError:
                return None
        if number < 0 or number != number or number in (float("inf"), float("-inf")):
            return None
        return number

    @staticmethod
    def _parse_timestamp(value: Any) -> Optional[datetime]:
        if not value or not isinstance(value, str):
            return None
        text = value.strip()
        for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
            try:
                # data.gov.in publishes station-local (IST) timestamps.
                return datetime.strptime(text, fmt).replace(tzinfo=_IST)
            except ValueError:
                continue
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=_IST)

    @staticmethod
    def _station_slug(record: Dict[str, Any]) -> str:
        station = str(record.get("station", "unknown"))
        city = str(record.get("city", "unknown"))
        state = str(record.get("state", "unknown"))
        raw = f"{state}-{city}-{station}".lower()
        return f"cpcb_{_SLUG.sub('_', raw).strip('_')}"

    @staticmethod
    def _grouping_key(record: Dict[str, Any], timestamp: datetime) -> Tuple[Any, ...]:
        return (
            str(record.get("station", "")).strip().lower(),
            str(record.get("city", "")).strip().lower(),
            str(record.get("state", "")).strip().lower(),
            round(float(record.get("latitude", 0.0)), 4),
            round(float(record.get("longitude", 0.0)), 4),
            timestamp.isoformat(),
        )

    @staticmethod
    def _freshness(timestamp: Optional[datetime]) -> Tuple[DataQualityStatus, Optional[str]]:
        if timestamp is None:
            return DataQualityStatus.UNAVAILABLE, "No valid source timestamp."
        now = datetime.now(timezone.utc)
        age = now - timestamp.astimezone(timezone.utc)
        if age < timedelta(minutes=-5):
            return DataQualityStatus.UNAVAILABLE, "Source timestamp is in the future."
        if age <= timedelta(hours=settings.CPCB_FRESH_HOURS):
            return DataQualityStatus.VERIFIED, None
        if age <= timedelta(hours=settings.CPCB_DELAYED_HOURS):
            return DataQualityStatus.DELAYED, "Source observation is delayed."
        return DataQualityStatus.STALE, "Source observation is stale."

    @staticmethod
    def _with_current_freshness(observation: CPCBStationObservation) -> CPCBStationObservation:
        status, warning = CPCBAdapter._freshness(observation.last_update)
        warnings = [w for w in observation.warnings if not w.startswith("Source observation")]
        if warning:
            warnings.append(warning)
        return observation.model_copy(update={"freshness": status, "warnings": warnings})

    def parse_records(self, records: List[Dict[str, Any]]) -> List[CPCBStationObservation]:
        """Group raw pollutant rows into station observations at one timestamp."""
        grouped: Dict[Tuple[Any, ...], CPCBStationObservation] = {}
        retrieval_time = datetime.now(timezone.utc)

        for record in records:
            if not isinstance(record, dict):
                continue
            station = str(record.get("station", "")).strip()
            city = str(record.get("city", "")).strip()
            state = str(record.get("state", "")).strip()
            if not station or not city or not state:
                logger.info("CPCBAdapter: dropped record with missing station/city/state.")
                continue

            timestamp = self._parse_timestamp(record.get("last_update"))
            if timestamp is None:
                logger.info("CPCBAdapter: dropped record with invalid last_update.")
                continue

            latitude = self._parse_number(record.get("latitude"))
            longitude = self._parse_number(record.get("longitude"))
            if (
                latitude is None
                or longitude is None
                or not (-90 <= latitude <= 90 and -180 <= longitude <= 180)
            ):
                logger.info("CPCBAdapter: dropped record with invalid coordinates.")
                continue

            key = self._grouping_key(record, timestamp)
            if key not in grouped:
                freshness, warning = self._freshness(timestamp)
                grouped[key] = CPCBStationObservation(
                    state=state,
                    city=city,
                    station=station,
                    station_id=self._station_slug(record),
                    latitude=latitude,
                    longitude=longitude,
                    last_update=timestamp,
                    retrieval_timestamp=retrieval_time,
                    freshness=freshness,
                    warnings=[warning] if warning else [],
                )
            observation = grouped[key]
            raw_pollutant = str(record.get("pollutant_id", "")).strip()
            if not raw_pollutant:
                logger.info("CPCBAdapter: dropped pollutant row without pollutant_id.")
                continue

            unit_raw = record.get("pollutant_unit")
            unit = str(unit_raw).strip() if isinstance(unit_raw, str) and unit_raw.strip() else None
            stats = CPCBPollutantStats(
                pollutant_id=raw_pollutant,
                min=self._parse_number(record.get("min_value")),
                max=self._parse_number(record.get("max_value")),
                avg=self._parse_number(record.get("avg_value")),
                unit=unit,
            )
            normalized = CPCB_POLLUTANT_MAP.get(raw_pollutant.lower())
            pollutant_key = normalized.value if normalized else raw_pollutant.lower()
            if pollutant_key in observation.pollutants:
                duplicate_warning = "Duplicate pollutant rows were collapsed."
                if duplicate_warning not in observation.warnings:
                    observation.warnings.append(duplicate_warning)
                continue
            observation.pollutants[pollutant_key] = stats

        return list(grouped.values())

    # ── Filter verification and provider discovery ───────────────────────────

    async def _sample_observations(self) -> List[CPCBStationObservation]:
        async def load() -> List[CPCBStationObservation]:
            records, _ = await self._fetch_pages(
                max_pages=1,
                page_size=max(settings.CPCB_MIN_OFFLINE_STATION_SAMPLE, 5),
            )
            return self.parse_records(records)

        return await self._load_with_fallback("sample", load)

    async def _all_observations(self) -> List[CPCBStationObservation]:
        """Bounded pagination, cached. Only used when a precise filter is unavailable."""

        async def load() -> List[CPCBStationObservation]:
            records, _ = await self._fetch_pages()
            return self.parse_records(records)

        return await self._load_with_fallback("all", load)

    @staticmethod
    def _matches(
        observation: CPCBStationObservation, city: Optional[str], state: Optional[str]
    ) -> bool:
        if city and observation.city.strip().lower() != city.strip().lower():
            return False
        if state and observation.state.strip().lower() != state.strip().lower():
            return False
        return True

    async def verify_filters(self) -> Dict[str, Dict[str, Any]]:
        """Independently probe Tamil Nadu and Chennai filters against live data."""

        async def load() -> Dict[str, Dict[str, Any]]:
            sample = await self._sample_observations()
            observed_cities = {obs.city.strip().lower() for obs in sample}
            observed_states = {obs.state.strip().lower() for obs in sample}
            results: Dict[str, Dict[str, Any]] = {}

            for field, value, observed in (
                ("state", "Tamil Nadu", observed_states),
                ("city", "Chennai", observed_cities),
            ):
                entry: Dict[str, Any] = {
                    "value": value,
                    "observed_in_unfiltered_sample": value.lower() in observed,
                    "verified": False,
                    "status": "value_not_in_sample",
                    "record_count": 0,
                }
                if entry["observed_in_unfiltered_sample"]:
                    try:
                        records, total = await self._fetch_pages(
                            filters={f"filters[{field}]": value}, max_pages=1, page_size=5
                        )
                    except CPCBProviderError as exc:
                        entry["status"] = "provider_unavailable"
                        entry["detail"] = redact_secrets(exc)
                    else:
                        parsed = self.parse_records(records)
                        expected_city = value if field == "city" else None
                        expected_state = value if field == "state" else None
                        entry["record_count"] = len(records)
                        entry["reported_total"] = total
                        if not records:
                            entry["status"] = "no_records"
                        elif parsed and all(
                            self._matches(obs, expected_city, expected_state) for obs in parsed
                        ):
                            entry["verified"] = True
                            entry["status"] = "verified"
                        else:
                            entry["status"] = "filter_returned_unrelated_records"
                results[field] = entry
            return results

        return await self._load_with_fallback("filter_verification", load)

    async def _filter_is_verified(self, city: Optional[str], state: Optional[str]) -> bool:
        """Only use upstream filters for values actually seen or probed successfully."""
        sample = await self._sample_observations()
        if city and not any(obs.city.strip().lower() == city.strip().lower() for obs in sample):
            verification = await self.verify_filters()
            if (
                not verification.get("city", {}).get("verified")
                or city.strip().lower() != "chennai"
            ):
                return False
        if state and not any(obs.state.strip().lower() == state.strip().lower() for obs in sample):
            verification = await self.verify_filters()
            if (
                not verification.get("state", {}).get("verified")
                or state.strip().lower() != "tamil nadu"
            ):
                return False
        return True

    async def get_station_observations(
        self, city: Optional[str] = None, state: Optional[str] = None
    ) -> List[CPCBStationObservation]:
        key = f"filter:{city or ''}:{state or ''}"

        async def load() -> List[CPCBStationObservation]:
            observations: List[CPCBStationObservation] = []
            if city or state:
                if await self._filter_is_verified(city, state):
                    filters: Dict[str, str] = {}
                    if state:
                        filters["filters[state]"] = state
                    if city:
                        filters["filters[city]"] = city
                    records, _ = await self._fetch_pages(filters=filters)
                    observations = [
                        obs
                        for obs in self.parse_records(records)
                        if self._matches(obs, city, state)
                    ]
                    if not observations:
                        logger.info(
                            "CPCBAdapter: verified filter returned zero records; "
                            "falling back to bounded unfiltered pagination."
                        )
                else:
                    logger.info("CPCBAdapter: filter value not verified; using local filtering.")
            if not observations:
                observations = [
                    obs for obs in await self._all_observations() if self._matches(obs, city, state)
                ]
            return observations

        return await self._load_with_fallback(key, load)

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

    # ── Conversion to shared application schema ──────────────────────────────

    def to_normalized(
        self,
        observation: CPCBStationObservation,
        user_lat: Optional[float] = None,
        user_lon: Optional[float] = None,
        distance: Optional[float] = None,
    ) -> NormalizedObservation:
        readings: Dict[str, NormalizedPollutantReading] = {}
        for pollutant_key, stats in observation.pollutants.items():
            if stats.avg is None:
                continue
            try:
                pollutant = PollutantType(pollutant_key)
            except ValueError:
                pollutant = None
            readings[pollutant_key] = NormalizedPollutantReading(
                pollutant=pollutant or PollutantType.PM2_5,
                value=stats.avg,
                unit=stats.unit,
                averaging_period_hours=(
                    (8 if pollutant in (PollutantType.CO, PollutantType.O3) else 24)
                    if settings.CPCB_AVERAGING_PERIOD_VERIFIED
                    else None
                ),
                min_value=stats.min,
                max_value=stats.max,
                source_pollutant_id=stats.pollutant_id,
            )

        calc_result = compute_official_cpcb_aqi(readings) if readings else None
        aqi_allowed = settings.CPCB_AVERAGING_PERIOD_VERIFIED
        notes_parts = list(observation.warnings)
        notes_parts.append(f"Source observation: {observation.last_update.isoformat()}")
        notes_parts.append(f"Retrieved: {observation.retrieval_timestamp.isoformat()}")
        if not aqi_allowed:
            notes_parts.append(
                "Official CPCB AQI unavailable: the averaging period of avg_value has not been verified "
                "for this feed. Pollutant concentrations are shown without an AQI claim."
            )
        elif calc_result and not calc_result.data_sufficiency_met:
            notes_parts.append(
                calc_result.reason or "Insufficient pollutant data for official AQI."
            )

        station = StationMetadata(
            station_id=observation.station_id,
            station_name=observation.station,
            city=observation.city,
            state=observation.state,
            latitude=observation.latitude,
            longitude=observation.longitude,
            distance_km=(
                distance
                if distance is not None
                else (
                    haversine_distance_km(
                        user_lat, user_lon, observation.latitude, observation.longitude
                    )
                    if user_lat is not None and user_lon is not None
                    else None
                )
            ),
            provider="CPCB/data.gov.in",
            source_observation_time=observation.last_update,
        )

        return NormalizedObservation(
            provider="CPCB/data.gov.in",
            station=station,
            readings=readings,
            calculated_aqi=calc_result.aqi if calc_result and aqi_allowed else None,
            dominant_pollutant=calc_result.dominant_pollutant
            if calc_result and aqi_allowed
            else None,
            aqi_category=calc_result.category if calc_result and aqi_allowed else None,
            data_sufficiency_met=bool(
                calc_result and calc_result.data_sufficiency_met and aqi_allowed
            ),
            measurement_timestamp=observation.last_update,
            retrieval_timestamp=observation.retrieval_timestamp,
            data_quality_status=observation.freshness,
            notes="; ".join(part for part in notes_parts if part),
        )

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
