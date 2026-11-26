import logging
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from app.adapters.base import AirQualityAdapter
from app.core.aqi_calculator import AQICalculatorResult, compute_official_cpcb_aqi
from app.core.config import settings
from app.schemas.observation import (
    DataQualityStatus,
    HourlyTrendPoint,
    NormalizedObservation,
    NormalizedPollutantReading,
    PollutantType,
    StationMetadata,
)

logger = logging.getLogger(__name__)

HTTP_OK = 200
IST = timezone(timedelta(hours=5, minutes=30))

# One lookup table drives both rolling windows and instantaneous readings.
# The second element is the number of hours in the CPCB averaging window.
POLLUTANT_SERIES: dict[PollutantType, tuple[str, int]] = {
    PollutantType.PM2_5: ("pm2_5", 24),
    PollutantType.PM10: ("pm10", 24),
    PollutantType.NO2: ("nitrogen_dioxide", 24),
    PollutantType.SO2: ("sulphur_dioxide", 24),
    PollutantType.CO: ("carbon_monoxide", 8),
    PollutantType.O3: ("ozone", 8),
}

# unit, divisor, rounding digits, averaging hours when a full window exists.
READING_RULES: dict[PollutantType, tuple[str, float, int, int]] = {
    PollutantType.PM2_5: ("µg/m³", 1.0, 1, 24),
    PollutantType.PM10: ("µg/m³", 1.0, 1, 24),
    PollutantType.NO2: ("µg/m³", 1.0, 1, 24),
    PollutantType.SO2: ("µg/m³", 1.0, 1, 24),
    PollutantType.CO: ("mg/m³", 1000.0, 2, 8),
    PollutantType.O3: ("µg/m³", 1.0, 1, 8),
}

# Trend field name, divisor and rounding digits (CO stays in mg/m³).
TREND_RULES: tuple[tuple[str, PollutantType, float, int], ...] = (
    ("pm2_5", PollutantType.PM2_5, 1.0, 1),
    ("pm10", PollutantType.PM10, 1.0, 1),
    ("no2", PollutantType.NO2, 1.0, 1),
    ("so2", PollutantType.SO2, 1.0, 1),
    ("co", PollutantType.CO, 1000.0, 2),
    ("o3", PollutantType.O3, 1.0, 1),
)


