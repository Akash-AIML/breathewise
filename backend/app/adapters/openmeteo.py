import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.adapters.base import AirQualityAdapter
from app.core.aqi_calculator import compute_official_cpcb_aqi
from app.core.config import settings
from app.schemas.observation import (
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
    ) -> Optional[NormalizedObservation]:
        params = {
            "latitude": round(latitude, 4),
            "longitude": round(longitude, 4),
            "current": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
            "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
            "timezone": "Asia/Kolkata",
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
        self, city: Optional[str] = None, state: Optional[str] = None
    ) -> List[StationMetadata]:
        # OpenMeteo is a spatial grid API rather than a catalog of fixed physical towers
        return []

    def _parse_response(
        self, data: Dict[str, Any], lat: float, lon: float
    ) -> Optional[NormalizedObservation]:
        current = data.get("current", {})
        if not current:
            return None

        # Parse timestamp: ISO8601 string, e.g. "2026-11-24T16:30"
        time_str = current.get("time")
        try:
            # Open-Meteo current time is in local Asia/Kolkata timezone (+05:30)
            naive_dt = datetime.fromisoformat(time_str)
            # Add IST timezone offset (+05:30)
            from datetime import timedelta
            from datetime import timezone as tz

            ist = tz(timedelta(hours=5, minutes=30))
            meas_time = naive_dt.replace(tzinfo=ist)
        except Exception:
            meas_time = datetime.now(timezone.utc)

        readings: Dict[PollutantType, NormalizedPollutantReading] = {}

        # PM2.5
        pm25_val = current.get("pm2_5")
        if pm25_val is not None and pm25_val >= 0.0:
            readings[PollutantType.PM2_5] = NormalizedPollutantReading(
                pollutant=PollutantType.PM2_5,
                value=round(float(pm25_val), 1),
                unit="µg/m³",
                averaging_period_hours=24,
            )

        # PM10
        pm10_val = current.get("pm10")
        if pm10_val is not None and pm10_val >= 0.0:
            readings[PollutantType.PM10] = NormalizedPollutantReading(
                pollutant=PollutantType.PM10,
                value=round(float(pm10_val), 1),
                unit="µg/m³",
                averaging_period_hours=24,
            )

        # NO2
        no2_val = current.get("nitrogen_dioxide")
        if no2_val is not None and no2_val >= 0.0:
            readings[PollutantType.NO2] = NormalizedPollutantReading(
                pollutant=PollutantType.NO2,
                value=round(float(no2_val), 1),
                unit="µg/m³",
                averaging_period_hours=24,
            )

        # SO2
        so2_val = current.get("sulphur_dioxide")
        if so2_val is not None and so2_val >= 0.0:
            readings[PollutantType.SO2] = NormalizedPollutantReading(
                pollutant=PollutantType.SO2,
                value=round(float(so2_val), 1),
                unit="µg/m³",
                averaging_period_hours=24,
            )

        # CO: Open-Meteo returns CO in µg/m³; CPCB formula requires mg/m³
        co_val = current.get("carbon_monoxide")
        if co_val is not None and co_val >= 0.0:
            co_mg_m3 = round(float(co_val) / 1000.0, 2)
            readings[PollutantType.CO] = NormalizedPollutantReading(
                pollutant=PollutantType.CO,
                value=co_mg_m3,
                unit="mg/m³",
                averaging_period_hours=8,
            )

        # Ozone (O3)
        o3_val = current.get("ozone")
        if o3_val is not None and o3_val >= 0.0:
            readings[PollutantType.O3] = NormalizedPollutantReading(
                pollutant=PollutantType.O3,
                value=round(float(o3_val), 1),
                unit="µg/m³",
                averaging_period_hours=8,
            )

        if not readings:
            return None

        # Compute official CPCB Indian AQI
        calc_result = compute_official_cpcb_aqi(readings)

        elevation = data.get("elevation", 0.0)
        station = StationMetadata(
            station_id=f"openmeteo_{round(lat, 2)}_{round(lon, 2)}",
            station_name=f"High-Res Observation Grid ({round(lat, 2)}°N, {round(lon, 2)}°E)",
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
            retrieval_timestamp=datetime.now(timezone.utc),
            data_quality_status=calc_result.quality_status,
            notes=calc_result.reason,
        )
