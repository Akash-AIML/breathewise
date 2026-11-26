import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

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

OPENAQ_PARAM_MAP: dict[str, PollutantType] = {
    "pm25": PollutantType.PM2_5,
    "pm10": PollutantType.PM10,
    "no2": PollutantType.NO2,
    "so2": PollutantType.SO2,
    "co": PollutantType.CO,
    "o3": PollutantType.O3,
    "nh3": PollutantType.NH3,
    "pb": PollutantType.PB,
}

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401

# CPCB breakpoints are defined against these concentration units.
REQUIRED_UNITS: dict[PollutantType, str] = {
    PollutantType.PM2_5: "µg/m³",
    PollutantType.PM10: "µg/m³",
    PollutantType.NO2: "µg/m³",
    PollutantType.SO2: "µg/m³",
    PollutantType.CO: "mg/m³",
    PollutantType.O3: "µg/m³",
    PollutantType.NH3: "µg/m³",
    PollutantType.PB: "µg/m³",
}

# OpenAQ reports CO in mass or volume units; CPCB breakpoints require mg/m³.
CO_UNIT_CONVERSIONS: dict[str, Callable[[float], float]] = {
    "µg/m³": lambda value: value / 1000.0,
    "ppm": lambda value: value * 1.145,
}
# Ozone ppm -> µg/m³ at 25 °C and 1 atm (48 g/mol / 24.45 L/mol).
O3_PPM_TO_UG_M3 = 1963.0
O3_UNIT_CONVERSIONS: dict[str, Callable[[float], float]] = {
    "ppm": lambda value: value * O3_PPM_TO_UG_M3,
}


