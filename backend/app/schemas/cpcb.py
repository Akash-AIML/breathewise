from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.observation import DataQualityStatus


class CPCBPollutantStats(BaseModel):
    """Validated min/max/avg values for one pollutant at one station/time."""

    pollutant_id: str = Field(..., description="Original pollutant_id as reported by the provider")
    min: float | None = Field(None, ge=0.0)
    max: float | None = Field(None, ge=0.0)
    avg: float | None = Field(None, ge=0.0)
    unit: str | None = Field(None, description="Only set when explicitly present in source data")


class CPCBStationObservation(BaseModel):
    """One CPCB station observation at one source timestamp."""

    provider: Literal["CPCB"] = "CPCB"
    source: Literal["data.gov.in"] = "data.gov.in"
    country: str = "India"
    state: str
    city: str
    station: str
    station_id: str
    latitude: float
    longitude: float
    distance_km: float | None = Field(None, ge=0.0)
    last_update: datetime = Field(..., description="Source observation timestamp (ISO-8601)")
    retrieval_timestamp: datetime = Field(
        ..., description="When BreatheWise retrieved the record from data.gov.in"
    )
    freshness: DataQualityStatus
    pollutants: dict[str, CPCBPollutantStats] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, value: float) -> float:
        if not -90.0 <= value <= 90.0:
            raise ValueError("latitude must be between -90 and 90")
        return value

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, value: float) -> float:
        if not -180.0 <= value <= 180.0:
            raise ValueError("longitude must be between -180 and 180")
        return value

    @field_validator("station", "state", "city")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("station, state and city are required")
        return value


class CPCBObservationsResponse(BaseModel):
    success: bool = True
    count: int = Field(..., ge=0)
    data: list[CPCBStationObservation] = Field(default_factory=list)
    selected_station_id: str | None = None
    message: str | None = None


class CPCBObservationResponse(BaseModel):
    success: bool = True
    data: CPCBStationObservation | None = None
    message: str | None = None


class CPCBFiltersResponse(BaseModel):
    success: bool = True
    data: dict[str, dict[str, Any]] = Field(default_factory=dict)
    message: str | None = None
