from fastapi import APIRouter

from app.api.v1.endpoints import air_quality, health, stations

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(air_quality.router, tags=["Air Quality"])
api_router.include_router(stations.router, tags=["Stations"])
