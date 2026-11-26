from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.observation import NormalizedObservation

ComparisonBasis = Literal["live_station", "coordinate_estimate", "mixed"]


class ComparisonDifferential(BaseModel):
    cleanest_station_id: str | None = None
    cleanest_station_name: str | None = None
    most_polluted_station_id: str | None = None
    most_polluted_station_name: str | None = None
    aqi_difference: int | None = None
    pm25_difference_ug_m3: float | None = None
    summary: str


class ComparisonCandidate(BaseModel):
    id: str
    label: str
    city: str | None = None
    state: str | None = None
    latitude: float
    longitude: float
    basis: Literal["live_station", "coordinate_estimate"]
    source: str


class ComparisonPreset(BaseModel):
    key: str
    name: str
    description: str
    ids: list[str]
    basis: Literal["live_station", "coordinate_estimate"]
    source: str
    candidates: list[ComparisonCandidate] = Field(default_factory=list)


class ComparisonPresetsResponse(BaseModel):
    success: bool = True
    source: str
    presets: list[ComparisonPreset] = Field(default_factory=list)
    message: str


class ComparisonResponse(BaseModel):
    success: bool = True
    stations_count: int = Field(..., ge=0)
    observations: list[NormalizedObservation] = Field(default_factory=list)
    differential: ComparisonDifferential | None = None
    basis: ComparisonBasis = "mixed"
    source: str = "unknown"
    requested_ids: list[str] = Field(default_factory=list)
    unresolved_ids: list[str] = Field(default_factory=list)
    message: str = ""
