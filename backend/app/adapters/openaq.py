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

OPENAQ_PARAM_MAP: Dict[str, PollutantType] = {
    "pm25": PollutantType.PM2_5,
    "pm10": PollutantType.PM10,
    "no2": PollutantType.NO2,
    "so2": PollutantType.SO2,
    "co": PollutantType.CO,
    "o3": PollutantType.O3,
    "nh3": PollutantType.NH3,
    "pb": PollutantType.PB,
}


class OpenAQAdapter(AirQualityAdapter):
    """
    Adapter for OpenAQ API (v3).
    Endpoint: https://api.openaq.org/v3/
    Requires header X-API-Key for v3.
    """

    BASE_URL = "https://api.openaq.org/v3"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAQ_API_KEY

    @property
    def provider_id(self) -> str:
        return "openaq"

    @property
    def provider_name(self) -> str:
        return "OpenAQ Global Air Quality Network (v3)"

    async def fetch_by_coordinates(
        self, latitude: float, longitude: float
    ) -> Optional[NormalizedObservation]:
        if not self.api_key:
            logger.info("OpenAQAdapter: No OPENAQ_API_KEY configured; skipping v3 endpoint.")
            return None

        headers = {"X-API-Key": self.api_key, "Accept": "application/json"}
        # Find nearest location within 50km (50,000m)
        params = {
            "coordinates": f"{latitude},{longitude}",
            "radius": 50000,
            "limit": 1,
            "order_by": "distance",
        }

        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/locations", headers=headers, params=params
                )
                if resp.status_code == 401:
                    logger.warning("OpenAQAdapter: Invalid or missing OpenAQ API key (HTTP 401).")
                    return None
                if resp.status_code != 200:
                    logger.warning("OpenAQAdapter: HTTP %s from OpenAQ API", resp.status_code)
                    return None

                results = resp.json().get("results", [])
                if not results:
                    return None

                loc = results[0]
                loc_id = loc.get("id")

                # Fetch latest measurements for this location
                meas_resp = await client.get(
                    f"{self.BASE_URL}/locations/{loc_id}/latest", headers=headers
                )
                if meas_resp.status_code != 200:
                    return None

                meas_data = meas_resp.json().get("results", [])
                return self._parse_openaq_data(loc, meas_data, latitude, longitude)
        except Exception as e:
            logger.error("OpenAQ fetch failed: %s", str(e))
            return None

    async def search_stations(
        self, city: Optional[str] = None, state: Optional[str] = None
    ) -> List[StationMetadata]:
        if not self.api_key:
            return []
        headers = {"X-API-Key": self.api_key}
        params: Dict[str, Any] = {"country": "IN", "limit": 50}
        if city:
            params["city"] = city
        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/locations", headers=headers, params=params
                )
                if resp.status_code != 200:
                    return []
                results = resp.json().get("results", [])
                stations = []
                for loc in results:
                    coords = loc.get("coordinates", {})
                    stations.append(
                        StationMetadata(
                            station_id=f"openaq_{loc.get('id')}",
                            station_name=loc.get("name", "OpenAQ Station"),
                            city=loc.get("locality", "Unknown"),
                            state="India",
                            latitude=coords.get("latitude", 0.0),
                            longitude=coords.get("longitude", 0.0),
                        )
                    )
                return stations
        except Exception as e:
            logger.error("OpenAQ search stations error: %s", str(e))
            return []

    def _parse_openaq_data(
        self, loc: Dict[str, Any], meas_data: List[Dict[str, Any]], lat: float, lon: float
    ) -> Optional[NormalizedObservation]:
        readings: Dict[PollutantType, NormalizedPollutantReading] = {}
        reported_timestamps: List[datetime] = []

        for m in meas_data:
            param = str(m.get("parameter", "")).lower()
            p_type = OPENAQ_PARAM_MAP.get(param)
            if not p_type:
                continue

            val = m.get("value")
            if val is None or val < 0.0:
                continue

            unit = m.get("unit", "µg/m³")
            # Convert CO if reported in µg/m³ or ppm to mg/m³
            if p_type == PollutantType.CO:
                if unit == "µg/m³":
                    val = val / 1000.0
                    unit = "mg/m³"
                elif unit == "ppm":
                    val = val * 1.145  # ppm to mg/m3 at STP
                    unit = "mg/m³"

            readings[p_type] = NormalizedPollutantReading(
                pollutant=p_type,
                value=round(val, 2),
                unit=unit,
                averaging_period_hours=8 if p_type in (PollutantType.CO, PollutantType.O3) else 24,
            )

            # Use the latest reported measurement time, never retrieval time.
            dt_str = m.get("datetime")
            if dt_str:
                try:
                    dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                    reported_timestamps.append(dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc))
                except (TypeError, ValueError):
                    continue

        if not readings or not reported_timestamps:
            return None

        latest_ts = max(reported_timestamps)

        calc_result = compute_official_cpcb_aqi(readings)
        coords = loc.get("coordinates", {})

        station = StationMetadata(
            station_id=f"openaq_{loc.get('id')}",
            station_name=loc.get("name", "OpenAQ Station"),
            city=loc.get("locality", "Unknown City"),
            state="India",
            latitude=coords.get("latitude", lat),
            longitude=coords.get("longitude", lon),
            distance_km=round(loc.get("distance", 0) / 1000.0, 2) if "distance" in loc else None,
        )

        return NormalizedObservation(
            provider=self.provider_id,
            station=station,
            readings={k.value: v for k, v in readings.items()},
            calculated_aqi=calc_result.aqi,
            dominant_pollutant=calc_result.dominant_pollutant,
            aqi_category=calc_result.category,
            data_sufficiency_met=calc_result.data_sufficiency_met,
            measurement_timestamp=latest_ts,
            retrieval_timestamp=datetime.now(timezone.utc),
            data_quality_status=calc_result.quality_status,
            notes=calc_result.reason,
        )
