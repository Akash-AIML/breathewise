from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.observation import NormalizedObservation

ComparisonBasis = Literal["live_station", "coordinate_estimate", "mixed"]


class ComparisonDifferential(BaseModel):
    cleanest_station_id: Optional[str] = None
    cleanest_station_name: Optional[str] = None
    most_polluted_station_id: Optional[str] = None
    most_polluted_station_name: Optional[str] = None
    aqi_difference: Optional[int] = None
    pm25_difference_ug_m3: Optional[float] = None
    summary: str


class ComparisonCandidate(BaseModel):
    id: str
    label: str
    city: Optional[str] = None
    state: Optional[str] = None
    latitude: float
    longitude: float
    basis: Literal["live_station", "coordinate_estimate"]
    source: str


class ComparisonPreset(BaseModel):
    key: str
    name: str
    description: str
    ids: List[str]
    basis: Literal["live_station", "coordinate_estimate"]
    source: str
    candidates: List[ComparisonCandidate] = Field(default_factory=list)


class ComparisonPresetsResponse(BaseModel):
    success: bool = True
    source: str
    presets: List[ComparisonPreset] = Field(default_factory=list)
    message: str


class ComparisonResponse(BaseModel):
    success: bool = True
    stations_count: int = Field(..., ge=0)
    observations: List[NormalizedObservation] = Field(default_factory=list)
    differential: Optional[ComparisonDifferential] = None
    basis: ComparisonBasis = "mixed"
    source: str = "unknown"
    requested_ids: List[str] = Field(default_factory=list)
    unresolved_ids: List[str] = Field(default_factory=list)
    message: str = ""
