from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.observation import NormalizedObservation


class ComparisonDifferential(BaseModel):
    cleanest_station_id: Optional[str] = None
    cleanest_station_name: Optional[str] = None
    most_polluted_station_id: Optional[str] = None
    most_polluted_station_name: Optional[str] = None
    aqi_difference: Optional[int] = None
    pm25_difference_ug_m3: Optional[float] = None
    summary: str


class ComparisonResponse(BaseModel):
    success: bool = True
    stations_count: int = Field(..., ge=0)
    observations: List[NormalizedObservation] = Field(default_factory=list)
    differential: Optional[ComparisonDifferential] = None
