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

# Standard CPCB Pollutant code mapping
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


class CPCBAdapter(AirQualityAdapter):
    """
    Adapter for Central Pollution Control Board (CPCB) data
    via the Open Government Data (OGD) Platform India (data.gov.in).
    Dataset resource_id: 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69
    """

    RESOURCE_ID = "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
    BASE_URL = "https://api.data.gov.in/resource"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.DATA_GOV_IN_API_KEY

    @property
    def provider_id(self) -> str:
        return "cpcb_ogd"

    @property
    def provider_name(self) -> str:
        return "Central Pollution Control Board (CPCB / data.gov.in)"

    async def fetch_by_coordinates(
        self, latitude: float, longitude: float
    ) -> Optional[NormalizedObservation]:
        """
        CPCB OGD API organizes data primarily by city/station rather than spatial radius.
        If an API key is available, queries the closest city station.
        """
        if not self.api_key:
            logger.info("CPCBAdapter: No DATA_GOV_IN_API_KEY configured; skipping OGD endpoint.")
            return None

        # Fetch records from OGD
        params = {
            "api-key": self.api_key,
            "format": "json",
            "limit": 50,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                resp = await client.get(f"{self.BASE_URL}/{self.RESOURCE_ID}", params=params)
                if resp.status_code == 429:
                    logger.warning("CPCBAdapter: data.gov.in rate limit exceeded (HTTP 429).")
                    return None
                if resp.status_code != 200:
                    logger.warning(
                        "CPCBAdapter: Received status %s from data.gov.in", resp.status_code
                    )
                    return None

                data = resp.json()
                records = data.get("records", [])
                if not records:
                    return None

                return self._parse_records_to_observation(records, latitude, longitude)
        except Exception as e:
            logger.error("CPCBAdapter fetch failed: %s", str(e))
            return None

    async def search_stations(
        self, city: Optional[str] = None, state: Optional[str] = None
    ) -> List[StationMetadata]:
        if not self.api_key:
            return []

        filters: Dict[str, str] = {}
        if city:
            filters["filters[city]"] = city
        if state:
            filters["filters[state]"] = state

        params = {
            "api-key": self.api_key,
            "format": "json",
            "limit": 100,
            **filters,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                resp = await client.get(f"{self.BASE_URL}/{self.RESOURCE_ID}", params=params)
                if resp.status_code != 200:
                    return []
                records = resp.json().get("records", [])
                stations_map: Dict[str, StationMetadata] = {}
                for r in records:
                    s_id = r.get("station", "unknown")
                    if s_id not in stations_map:
                        stations_map[s_id] = StationMetadata(
                            station_id=s_id,
                            station_name=s_id,
                            city=r.get("city", "Unknown City"),
                            state=r.get("state", "Unknown State"),
                            latitude=float(r.get("latitude", 0.0)) if r.get("latitude") else 0.0,
                            longitude=float(r.get("longitude", 0.0)) if r.get("longitude") else 0.0,
                        )
                return list(stations_map.values())
        except Exception as e:
            logger.error("CPCB search stations failed: %s", str(e))
            return []

    def _parse_records_to_observation(
        self, records: List[Dict[str, Any]], lat: float, lon: float
    ) -> Optional[NormalizedObservation]:
        readings: Dict[PollutantType, NormalizedPollutantReading] = {}
        first = records[0]
        station_name = first.get("station", "CPCB Station")
        city = first.get("city", "Unknown")
        state = first.get("state", "Unknown")
        timestamp_str = first.get("last_update")

        measurement_time = datetime.now(timezone.utc)
        if timestamp_str:
            try:
                # e.g., "24-11-2026 16:00:00" or ISO format
                for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
                    try:
                        measurement_time = datetime.strptime(timestamp_str, fmt).replace(
                            tzinfo=timezone.utc
                        )
                        break
                    except ValueError:
                        continue
            except Exception:
                pass

        for r in records:
            p_raw = str(r.get("pollutant_id", "")).lower().strip()
            p_type = CPCB_POLLUTANT_MAP.get(p_raw)
            if not p_type:
                continue

            val_raw = r.get("pollutant_avg")
            if val_raw is None or val_raw == "" or val_raw == "NA":
                continue
            try:
                val = float(val_raw)
            except ValueError:
                continue

            unit = r.get("pollutant_unit", "µg/m³")
            readings[p_type] = NormalizedPollutantReading(
                pollutant=p_type,
                value=val,
                unit=unit,
                averaging_period_hours=8 if p_type in (PollutantType.CO, PollutantType.O3) else 24,
            )

        if not readings:
            return None

        # Calculate official CPCB AQI
        calc_result = compute_official_cpcb_aqi(readings)

        # Build schema observation
        station = StationMetadata(
            station_id=f"cpcb_{city.lower()}_{station_name.lower().replace(' ', '_')}",
            station_name=station_name,
            city=city,
            state=state,
            latitude=lat,
            longitude=lon,
        )

        return NormalizedObservation(
            provider=self.provider_id,
            station=station,
            readings={k.value: v for k, v in readings.items()},
            calculated_aqi=calc_result.aqi,
            dominant_pollutant=calc_result.dominant_pollutant,
            aqi_category=calc_result.category,
            data_sufficiency_met=calc_result.data_sufficiency_met,
            measurement_timestamp=measurement_time,
            retrieval_timestamp=datetime.now(timezone.utc),
            data_quality_status=calc_result.quality_status,
            notes=calc_result.reason,
        )
