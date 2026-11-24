from fastapi import APIRouter

from app.api.v1.endpoints import air_quality, comparison, health, stations

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(air_quality.router, tags=["Air Quality"])
# Include comparison router before stations to avoid /stations/{station_id} route shadowing
api_router.include_router(comparison.router, tags=["Station Comparison"])
api_router.include_router(stations.router, tags=["Stations"])
