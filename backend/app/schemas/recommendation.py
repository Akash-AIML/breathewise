from datetime import datetime, timezone
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.observation import AQICategory, DataQualityStatus, PollutantType
from app.schemas.profile import HouseholdProfile


class RiskClassification(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"
    SEVERE = "severe"


class EnvironmentalAssessment(BaseModel):
    """
    Stage 1 Output: Mathematical risk classification and data confidence
    derived strictly from validated observation sensors.
    """

    risk_level: RiskClassification
    aqi: Optional[int] = None
    category: Optional[AQICategory] = None
    dominant_pollutant: Optional[PollutantType] = None
    data_quality: DataQualityStatus
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_stale: bool = False
    assessment_summary: str


class RecommendationItem(BaseModel):
    id: str
    category: Literal["planner", "indoor", "commute", "sustainability", "protective"]
    title: str
    time_of_day: Optional[Literal["morning", "afternoon", "evening", "all_day"]] = None
    action: str
    priority: Literal["critical", "high", "medium", "low"]
    reason: str
    supporting_evidence: str
    expected_impact: Literal[
        "positive_exposure_reduction", "positive_emission_reduction", "balanced"
    ]
    limitations: Optional[str] = None


class IndoorGuidance(BaseModel):
    """
    Module 5: Evidence-based domestic indoor air quality guidance.
    """

    hepa_sizing_cadr_m3_hr: Optional[int] = None
    hepa_sizing_explanation: str
    filter_maintenance_tips: List[str]
    ventilation_advice: str
    cooking_smoke_precautions: List[str]
    practical_low_cost_precautions: List[str]
    houseplant_scientific_disclaimer: str


class SustainableAlternative(BaseModel):
    """
    Module 6: Sustainable mobility and routine alternatives with documented emission factors.
    """

    mode: str
    emission_factor_g_co2_per_km: float
    estimated_emission_reduction_pct: float
    personal_exposure_mitigation: str
    condition_dependent_note: Optional[str] = None


class PersonalizedPlan(BaseModel):
    """
    Stage 2 Output: Complete deterministic personalized routine and guidance package.
    """

    environmental_assessment: EnvironmentalAssessment
    household_profile: HouseholdProfile
    morning_recommendations: List[RecommendationItem]
    afternoon_recommendations: List[RecommendationItem]
    evening_recommendations: List[RecommendationItem]
    indoor_guidance: IndoorGuidance
    sustainable_alternatives: List[SustainableAlternative]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