class OpenMeteoAdapter(AirQualityAdapter):
    """
    Adapter for Open-Meteo Air Quality API.
    Provides verified atmospheric and ground-level criteria pollutants
    (Copernicus Atmosphere Monitoring Service / CAMS models & station integrations).
    URL: https://air-quality-api.open-meteo.com/v1/air-quality
    Free open access, zero synthetic generation.
    """

    BASE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

    @property
    def provider_id(self) -> str:
        return "openmeteo_cams"

    @property
    def provider_name(self) -> str:
        return "Open-Meteo / Copernicus CAMS Environmental Service"

    async def fetch_by_coordinates(
        self, latitude: float, longitude: float
    ) -> NormalizedObservation | None:
        params: dict[str, str | int | float] = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "current": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
            "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
            # Two past days are required to build genuine rolling 24-hour
            # averages for the last 24 completed hours at any location.
            "past_days": 2,
            "forecast_days": 1,
            "timezone": "auto",
        }

        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                resp = await client.get(self.BASE_URL, params=params)
                if resp.status_code != HTTP_OK:
                    logger.warning("OpenMeteoAdapter: HTTP %s from API", resp.status_code)
                    return None

                data = resp.json()
                return self._parse_response(data, latitude, longitude)
        except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError) as e:
            logger.error("OpenMeteo fetch failed (%s): %s", type(e).__name__, str(e))
            return None

    async def search_stations(
        self, city: str | None = None, state: str | None = None
    ) -> list[StationMetadata]:
        return []

    @staticmethod
    def _resolve_timezone(data: dict[str, Any]) -> tzinfo:
        name = data.get("timezone")
        if name:
            try:
                return ZoneInfo(name)
            except (ZoneInfoNotFoundError, ValueError):
                logger.warning("OpenMeteoAdapter: unknown timezone %s; using IST fallback", name)
        return IST

    @staticmethod
    def _parse_local_time(value: str | None, tz: tzinfo) -> datetime | None:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
        return dt.astimezone(tz) if dt.tzinfo else dt.replace(tzinfo=tz)

    @staticmethod
    def _rolling_average(series: list[Any], end_index: int, hours: int) -> float | None:
        """Average exactly `hours` values ending at end_index; nulls reject the window."""
        start_index = end_index - hours + 1
        if start_index < 0 or end_index >= len(series):
            return None
        window = series[start_index : end_index + 1]
        values = [float(v) for v in window if isinstance(v, (int, float)) and v >= 0]
        if len(values) != hours:
            return None
        return sum(values) / hours

    @staticmethod
    def _rolling_values_at(hourly_data: dict[str, Any], index: int) -> dict[PollutantType, float]:
        values: dict[PollutantType, float] = {}
        for pollutant, (key, hours) in POLLUTANT_SERIES.items():
            average = OpenMeteoAdapter._rolling_average(hourly_data.get(key, []), index, hours)
            if average is not None:
                values[pollutant] = average
        return values

    @staticmethod
    def _build_reading(
        pollutant: PollutantType, value: float, averaged: bool
    ) -> NormalizedPollutantReading:
        unit, divisor, digits, full_window_hours = READING_RULES[pollutant]
        return NormalizedPollutantReading(
            pollutant=pollutant,
            value=round(value / divisor, digits),
            unit=unit,
            averaging_period_hours=full_window_hours if averaged else 1,
        )

    @classmethod
    def _build_readings(
        cls, values: dict[PollutantType, float], averaged: bool
    ) -> dict[PollutantType, NormalizedPollutantReading]:
        return {
            pollutant: cls._build_reading(pollutant, value, averaged)
            for pollutant, value in values.items()
        }

    @staticmethod
    def _instant_values(current: dict[str, Any]) -> dict[PollutantType, float]:
        values: dict[PollutantType, float] = {}
        for pollutant, (key, _) in POLLUTANT_SERIES.items():
            value = current.get(key)
            if isinstance(value, (int, float)) and value >= 0:
                values[pollutant] = float(value)
        return values

    @classmethod
    def _completed_hour_indices(cls, data: dict[str, Any], tz: tzinfo) -> list[int]:
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        current_dt = cls._parse_local_time(data.get("current", {}).get("time"), tz)
        if not times or current_dt is None:
            return []
        current_hour = current_dt.replace(minute=0, second=0, microsecond=0)
        indices: list[int] = []
        for index, value in enumerate(times):
            point_dt = cls._parse_local_time(value, tz)
            if point_dt is not None and point_dt < current_hour:
                indices.append(index)
        return indices

    @classmethod
    def _resolve_values(  # noqa: PLR0913, PLR0917 - one argument per input series
        cls,
        current: dict[str, Any],
        hourly_data: dict[str, Any],
        times: list[Any],
        completed_indices: list[int],
        tz: tzinfo,
        meas_time: datetime,
    ) -> tuple[dict[PollutantType, float], bool, datetime]:
        """Prefer genuine CPCB windows; label instantaneous fallbacks as estimated."""
        values: dict[PollutantType, float] = {}
        if completed_indices:
            last_index = completed_indices[-1]
            values = cls._rolling_values_at(hourly_data, last_index)
            if values:
                meas_time = cls._parse_local_time(times[last_index], tz) or meas_time
                return values, True, meas_time
        return cls._instant_values(current), False, meas_time

    @staticmethod
    def _quality_and_notes(
        calc_result: AQICalculatorResult, averaged: bool, meas_time: datetime
    ) -> tuple[DataQualityStatus, str | None]:
        quality_status = calc_result.quality_status
        notes = calc_result.reason
        if averaged:
            provenance = (
                "Latest completed 24-hour rolling averages ending "
                f"{meas_time.isoformat()}; Open-Meteo CAMS hourly model data."
            )
            notes = f"{notes}; {provenance}" if notes else provenance
            return quality_status, notes

        if quality_status == DataQualityStatus.VERIFIED:
            quality_status = DataQualityStatus.ESTIMATED
        note = "Instantaneous hourly concentrations used; CPCB 24-hour averaging unavailable."
        return quality_status, f"{notes}; {note}" if notes else note

    @classmethod
    def _trend_point(
        cls,
        hourly_data: dict[str, Any],
        times: list[Any],
        index: int,
        tz: tzinfo,
    ) -> HourlyTrendPoint:
        values = cls._rolling_values_at(hourly_data, index)
        readings = cls._build_readings(values, averaged=True)
        h_calc = compute_official_cpcb_aqi(readings) if readings else None
        point_dt = cls._parse_local_time(times[index], tz)
        fields = {
            field: round(values[pollutant] / divisor, digits) if pollutant in values else None
            for field, pollutant, divisor, digits in TREND_RULES
        }
        return HourlyTrendPoint(
            time=point_dt.isoformat() if point_dt else times[index],
            pm2_5=fields["pm2_5"],
            pm10=fields["pm10"],
            no2=fields["no2"],
            so2=fields["so2"],
            co=fields["co"],
            o3=fields["o3"],
            aqi=h_calc.aqi if h_calc else None,
            category=h_calc.category if h_calc else None,
        )

    @staticmethod
    def _build_station(lat: float, lon: float, elevation: Any) -> StationMetadata:
        lat_label = f"{abs(lat):.4f}°{'N' if lat >= 0 else 'S'}"
        lon_label = f"{abs(lon):.4f}°{'E' if lon >= 0 else 'W'}"
        return StationMetadata(
            station_id=f"openmeteo_{round(lat, 4)}_{round(lon, 4)}",
            station_name=f"High-Res Observation Grid ({lat_label}, {lon_label})",
            city="Regional Grid Point",
            state="India",
            latitude=lat,
            longitude=lon,
            elevation_m=float(elevation) if elevation else None,
        )

    def _parse_response(
        self, data: dict[str, Any], lat: float, lon: float
    ) -> NormalizedObservation | None:
        current = data.get("current", {})
        if not current:
            return None

        tz = self._resolve_timezone(data)
        hourly_data = data.get("hourly", {})
        times = hourly_data.get("time", [])
        completed_indices = self._completed_hour_indices(data, tz)
        meas_time = self._parse_local_time(current.get("time"), tz) or datetime.now(UTC)

        values, averaged, meas_time = self._resolve_values(
            current, hourly_data, times, completed_indices, tz, meas_time
        )
        if not values:
            return None

        readings = self._build_readings(values, averaged=averaged)
        calc_result = compute_official_cpcb_aqi(readings)
        quality_status, notes = self._quality_and_notes(calc_result, averaged, meas_time)

        # Last 24 completed hours only — never future forecast hours.
        hourly_trend = [
            self._trend_point(hourly_data, times, index, tz) for index in completed_indices[-24:]
        ]

        return NormalizedObservation(
            provider=self.provider_id,
            station=self._build_station(lat, lon, data.get("elevation", 0.0)),
            readings={k.value: v for k, v in readings.items()},
            calculated_aqi=calc_result.aqi,
            dominant_pollutant=calc_result.dominant_pollutant,
            aqi_category=calc_result.category,
            data_sufficiency_met=calc_result.data_sufficiency_met,
            measurement_timestamp=meas_time,
            retrieval_timestamp=datetime.now(UTC),
            data_quality_status=quality_status,
            notes=notes,
            hourly_trend=hourly_trend,
        )
