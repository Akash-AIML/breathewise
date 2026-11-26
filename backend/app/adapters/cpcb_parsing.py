import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

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

_SLUG = re.compile(r"[^a-z0-9]+")
_IST = ZoneInfo("Asia/Kolkata")


class CPCBParsingMixin:
    """Record parsing, freshness checks, and normalization for CPCBAdapter."""

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
        status, warning = CPCBParsingMixin._freshness(observation.last_update)
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

        aqi_inputs = {r.pollutant: r for r in readings.values()}
        calc_result = compute_official_cpcb_aqi(aqi_inputs) if aqi_inputs else None
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