class OpenAQAdapter(AirQualityAdapter):
    """
    Adapter for OpenAQ API (v3).
    Endpoint: https://api.openaq.org/v3/
    Requires header X-API-Key for v3.
    """

    BASE_URL = "https://api.openaq.org/v3"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.OPENAQ_API_KEY

    @property
    def provider_id(self) -> str:
        return "openaq"

    @property
    def provider_name(self) -> str:
        return "OpenAQ Global Air Quality Network (v3)"

    @staticmethod
    def _location_results(response: httpx.Response) -> list[dict[str, Any]] | None:
        if response.status_code == HTTP_UNAUTHORIZED:
            logger.warning("OpenAQAdapter: Invalid or missing OpenAQ API key (HTTP 401).")
            return None
        if response.status_code != HTTP_OK:
            logger.warning("OpenAQAdapter: HTTP %s from OpenAQ API", response.status_code)
            return None
        payload = response.json()
        if not isinstance(payload, dict):
            # ValueError is a known provider failure; failover must continue.
            raise ValueError("OpenAQ locations response must be a JSON object.")
        results: list[dict[str, Any]] = payload.get("results", [])
        if not isinstance(results, list):
            raise ValueError("OpenAQ locations response has no results list.")
        return results or None

    @classmethod
    async def _latest_results(
        cls, client: httpx.AsyncClient, headers: dict[str, str], location_id: Any
    ) -> list[dict[str, Any]] | None:
        response = await client.get(
            f"{cls.BASE_URL}/locations/{location_id}/latest", headers=headers
        )
        if response.status_code != HTTP_OK:
            return None
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("OpenAQ latest-results response must be a JSON object.")
        results: list[dict[str, Any]] = payload.get("results", [])
        if not isinstance(results, list):
            raise ValueError("OpenAQ latest-results response has no results list.")
        return results

    async def fetch_by_coordinates(
        self, latitude: float, longitude: float
    ) -> NormalizedObservation | None:
        if not self.api_key:
            logger.info("OpenAQAdapter: No OPENAQ_API_KEY configured; skipping v3 endpoint.")
            return None

        headers = {"X-API-Key": self.api_key, "Accept": "application/json"}
        # Find nearest location within 50km (50,000m)
        params: dict[str, str | int | float] = {
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
                results = self._location_results(resp)
                if not results:
                    return None

                loc = results[0]
                # Fetch latest measurements for this location
                meas_data = await self._latest_results(client, headers, loc.get("id"))
                if meas_data is None:
                    return None
                return self._parse_openaq_data(loc, meas_data, latitude, longitude)
        except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError) as e:
            logger.error("OpenAQ fetch failed (%s): %s", type(e).__name__, str(e))
            return None

    async def search_stations(
        self, city: str | None = None, state: str | None = None
    ) -> list[StationMetadata]:
        if not self.api_key:
            return []
        headers = {"X-API-Key": self.api_key}
        params: dict[str, Any] = {"country": "IN", "limit": 50}
        if city:
            params["city"] = city
        try:
            async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT_SECONDS) as client:
                resp = await client.get(
                    f"{self.BASE_URL}/locations", headers=headers, params=params
                )
                if resp.status_code != HTTP_OK:
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
        except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError) as e:
            logger.error("OpenAQ search stations error (%s): %s", type(e).__name__, str(e))
            return []

    @staticmethod
    def _normalized_value(
        pollutant: PollutantType, value: Any, unit: Any
    ) -> tuple[float, str] | None:
        """Return a CPCB-compatible value/unit, or None for unverifiable units."""
        required_unit = REQUIRED_UNITS[pollutant]
        if unit == required_unit:
            return float(value), required_unit

        if pollutant == PollutantType.CO:
            conversions = CO_UNIT_CONVERSIONS
        elif pollutant == PollutantType.O3:
            conversions = O3_UNIT_CONVERSIONS
        else:
            conversions = {}
        converter = conversions.get(unit) if isinstance(unit, str) else None
        if converter is None:
            return None
        return converter(float(value)), required_unit

    @staticmethod
    def _measurement_source(
        loc: dict[str, Any], measurement: dict[str, Any]
    ) -> tuple[str, Any] | None:
        """Resolve parameter/unit from sensorsId against the location's sensors metadata."""
        if "sensorsId" not in measurement:
            # Direct parameter/unit payloads remain supported for legacy callers.
            return str(measurement.get("parameter", "")).lower(), measurement.get("unit", "µg/m³")

        sensors = loc.get("sensors")
        if not isinstance(sensors, list):
            return None
        sensor = next(
            (
                item
                for item in sensors
                if isinstance(item, dict) and item.get("id") == measurement["sensorsId"]
            ),
            None,
        )
        if sensor is None:
            return None
        parameter = sensor.get("parameter")
        if isinstance(parameter, dict):
            name = parameter.get("name") or parameter.get("id") or ""
            units = parameter.get("units", "µg/m³")
        else:
            name, units = parameter or "", "µg/m³"
        return str(name).lower(), units

    @classmethod
    def _reading_from_measurement(
        cls,
        measurement: dict[str, Any],
        source: tuple[str, Any],
    ) -> tuple[PollutantType, NormalizedPollutantReading] | None:
        param, unit = source
        pollutant = OPENAQ_PARAM_MAP.get(str(param).lower())
        if not pollutant:
            return None

        value = measurement.get("value")
        if value is None or value < 0.0:
            return None

        normalized = cls._normalized_value(pollutant, value, unit)
        if normalized is None:
            # Unknown/unconvertible units must not be compared to CPCI breakpoints.
            return None
        value, unit = normalized
        reading = NormalizedPollutantReading(
            pollutant=pollutant,
            value=round(value, 2),
            unit=unit,
            # Latest values carry no verified averaging window.
            averaging_period_hours=None,
        )
        return pollutant, reading

    @staticmethod
    def _reported_timestamp(measurement: dict[str, Any]) -> datetime | None:
        """Use the latest reported measurement time, never retrieval time."""
        raw = measurement.get("datetime")
        if isinstance(raw, dict):
            # OpenAQ v3 latest results report the observation time as {"utc": ...}.
            raw = raw.get("utc")
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (TypeError, ValueError, AttributeError):
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    @staticmethod
    def _build_station(loc: dict[str, Any], lat: float, lon: float) -> StationMetadata:
        coords = loc.get("coordinates", {})
        return StationMetadata(
            station_id=f"openaq_{loc.get('id')}",
            station_name=loc.get("name", "OpenAQ Station"),
            city=loc.get("locality", "Unknown City"),
            state="India",
            latitude=coords.get("latitude", lat),
            longitude=coords.get("longitude", lon),
            distance_km=round(loc.get("distance", 0) / 1000.0, 2) if "distance" in loc else None,
        )

    def _parse_openaq_data(
        self, loc: dict[str, Any], meas_data: list[dict[str, Any]], lat: float, lon: float
    ) -> NormalizedObservation | None:
        readings: dict[PollutantType, NormalizedPollutantReading] = {}
        reported_timestamps: list[datetime] = []

        for measurement in meas_data:
            source = self._measurement_source(loc, measurement)
            if source is None:
                continue
            parsed = self._reading_from_measurement(measurement, source)
            if parsed is None:
                continue
            pollutant, reading = parsed
            readings[pollutant] = reading

            timestamp = self._reported_timestamp(measurement)
            if timestamp is not None:
                reported_timestamps.append(timestamp)

        if not readings or not reported_timestamps:
            return None

        calc_result = compute_official_cpcb_aqi(readings)
        return NormalizedObservation(
            provider=self.provider_id,
            station=self._build_station(loc, lat, lon),
            readings={k.value: v for k, v in readings.items()},
            calculated_aqi=calc_result.aqi,
            dominant_pollutant=calc_result.dominant_pollutant,
            aqi_category=calc_result.category,
            data_sufficiency_met=calc_result.data_sufficiency_met,
            measurement_timestamp=max(reported_timestamps),
            retrieval_timestamp=datetime.now(UTC),
            data_quality_status=calc_result.quality_status,
            notes=calc_result.reason,
        )
