import logging
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx

from app.adapters.base import AirQualityAdapter
from app.core.aqi_calculator import compute_official_cpcb_aqi
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
                if resp.status_code != 200:
                    logger.warning("OpenMeteoAdapter: HTTP %s from API", resp.status_code)
                    return None

                data = resp.json()
                return self._parse_response(data, latitude, longitude)
        except Exception as e:
            logger.error("OpenMeteo fetch failed: %s", str(e))
            return None

    async def search_stations(
        self, city: str | None = None, state: str | None = None
    ) -> list[StationMetadata]:
        return []

    @staticmethod
    def _resolve_timezone(data: dict[str, Any]):
        name = data.get("timezone")
        if name:
            try:
                return ZoneInfo(name)
            except (ZoneInfoNotFoundError, ValueError):
                logger.warning("OpenMeteoAdapter: unknown timezone %s; using IST fallback", name)
        return timezone(timedelta(hours=5, minutes=30))

    @staticmethod
    def _parse_local_time(value: str | None, tz) -> datetime | None:
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
        series_map = {
            PollutantType.PM2_5: ("pm2_5", 24),
            PollutantType.PM10: ("pm10", 24),
            PollutantType.NO2: ("nitrogen_dioxide", 24),
            PollutantType.SO2: ("sulphur_dioxide", 24),
            PollutantType.CO: ("carbon_monoxide", 8),
            PollutantType.O3: ("ozone", 8),
        }
        values: dict[PollutantType, float] = {}
        for pollutant, (key, hours) in series_map.items():
            average = OpenMeteoAdapter._rolling_average(hourly_data.get(key, []), index, hours)
            if average is not None:
                values[pollutant] = average
        return values

    @staticmethod
    def _build_readings(
        values: dict[PollutantType, float], averaged: bool
    ) -> dict[PollutantType, NormalizedPollutantReading]:
        readings: dict[PollutantType, NormalizedPollutantReading] = {}
        for pollutant, value in values.items():
            if pollutant == PollutantType.CO:
                reading = NormalizedPollutantReading(
                    pollutant=pollutant,
                    value=round(value / 1000.0, 2),
                    unit="mg/m³",
                    averaging_period_hours=8 if averaged else 1,
                )
            else:
                reading = NormalizedPollutantReading(
                    pollutant=pollutant,
                    value=round(value, 1),
                    unit="µg/m³",
                    averaging_period_hours=(
                        (
                            24
                            if pollutant
                            in (
                                PollutantType.PM2_5,
                                PollutantType.PM10,
                                PollutantType.NO2,
                                PollutantType.SO2,
                            )
                            else 8
                        )
                        if averaged
                        else 1
                    ),
                )
            readings[pollutant] = reading
        return readings

    @staticmethod
    def _instant_values(current: dict[str, Any]) -> dict[PollutantType, float]:
        raw_map = {
            PollutantType.PM2_5: "pm2_5",
            PollutantType.PM10: "pm10",
            PollutantType.NO2: "nitrogen_dioxide",
            PollutantType.SO2: "sulphur_dioxide",
            PollutantType.CO: "carbon_monoxide",
            PollutantType.O3: "ozone",
        }
        values: dict[PollutantType, float] = {}
        for pollutant, key in raw_map.items():
            value = current.get(key)
            if isinstance(value, (int, float)) and value >= 0:
                values[pollutant] = float(value)
        return values

    @staticmethod
    def _completed_hour_indices(data: dict[str, Any], tz) -> list[int]:
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        current_dt = OpenMeteoAdapter._parse_local_time(data.get("current", {}).get("time"), tz)
        if not times or current_dt is None:
            return []
        current_hour = current_dt.replace(minute=0, second=0, microsecond=0)
        indices: list[int] = []
        for index, value in enumerate(times):
            point_dt = OpenMeteoAdapter._parse_local_time(value, tz)
            if point_dt is not None and point_dt < current_hour:
                indices.append(index)
        return indices

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

        # Prefer true CPCB averaging windows built from the hourly model series.
        # Fall back to instantaneous values only when no completed hours exist,
        # and label those readings as estimated rather than 24-hour averages.
        values: dict[PollutantType, float] = {}
        averaged = False
        meas_time = self._parse_local_time(current.get("time"), tz) or datetime.now(UTC)
        if completed_indices:
            last_index = completed_indices[-1]
            values = self._rolling_values_at(hourly_data, last_index)
            if values:
                averaged = True
                meas_time = self._parse_local_time(times[last_index], tz) or meas_time
        if not values:
            values = self._instant_values(current)
        if not values:
            return None

        readings = self._build_readings(values, averaged=averaged)
        calc_result = compute_official_cpcb_aqi(readings)
        quality_status = calc_result.quality_status
        notes = calc_result.reason
        if averaged:
            provenance = (
                "Latest completed 24-hour rolling averages ending "
                f"{meas_time.isoformat()}; Open-Meteo CAMS hourly model data."
            )
            notes = f"{notes}; {provenance}" if notes else provenance
        else:
            if quality_status == DataQualityStatus.VERIFIED:
                quality_status = DataQualityStatus.ESTIMATED
            note = "Instantaneous hourly concentrations used; CPCB 24-hour averaging unavailable."
            notes = f"{notes}; {note}" if notes else note

        # Last 24 completed hours only — never future forecast hours.
        hourly_trend: list[HourlyTrendPoint] = []
        for index in completed_indices[-24:]:
            point_values = self._rolling_values_at(hourly_data, index)
            point_readings = self._build_readings(point_values, averaged=True)
            h_calc = compute_official_cpcb_aqi(point_readings) if point_readings else None
            point_dt = self._parse_local_time(times[index], tz)
            hourly_trend.append(
                HourlyTrendPoint(
                    time=point_dt.isoformat() if point_dt else times[index],
                    pm2_5=round(point_values[PollutantType.PM2_5], 1)
                    if PollutantType.PM2_5 in point_values
                    else None,
                    pm10=round(point_values[PollutantType.PM10], 1)
                    if PollutantType.PM10 in point_values
                    else None,
                    no2=round(point_values[PollutantType.NO2], 1)
                    if PollutantType.NO2 in point_values
                    else None,
                    so2=round(point_values[PollutantType.SO2], 1)
                    if PollutantType.SO2 in point_values
                    else None,
                    co=round(point_values[PollutantType.CO] / 1000.0, 2)
                    if PollutantType.CO in point_values
                    else None,
                    o3=round(point_values[PollutantType.O3], 1)
                    if PollutantType.O3 in point_values
                    else None,
                    aqi=h_calc.aqi if h_calc else None,
                    category=h_calc.category if h_calc else None,
                )
            )

        elevation = data.get("elevation", 0.0)
        lat_label = f"{abs(lat):.4f}°{'N' if lat >= 0 else 'S'}"
        lon_label = f"{abs(lon):.4f}°{'E' if lon >= 0 else 'W'}"
        station = StationMetadata(
            station_id=f"openmeteo_{round(lat, 4)}_{round(lon, 4)}",
            station_name=f"High-Res Observation Grid ({lat_label}, {lon_label})",
            city="Regional Grid Point",
            state="India",
            latitude=lat,
            longitude=lon,
            elevation_m=float(elevation) if elevation else None,
        )

        return NormalizedObservation(
            provider=self.provider_id,
            station=station,
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
