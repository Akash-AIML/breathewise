from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.observation import AQICategory, DataQualityStatus, PollutantType
from app.schemas.profile import HouseholdProfile


class RiskClassification(StrEnum):
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
    aqi: int | None = None
    category: AQICategory | None = None
    dominant_pollutant: PollutantType | None = None
    data_quality: DataQualityStatus
    confidence: float = Field(..., ge=0.0, le=1.0)
    is_stale: bool = False
    assessment_summary: str


class RecommendationItem(BaseModel):
    id: str
    category: Literal["planner", "indoor", "commute", "sustainability", "protective"]
    title: str
    time_of_day: Literal["morning", "afternoon", "evening", "all_day"] | None = None
    action: str
    priority: Literal["critical", "high", "medium", "low"]
    reason: str
    supporting_evidence: str
    expected_impact: Literal[
        "positive_exposure_reduction", "positive_emission_reduction", "balanced"
    ]
    limitations: str | None = None


class IndoorGuidance(BaseModel):
    """
    Module 5: Evidence-based domestic indoor air quality guidance.
    """

    hepa_sizing_cadr_m3_hr: int | None = None
    hepa_sizing_explanation: str
    filter_maintenance_tips: list[str]
    ventilation_advice: str
    cooking_smoke_precautions: list[str]
    practical_low_cost_precautions: list[str]
    houseplant_scientific_disclaimer: str


class SustainableAlternative(BaseModel):
    """
    Module 6: Sustainable mobility and routine alternatives with documented emission factors.
    """

    mode: str
    emission_factor_g_co2_per_km: float
    estimated_emission_reduction_pct: float
    personal_exposure_mitigation: str
    condition_dependent_note: str | None = None


class PersonalizedPlan(BaseModel):
    """
    Stage 2 Output: Complete deterministic personalized routine and guidance package.
    """

    environmental_assessment: EnvironmentalAssessment
    household_profile: HouseholdProfile
    morning_recommendations: list[RecommendationItem]
    afternoon_recommendations: list[RecommendationItem]
    evening_recommendations: list[RecommendationItem]
    indoor_guidance: IndoorGuidance
    sustainable_alternatives: list[SustainableAlternative]
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
