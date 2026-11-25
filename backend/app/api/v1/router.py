from fastapi import APIRouter

from app.api.v1.endpoints import (
    air_quality,
    assistant,
    comparison,
    cpcb,
    health,
    locations,
    recommendations,
    stations,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(cpcb.router, tags=["CPCB Data"])
api_router.include_router(air_quality.router, tags=["Air Quality"])
# Include comparison and recommendations routers before generic stations
api_router.include_router(comparison.router, tags=["Station Comparison"])
api_router.include_router(recommendations.router, tags=["Recommendations & Planning"])
api_router.include_router(assistant.router, tags=["AI Assistant"])
api_router.include_router(locations.router, tags=["Locations"])
api_router.include_router(stations.router, tags=["Stations"])
