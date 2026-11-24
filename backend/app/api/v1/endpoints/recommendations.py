import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.policy_engine import (
    assess_environmental_risk,
    generate_indoor_guidance,
    generate_personalized_plan,
    generate_sustainable_alternatives,
)
from app.schemas.profile import HouseholdProfile
from app.schemas.recommendation import (
    IndoorGuidance,
    PersonalizedPlan,
    SustainableAlternative,
)
from app.services.air_quality_service import AirQualityService

logger = logging.getLogger(__name__)
router = APIRouter()
air_quality_service = AirQualityService()


class PlanRequest(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    profile: Optional[HouseholdProfile] = Field(
        default_factory=HouseholdProfile, description="Optional household demographic and preference profile"
    )


@router.post("/recommendations/plan", response_model=PersonalizedPlan)
async def generate_plan(request: PlanRequest) -> PersonalizedPlan:
    """
    STAGES 1 & 2: Multi-Stage Deterministic Recommendation Pipeline
    1. Fetches authentic validated observation for user coordinates.
    2. Executes Stage 1 Environmental Assessment (risk classification & data confidence).
    3. Executes Stage 2 Policy Engine (applies household profile rules, priorities, & time-slotted routines).
    """
    obs = await air_quality_service.get_air_quality_for_coordinates(
        latitude=request.lat, longitude=request.lon
    )
    if not obs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Environmental observation currently unavailable for these coordinates.",
        )

    assessment = assess_environmental_risk(obs)
    plan = generate_personalized_plan(assessment, request.profile or HouseholdProfile())
    return plan


@router.get("/recommendations/indoor", response_model=IndoorGuidance)
async def get_indoor_guidance(
    area_sqft: int = Query(600, ge=100, le=10000, description="Home carpet area in sq.ft."),
    aqi: Optional[int] = Query(None, ge=0, le=1000, description="Optional current ambient AQI"),
) -> IndoorGuidance:
    """
    MODULE 5: Returns domestic HEPA sizing CADR, maintenance rules,
    cooking smoke safeguards, and evidence-based plant disclaimers.
    """
    profile = HouseholdProfile(home_area_sqft=area_sqft)
    return generate_indoor_guidance(profile, aqi)


@router.get(
    "/recommendations/sustainable-alternatives",
    response_model=List[SustainableAlternative],
)
async def get_sustainable_alternatives(
    aqi: Optional[int] = Query(None, ge=0, le=1000, description="Optional current ambient AQI"),
) -> List[SustainableAlternative]:
    """
    MODULE 6: Returns documented sustainable transit modes with verified Indian emission factors
    and personal health exposure trade-off assessments.
    """
    profile = HouseholdProfile()
    return generate_sustainable_alternatives(profile, aqi)
