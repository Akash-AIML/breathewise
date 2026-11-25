from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.observation import PollutantType
from app.schemas.profile import HouseholdProfile
from app.schemas.recommendation import RiskClassification


class ChatQueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="User question regarding air quality, outdoor safety, or daily planning",
    )
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")
    profile: Optional[HouseholdProfile] = Field(
        default_factory=HouseholdProfile,
        description="Household vulnerability and lifestyle profile",
    )


class ExplanationResponse(BaseModel):
    """
    STAGE 3: Grounded natural-language explanation strictly derived
    from validated Stage 1 environmental telemetry and Stage 2 approved policies.
    """

    answer: str = Field(..., description="Grounded, personalized natural language response")
    referenced_aqi: Optional[int] = Field(None, description="CPCB AQI value referenced in response")
    dominant_pollutant: Optional[PollutantType] = Field(
        None, description="Dominant pollutant driving the risk assessment"
    )
    risk_level: RiskClassification = Field(
        ..., description="Deterministic environmental risk classification"
    )
    approved_actions: List[str] = Field(
        default_factory=list, description="List of approved deterministic actions relevant to query"
    )
    scientific_rationale: str = Field(
        ..., description="Underlying environmental science or health basis"
    )
    provider_provenance: str = Field(..., description="Telemetry source provider")
    llm_grounded: bool = Field(
        False,
        description="Whether generated via validated server-side LLM or deterministic fallback",
    )
    disclaimer: str = Field(
        "BreatheWise provides evidence-based environmental guidance. It does not substitute professional medical diagnosis.",
        description="Mandatory health disclaimer",
    )
