from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class PollutantType(StrEnum):
    PM2_5 = "PM2.5"
    PM10 = "PM10"
    NO2 = "NO2"
    SO2 = "SO2"
    CO = "CO"
    O3 = "O3"
    NH3 = "NH3"
    PB = "Pb"


class AQICategory(StrEnum):
    GOOD = "Good"
    SATISFACTORY = "Satisfactory"
    MODERATE = "Moderate"
    POOR = "Poor"
    VERY_POOR = "Very Poor"
    SEVERE = "Severe"


class DataQualityStatus(StrEnum):
    VERIFIED = "verified"
    ESTIMATED = "estimated"
    DELAYED = "delayed"
    INSUFFICIENT = "insufficient"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class NormalizedPollutantReading(BaseModel):
    pollutant: PollutantType
    value: float = Field(..., ge=0.0, description="Concentration value; must be non-negative")
    unit: str | None = Field(
        None, description="Verified measurement unit; null when the provider omits it"
    )
    sub_index: int | None = Field(None, ge=0, description="CPCB calculated sub-index")
    averaging_period_hours: int | None = Field(
        None, ge=1, le=24, description="Verified averaging period; null when unknown"
    )
    min_value: float | None = Field(None, ge=0.0, description="Source-reported minimum")
    max_value: float | None = Field(None, ge=0.0, description="Source-reported maximum")
    source_pollutant_id: str | None = Field(
        None, description="Original pollutant identifier from the provider"
    )


class HourlyTrendPoint(BaseModel):
    time: str = Field(..., description="ISO timestamp for the hour")
    pm2_5: float | None = None
    pm10: float | None = None
    no2: float | None = None
    so2: float | None = None
    co: float | None = None
    o3: float | None = None
    aqi: int | None = None
    category: AQICategory | None = None


class StationMetadata(BaseModel):
    station_id: str
    station_name: str
    city: str
    state: str
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    distance_km: float | None = Field(None, ge=0.0)
    elevation_m: float | None = None
    provider: str | None = Field(None, description="Source of this station metadata")
    source_observation_time: datetime | None = Field(
        None, description="Source timestamp when this station last reported"
    )


class NormalizedObservation(BaseModel):
    provider: str = Field(..., description="Data source name (e.g. cpcb_ogd, openaq, openmeteo)")
    station: StationMetadata
    readings: dict[str, NormalizedPollutantReading] = Field(default_factory=dict)
    calculated_aqi: int | None = Field(None, ge=0, description="Overall CPCB AQI value")
    dominant_pollutant: PollutantType | None = None
    aqi_category: AQICategory | None = None
    data_sufficiency_met: bool = Field(
        False, description="Whether CPCB >=3 pollutants rule is satisfied"
    )
    measurement_timestamp: datetime = Field(
        ..., description="Actual timestamp reported by the station"
    )
    retrieval_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When our server retrieved it",
    )
    data_quality_status: DataQualityStatus = Field(DataQualityStatus.VERIFIED)
    notes: str | None = None
    hourly_trend: list[HourlyTrendPoint] = Field(
        default_factory=list, description="Historical hourly trend series"
    )

    @field_validator("readings")
    @classmethod
    def validate_readings_not_empty(
        cls, v: dict[str, NormalizedPollutantReading]
    ) -> dict[str, NormalizedPollutantReading]:
        return v
