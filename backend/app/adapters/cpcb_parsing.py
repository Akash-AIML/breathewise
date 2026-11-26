import logging
import math
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.adapters.cpcb_transport import CPCBResponseError
from app.core.aqi_calculator import AQICalculatorResult, compute_official_cpcb_aqi
from app.core.config import settings
from app.core.geo import (
    MAX_LATITUDE,
    MAX_LONGITUDE,
    MIN_LATITUDE,
    MIN_LONGITUDE,
    haversine_distance_km,
)
from app.schemas.cpcb import CPCBPollutantStats, CPCBStationObservation
from app.schemas.observation import (
    DataQualityStatus,
    NormalizedObservation,
    NormalizedPollutantReading,
    PollutantType,
    StationMetadata,
)

logger = logging.getLogger(__name__)

CPCB_POLLUTANT_MAP: dict[str, PollutantType] = {
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

_SLUG = re.compile(r"[^a-z0-9]+")
_IST = ZoneInfo("Asia/Kolkata")
_SHORT_AVERAGING_POLLUTANTS = frozenset({PollutantType.CO, PollutantType.O3})
_LONG_AVERAGING_HOURS = 24
_SHORT_AVERAGING_HOURS = 8
_AQI_UNVERIFIED_NOTE = (
    "Official CPCB AQI unavailable: the averaging period of avg_value has not been verified "
    "for this feed. Pollutant concentrations are shown without an AQI claim."
)
_DUPLICATE_WARNING = "Duplicate pollutant rows were collapsed."


class CPCBParsingMixin:
    """Record parsing, freshness checks, and normalization for CPCBAdapter."""

    @staticmethod
    def _parse_number(value: Any) -> float | None:
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
        if number < 0 or math.isnan(number) or math.isinf(number):
            return None
        return number

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
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
    def _station_slug(record: dict[str, Any]) -> str:
        station = str(record.get("station", "unknown"))
        city = str(record.get("city", "unknown"))
        state = str(record.get("state", "unknown"))
        raw = f"{state}-{city}-{station}".lower()
        return f"cpcb_{_SLUG.sub('_', raw).strip('_')}"

    @staticmethod
    def _grouping_key(record: dict[str, Any], timestamp: datetime) -> tuple[Any, ...]:
        return (
            str(record.get("station", "")).strip().lower(),
            str(record.get("city", "")).strip().lower(),
            str(record.get("state", "")).strip().lower(),
            round(float(record.get("latitude", 0.0)), 4),
            round(float(record.get("longitude", 0.0)), 4),
            timestamp.isoformat(),
        )

    @staticmethod
    def _freshness(timestamp: datetime | None) -> tuple[DataQualityStatus, str | None]:
        if timestamp is None:
            return DataQualityStatus.UNAVAILABLE, "No valid source timestamp."
        now = datetime.now(UTC)
        age = now - timestamp.astimezone(UTC)
        if age < timedelta(minutes=-5):
            return DataQualityStatus.UNAVAILABLE, "Source timestamp is in the future."
        if age <= timedelta(hours=settings.CPCB_FRESH_HOURS):
            return DataQualityStatus.VERIFIED, None
        if age <= timedelta(hours=settings.CPCB_DELAYED_HOURS):
            return DataQualityStatus.DELAYED, "Source observation is delayed."
        return DataQualityStatus.STALE, "Source observation is stale."

    @staticmethod
    def _with_current_freshness(observation: CPCBStationObservation) -> CPCBStationObservation:
        status, warning = CPCBParsingMixin._freshness(observation.last_update)
        warnings = [w for w in observation.warnings if not w.startswith("Source observation")]
        if warning:
            warnings.append(warning)
        return observation.model_copy(update={"freshness": status, "warnings": warnings})

    @staticmethod
    def _record_identity(record: dict[str, Any]) -> tuple[str, str, str] | None:
        station = str(record.get("station", "")).strip()
        city = str(record.get("city", "")).strip()
        state = str(record.get("state", "")).strip()
        if not station or not city or not state:
            logger.info("CPCBAdapter: dropped record with missing station/city/state.")
            return None
        return station, city, state

    @classmethod
    def _record_coordinates(cls, record: dict[str, Any]) -> tuple[float, float] | None:
        latitude = cls._parse_number(record.get("latitude"))
        longitude = cls._parse_number(record.get("longitude"))
        if (
            latitude is None
            or longitude is None
            or not (
                MIN_LATITUDE <= latitude <= MAX_LATITUDE
                and MIN_LONGITUDE <= longitude <= MAX_LONGITUDE
            )
        ):
            logger.info("CPCBAdapter: dropped record with invalid coordinates.")
            return None
        return latitude, longitude

    def _new_observation(
        self,
        record: dict[str, Any],
        identity: tuple[str, str, str],
        timestamp: datetime,
        retrieval_time: datetime,
        coordinates: tuple[float, float],
    ) -> CPCBStationObservation:
        station, city, state = identity
        latitude, longitude = coordinates
        freshness, warning = self._freshness(timestamp)
        return CPCBStationObservation(
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

    def _add_pollutant_row(
        self, observation: CPCBStationObservation, record: dict[str, Any]
    ) -> None:
        raw_pollutant = str(record.get("pollutant_id", "")).strip()
        if not raw_pollutant:
            logger.info("CPCBAdapter: dropped pollutant row without pollutant_id.")
            return

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
            if _DUPLICATE_WARNING not in observation.warnings:
                observation.warnings.append(_DUPLICATE_WARNING)
            return
        observation.pollutants[pollutant_key] = stats

    def parse_records(self, records: list[dict[str, Any]]) -> list[CPCBStationObservation]:
        """Group raw pollutant rows into station observations at one timestamp."""
        if not isinstance(records, list):
            raise CPCBResponseError("CPCB provider returned an invalid records collection.")

        grouped: dict[tuple[Any, ...], CPCBStationObservation] = {}
        retrieval_time = datetime.now(UTC)

        for record in records:
            if not isinstance(record, dict):
                logger.info("CPCBAdapter: dropped malformed record.")
                continue
            identity = self._record_identity(record)
            if identity is None:
                continue

            timestamp = self._parse_timestamp(record.get("last_update"))
            if timestamp is None:
                logger.info("CPCBAdapter: dropped record with invalid last_update.")
                continue

            coordinates = self._record_coordinates(record)
            if coordinates is None:
                continue

            key = self._grouping_key(record, timestamp)
            if key not in grouped:
                grouped[key] = self._new_observation(
                    record, identity, timestamp, retrieval_time, coordinates
                )
            self._add_pollutant_row(grouped[key], record)

        return list(grouped.values())

    @staticmethod
    def _reading_from_stats(
        pollutant_key: str, stats: CPCBPollutantStats
    ) -> NormalizedPollutantReading | None:
        if stats.avg is None:
            return None
        try:
            pollutant = PollutantType(pollutant_key)
        except ValueError:
            # Unsupported identities must never be counted as PM2.5 by the AQI rule.
            logger.info("CPCBAdapter: dropped unsupported pollutant identity %s.", pollutant_key)
            return None

        averaging_period = None
        if settings.CPCB_AVERAGING_PERIOD_VERIFIED:
            averaging_period = (
                _SHORT_AVERAGING_HOURS
                if pollutant in _SHORT_AVERAGING_POLLUTANTS
                else _LONG_AVERAGING_HOURS
            )
        return NormalizedPollutantReading(
            pollutant=pollutant,
            value=stats.avg,
            unit=stats.unit,
            averaging_period_hours=averaging_period,
            min_value=stats.min,
            max_value=stats.max,
            source_pollutant_id=stats.pollutant_id,
        )

    @staticmethod
    def _notes_parts(
        observation: CPCBStationObservation,
        calc_result: AQICalculatorResult | None,
        aqi_allowed: bool,
    ) -> list[str]:
        parts = list(observation.warnings)
        parts.append(f"Source observation: {observation.last_update.isoformat()}")
        parts.append(f"Retrieved: {observation.retrieval_timestamp.isoformat()}")
        if not aqi_allowed:
            parts.append(_AQI_UNVERIFIED_NOTE)
        elif calc_result and not calc_result.data_sufficiency_met:
            parts.append(calc_result.reason or "Insufficient pollutant data for official AQI.")
        return parts

    @staticmethod
    def _station_metadata(
        observation: CPCBStationObservation,
        user_lat: float | None,
        user_lon: float | None,
        distance: float | None,
    ) -> StationMetadata:
        if distance is None and user_lat is not None and user_lon is not None:
            distance = haversine_distance_km(
                user_lat, user_lon, observation.latitude, observation.longitude
            )
        return StationMetadata(
            station_id=observation.station_id,
            station_name=observation.station,
            city=observation.city,
            state=observation.state,
            latitude=observation.latitude,
            longitude=observation.longitude,
            distance_km=distance,
            provider="CPCB/data.gov.in",
            source_observation_time=observation.last_update,
        )

    def to_normalized(
        self,
        observation: CPCBStationObservation,
        user_lat: float | None = None,
        user_lon: float | None = None,
        distance: float | None = None,
    ) -> NormalizedObservation:
        readings = {
            pollutant_key: reading
            for pollutant_key, stats in observation.pollutants.items()
            if (reading := self._reading_from_stats(pollutant_key, stats)) is not None
        }

        # Only recognized PollutantType identities (already filtered by
        # _reading_from_stats) may reach the official CPCB calculator.
        aqi_inputs = {r.pollutant: r for r in readings.values()}
        calc_result = compute_official_cpcb_aqi(aqi_inputs) if aqi_inputs else None
        aqi_allowed = settings.CPCB_AVERAGING_PERIOD_VERIFIED

        return NormalizedObservation(
            provider="CPCB/data.gov.in",
            station=self._station_metadata(observation, user_lat, user_lon, distance),
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
            notes="; ".join(
                part for part in self._notes_parts(observation, calc_result, aqi_allowed) if part
            ),
        )
