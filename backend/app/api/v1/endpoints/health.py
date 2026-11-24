from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import settings
from app.schemas.api import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def check_health() -> HealthResponse:
    """Diagnostic health check endpoint providing service & adapter statuses."""
    providers_status = {
        "cpcb_ogd": "configured" if settings.DATA_GOV_IN_API_KEY else "unconfigured_degraded",
        "openaq": "configured" if settings.OPENAQ_API_KEY else "unconfigured_degraded",
        "openmeteo_cams": "operational",
    }
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.now(timezone.utc),
        environment=settings.ENVIRONMENT,
        providers=providers_status,
    )
