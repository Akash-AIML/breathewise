from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, Field, field_validator


class PollutantType(str, Enum):
    PM2_5 = "PM2.5"
    PM10 = "PM10"
    NO2 = "NO2"
    SO2 = "SO2"
    CO = "CO"
    O3 = "O3"
    NH3 = "NH3"
    PB = "Pb"


class AQICategory(str, Enum):
    GOOD = "Good"
    SATISFACTORY = "Satisfactory"
    MODERATE = "Moderate"
    POOR = "Poor"
    VERY_POOR = "Very Poor"
    SEVERE = "Severe"


class DataQualityStatus(str, Enum):
    VERIFIED = "verified"
    ESTIMATED = "estimated"
    INSUFFICIENT = "insufficient"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class NormalizedPollutantReading(BaseModel):
    pollutant: PollutantType
    value: float = Field(..., ge=0.0, description="Concentration value; must be non-negative")
    unit: str = Field(..., description="Measurement unit (e.g., µg/m³, mg/m³)")
    sub_index: Optional[int] = Field(None, ge=0, description="CPCB calculated sub-index")
    averaging_period_hours: int = Field(24, ge=1, le=24, description="Standard averaging period")


class StationMetadata(BaseModel):
    station_id: str
    station_name: str
    city: str
    state: str
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    distance_km: Optional[float] = Field(None, ge=0.0)
    elevation_m: Optional[float] = None


class NormalizedObservation(BaseModel):
    provider: str = Field(..., description="Data source name (e.g. cpcb_ogd, openaq, openmeteo)")
    station: StationMetadata
    readings: Dict[str, NormalizedPollutantReading] = Field(default_factory=dict)
    calculated_aqi: Optional[int] = Field(None, ge=0, description="Overall CPCB AQI value")
    dominant_pollutant: Optional[PollutantType] = None
    aqi_category: Optional[AQICategory] = None
    data_sufficiency_met: bool = Field(
        False, description="Whether CPCB >=3 pollutants rule is satisfied"
    )
    measurement_timestamp: datetime = Field(
        ..., description="Actual timestamp reported by the station"
    )
    retrieval_timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="When our server retrieved it"
    )
    data_quality_status: DataQualityStatus = Field(DataQualityStatus.VERIFIED)
    notes: Optional[str] = None

    @field_validator("readings")
    @classmethod
    def validate_readings_not_empty(
        cls, v: Dict[str, NormalizedPollutantReading]
    ) -> Dict[str, NormalizedPollutantReading]:
        return v
