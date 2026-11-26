from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.observation import NormalizedObservation, StationMetadata


class HealthResponse(BaseModel):
    status: str = Field("healthy", description="API health status")
    version: str = Field("0.1.0", description="API version")
    timestamp: datetime = Field(..., description="Server current timestamp")
    environment: str = Field(..., description="Current running environment")
    providers: dict[str, str] = Field(
        default_factory=dict, description="Status of configured data adapters"
    )


class AirQualityResponse(BaseModel):
    success: bool = True
    data: NormalizedObservation | None = None
    message: str | None = None


class StationsResponse(BaseModel):
    success: bool = True
    count: int = Field(..., ge=0)
    data: list[StationMetadata] = Field(default_factory=list)
    message: str | None = None


class ErrorDetail(BaseModel):
    field: str | None = None
    message: str


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
    details: list[ErrorDetail] | None = None
