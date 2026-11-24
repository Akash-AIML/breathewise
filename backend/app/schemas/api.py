from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.observation import NormalizedObservation, StationMetadata


class HealthResponse(BaseModel):
    status: str = Field("healthy", description="API health status")
    version: str = Field("0.1.0", description="API version")
    timestamp: datetime = Field(..., description="Server current timestamp")
    environment: str = Field(..., description="Current running environment")
    providers: Dict[str, str] = Field(
        default_factory=dict, description="Status of configured data adapters"
    )


class AirQualityResponse(BaseModel):
    success: bool = True
    data: Optional[NormalizedObservation] = None
    message: Optional[str] = None


class StationsResponse(BaseModel):
    success: bool = True
    count: int = Field(..., ge=0)
    data: List[StationMetadata] = Field(default_factory=list)


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
    details: Optional[List[ErrorDetail]] = None
